"""
日報專用：寫入 Notion 廣告每日數據資料庫
跟既有 send_to_notion.py 的「週報頁面」邏輯不同——這裡是寫資料庫的列。
適配 Notion API 2025-09 起的 data_sources 新架構。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests

from config import settings

logger = logging.getLogger("daily_briefing")

NOTION_BASE = "https://api.notion.com/v1"
NOTION_HEADERS = {
    "Authorization": f"Bearer {settings.notion_api_token}",
    "Notion-Version": "2025-09-03",
    "Content-Type": "application/json",
}


def _resolve_data_source_id(database_id: str) -> str:
    """從 database_id 拿 data_source_id（新版 Notion API）。"""
    r = requests.get(
        f"{NOTION_BASE}/databases/{database_id}",
        headers=NOTION_HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    sources = r.json().get("data_sources", [])
    if not sources:
        raise RuntimeError(f"資料庫 {database_id} 沒有 data source")
    return sources[0]["id"]


def _query_existing(data_source_id: str, date_str: str) -> str | None:
    """查當日是否已有記錄，回傳 page_id 或 None。"""
    r = requests.post(
        f"{NOTION_BASE}/data_sources/{data_source_id}/query",
        headers=NOTION_HEADERS,
        json={
            "filter": {"property": "日期", "title": {"equals": date_str}}
        },
        timeout=30,
    )
    r.raise_for_status()
    results = r.json().get("results", [])
    return results[0]["id"] if results else None


def write_daily_record(
    database_id: str,
    date_str: str,
    summary: dict[str, Any],
    alerts: dict[str, list],
    briefing_text: str,
) -> str:
    """
    寫入單日廣告數據到指定資料庫（upsert）。
    回傳寫入的 page id 或 url。
    """
    data_source_id = _resolve_data_source_id(database_id)

    properties = {
        "日期": {"title": [{"text": {"content": date_str}}]},
        "總花費": {"number": float(summary.get("spend", 0))},
        "購買數": {"number": int(summary.get("purchases", 0))},
        "總營收": {"number": float(summary.get("purchase_value", 0))},
        "整體ROAS": {"number": float(summary.get("roas", 0))},
        "平均CPA": {"number": float(summary.get("cpa", 0))},
        "平均CTR": {"number": float(summary.get("ctr", 0))},
        "廣告數": {"number": int(summary.get("ad_count", 0))},
        "紅色警示數": {"number": len(alerts.get("alerts_red", []))},
        "綠色加碼數": {"number": len(alerts.get("alerts_green", []))},
        "黃色觀察數": {"number": len(alerts.get("alerts_yellow", []))},
        "早報摘要": {
            "rich_text": [{"text": {"content": briefing_text[:2000]}}]
        },
        "更新時間": {"date": {"start": datetime.now().isoformat()}},
    }

    existing_page_id = _query_existing(data_source_id, date_str)
    if existing_page_id:
        r = requests.patch(
            f"{NOTION_BASE}/pages/{existing_page_id}",
            headers=NOTION_HEADERS,
            json={"properties": properties},
            timeout=30,
        )
        r.raise_for_status()
        logger.info(f"  ✓ 已更新 {date_str} 既有記錄")
        return existing_page_id
    else:
        r = requests.post(
            f"{NOTION_BASE}/pages",
            headers=NOTION_HEADERS,
            json={
                "parent": {
                    "type": "data_source_id",
                    "data_source_id": data_source_id,
                },
                "properties": properties,
            },
            timeout=30,
        )
        r.raise_for_status()
        page_id = r.json().get("id", "")
        logger.info(f"  ✓ 新增 {date_str} 記錄")
        return page_id
