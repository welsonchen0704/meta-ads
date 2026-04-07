"""
Telegram 通知模組
支援成功通知和錯誤通知。
使用 HTML parse_mode 避免 Markdown 特殊字元問題。
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from config import settings

logger = logging.getLogger("meta_weekly_report")

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _send(text: str, parse_mode: str = "HTML") -> None:
    """底層發送函數。"""
    url = TELEGRAM_API.format(token=settings.telegram_bot_token)
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()


def send_report_notification(
    title: str,
    summary: dict[str, Any],
    notion_url: str,
    ai_summary_text: str | None = None,
) -> None:
    """發送週報完成通知。"""
    lines = [
        f"<b>📊 {title}</b>",
        "",
        f"花費：{summary['total_spend']:,.0f} 元",
        f"購買：{summary['total_purchases']:,.0f} 筆",
        f"營收：{summary['total_purchase_value']:,.0f} 元",
        f"ROAS：{summary['weighted_roas']:.2f}x",
        "",
        f"🟢 加碼候選：{len(summary['scale_candidates'])} 筆",
        f"🔴 暫停候選：{len(summary['pause_candidates'])} 筆",
        f"🟡 觀察：{len(summary['watch_list'])} 筆",
    ]

    if ai_summary_text:
        lines.append("")
        lines.append("<b>AI 摘要：</b>")
        lines.append(ai_summary_text[:500])

    lines.append("")
    lines.append(f"📎 完整報告：{notion_url}")

    try:
        _send("\n".join(lines))
        logger.info("Telegram 通知已發送")
    except Exception as e:
        logger.error(f"Telegram 通知發送失敗: {e}")


def send_error_notification(error_message: str) -> None:
    """發送錯誤通知。即使主流程失敗，也要讓 Welson 知道。"""
    text = (
        "<b>⚠️ Meta 週報產生失敗</b>\n\n"
        f"錯誤訊息：\n<code>{error_message[:1000]}</code>\n\n"
        "請檢查 GitHub Actions log。"
    )
    try:
        _send(text)
        logger.info("錯誤通知已發送")
    except Exception as e:
        logger.critical(f"連 Telegram 錯誤通知都發送失敗: {e}")


def send_token_expiry_warning() -> None:
    """Token 即將過期或已過期的警告。"""
    text = (
        "<b>🔑 Meta Token 可能已過期</b>\n\n"
        "Meta User Access Token 驗證失敗。\n"
        "請到 Meta Developer 後台重新產生 token，\n"
        "然後更新 GitHub Secrets 中的 META_USER_ACCESS_TOKEN。"
    )
    try:
        _send(text)
    except Exception:
        pass
