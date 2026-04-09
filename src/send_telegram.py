"""
Telegram 通知模組
支援週報通知、日報通知與錯誤通知。
使用 HTML parse_mode 避免 Markdown 特殊字元問題。
"""
from __future__ import annotations

import logging
from datetime import datetime
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


# ── 日報專用通知 ───────────────────────────────────────────
def _format_daily_briefing(brand: str, eval_result: dict, notion_url: str = "") -> str:
    """產生日報文字（HTML 格式給 Telegram）。"""
    summary = eval_result["yesterday_summary"]
    last_3d_summary = eval_result.get("last_3d_summary", {})
    last_7d_summary = eval_result.get("last_7d_summary", {})
    red = eval_result["alerts_red"]
    green = eval_result["alerts_green"]
    yellow = eval_result["alerts_yellow"]

    today_str = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"<b>📊 {brand} 廣告早報 {today_str}</b>",
        "",
    ]

    # 紅色警示
    if red:
        lines.append(f"🔴 <b>立刻處理 ({len(red)})</b>")
        for a in red[:5]:  # 最多顯示 5 條
            lines.append(f"• {a['message']}")
        if len(red) > 5:
            lines.append(f"  ...還有 {len(red) - 5} 條")
        lines.append("")

    # 綠色加碼
    if green:
        lines.append(f"🟢 <b>加碼機會 ({len(green)})</b>")
        for a in green[:5]:
            lines.append(f"• {a['message']}")
        if len(green) > 5:
            lines.append(f"  ...還有 {len(green) - 5} 條")
        lines.append("")

    # 黃色觀察
    if yellow:
        lines.append(f"🟡 <b>注意觀察 ({len(yellow)})</b>")
        for a in yellow[:3]:
            lines.append(f"• {a['message']}")
        if len(yellow) > 3:
            lines.append(f"  ...還有 {len(yellow) - 3} 條")
        lines.append("")

    # 沒事的話顯示「今天平靜」
    if not red and not green and not yellow:
        lines.append("✅ 今日無警示，整體運作正常")
        lines.append("")

    # 昨日總結
    lines.extend([
        "<b>📈 昨日總結</b>",
        f"花費：NT${summary.get('spend', 0):,.0f}",
        f"購買：{summary.get('purchases', 0)} 筆",
        f"營收：NT${summary.get('purchase_value', 0):,.0f}",
        f"ROAS：{summary.get('roas', 0):.2f}x  |  CPA：NT${summary.get('cpa', 0):,.0f}",
        f"廣告組數：{summary.get('ad_count', 0)}",
        "",
    ])

    # 7 天趨勢
    if last_7d_summary.get("ad_count", 0) > 0:
        roas_3d = last_3d_summary.get("roas", 0)
        roas_7d = last_7d_summary.get("roas", 0)
        roas_arrow = "↑" if roas_3d > roas_7d else ("↓" if roas_3d < roas_7d else "→")
        lines.extend([
            "<b>📊 趨勢（過去 3 天 vs 7 天）</b>",
            f"ROAS：{roas_3d:.2f} vs {roas_7d:.2f} {roas_arrow}",
            f"CPA：NT${last_3d_summary.get('cpa', 0):,.0f} vs NT${last_7d_summary.get('cpa', 0):,.0f}",
            "",
        ])

    if notion_url:
        lines.append(f"📎 完整資料：{notion_url}")

    return "\n".join(lines)


def send_daily_briefing(brand: str, eval_result: dict, notion_url: str = "") -> None:
    """發送單一品牌的每日早報。"""
    text = _format_daily_briefing(brand, eval_result, notion_url)
    try:
        _send(text)
        logger.info(f"  ✓ {brand} 日報已發送")
    except Exception as e:
        logger.error(f"  ✗ {brand} 日報發送失敗：{e}")
        # 發失敗也要記住內容，方便後續排錯
        logger.error(f"  訊息內容：\n{text}")


def get_daily_briefing_text(brand: str, eval_result: dict, notion_url: str = "") -> str:
    """供其他模組（例如寫 Notion）取得純文字早報。"""
    text = _format_daily_briefing(brand, eval_result, notion_url)
    # 去掉 HTML tag 給 Notion 用
    import re
    return re.sub(r"<[^>]+>", "", text)
