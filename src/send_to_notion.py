"""
Notion 寫入模組
對齊 Notion「Meta 廣告週報資料庫」的完整 schema。
Database ID: e6852fdccbac4d1a9648e5528d1074b4
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from config import settings
from utils import http_post

logger = logging.getLogger("meta_weekly_report")

NOTION_VERSION = "2022-06-28"
NOTION_PAGES_URL = "https://api.notion.com/v1/pages"


def _notion_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.notion_api_token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    """
    將 Markdown 報告轉為 Notion block 物件。
    簡易轉換：支援 heading、paragraph、bulleted_list、callout。
    Notion API 單次最多 100 個 children blocks。
    """
    blocks: list[dict[str, Any]] = []
    lines = markdown.split("\n")

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("# ") and not stripped.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]
                },
            })
        elif stripped.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": stripped[3:]}}]
                },
            })
        elif stripped.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": stripped[4:]}}]
                },
            })
        elif stripped.startswith("- "):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]
                },
            })
        elif stripped.startswith("|") and not stripped.startswith("|---"):
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            text = " | ".join(cells)
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                },
            })
        elif stripped.startswith("> "):
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": [{"type": "text", "text": {"content": stripped[2:]}}],
                    "icon": {"type": "emoji", "emoji": "💡"},
                },
            })
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": stripped}}]
                },
            })

    return blocks[:100]


def create_weekly_report_page(
    title: str,
    markdown_report: str,
    summary: dict[str, Any],
    start_date: str,
    end_date: str,
    ai_summary_text: str | None = None,
    error_note: str = "",
) -> str:
    """
    在 Notion「Meta 廣告週報資料庫」中建立週報頁面。
    完整對齊 DB schema，寫入 properties + block content。
    """
    now = datetime.now()

    short_summary_parts = []
    if ai_summary_text:
        short_summary_parts.append(ai_summary_text[:1500])
    else:
        short_summary_parts.append(
            f"花費 {summary['total_spend']:,.0f} 元｜"
            f"購買 {summary['total_purchases']:,.0f} 筆｜"
            f"ROAS {summary['weighted_roas']:.2f}x｜"
            f"加碼 {len(summary['scale_candidates'])} / "
            f"暫停 {len(summary['pause_candidates'])} / "
            f"觀察 {len(summary['watch_list'])}"
        )
    short_summary = "\n".join(short_summary_parts)

    properties: dict[str, Any] = {
        "週報標題": {"title": [{"text": {"content": title}}]},
        "週次": {"rich_text": [{"text": {"content": now.strftime("%Y-W%W")}}]},
        "摘要": {"rich_text": [{"text": {"content": short_summary[:2000]}}]},
        "開始日期": {"date": {"start": start_date}},
        "結束日期": {"date": {"start": end_date}},
        "產生時間": {"date": {"start": now.isoformat()}},
        "報告狀態": {"select": {"name": "成功"}},
        "Telegram已通知": {"checkbox": False},
        "總花費": {"number": summary["total_spend"]},
        "總購買": {"number": summary["total_purchases"]},
        "總購買金額": {"number": summary["total_purchase_value"]},
        "整體ROAS": {"number": summary["weighted_roas"]},
        "高效廣告數": {"number": len(summary["scale_candidates"])},
        "低效廣告數": {"number": len(summary["pause_candidates"])},
    }

    if error_note:
        properties["錯誤備註"] = {
            "rich_text": [{"text": {"content": error_note[:2000]}}]
        }

    payload: dict[str, Any] = {
        "parent": {"database_id": settings.notion_database_id_weekly_report},
        "properties": properties,
        "children": _markdown_to_blocks(markdown_report),
    }

    headers = _notion_headers()
    data = http_post(NOTION_PAGES_URL, headers, payload)

    page_url = data.get("url", "")
    page_id = data.get("id", "")
    logger.info(f"Notion 頁面已建立: {page_url}")

    if page_id and page_url:
        _update_self_link(page_id, page_url)

    return page_url


def _update_self_link(page_id: str, page_url: str) -> None:
    """回寫 Notion連結 URL 到頁面自身。"""
    import requests

    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "Notion連結": {"url": page_url},
        }
    }
    try:
        response = requests.patch(url, headers=_notion_headers(), json=payload, timeout=30)
        response.raise_for_status()
        logger.info("Notion連結已回寫")
    except Exception as e:
        logger.warning(f"回寫 Notion連結 失敗（不影響主流程）: {e}")


def create_error_report_page(
    start_date: str,
    end_date: str,
    error_message: str,
) -> str:
    """報告產生失敗時，在 Notion 建立一筆失敗紀錄。"""
    now = datetime.now()
    title = f"Meta 廣告週報 {end_date}（失敗）"

    payload: dict[str, Any] = {
        "parent": {"database_id": settings.notion_database_id_weekly_report},
        "properties": {
            "週報標題": {"title": [{"text": {"content": title}}]},
            "週次": {"rich_text": [{"text": {"content": now.strftime("%Y-W%W")}}]},
            "開始日期": {"date": {"start": start_date}},
            "結束日期": {"date": {"start": end_date}},
            "產生時間": {"date": {"start": now.isoformat()}},
            "報告狀態": {"select": {"name": "失敗"}},
            "錯誤備註": {"rich_text": [{"text": {"content": error_message[:2000]}}]},
            "Telegram已通知": {"checkbox": False},
        },
    }

    try:
        headers = _notion_headers()
        data = http_post(NOTION_PAGES_URL, headers, payload)
        return data.get("url", "")
    except Exception as e:
        logger.error(f"建立失敗紀錄也失敗了: {e}")
        return ""


def update_telegram_notified(page_id: str) -> None:
    """更新 Notion 頁面的 Telegram 已通知狀態。"""
    import requests

    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "Telegram已通知": {"checkbox": True},
        }
    }
    response = requests.patch(url, headers=_notion_headers(), json=payload, timeout=30)
    response.raise_for_status()
