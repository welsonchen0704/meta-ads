"""
共用工具函數
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import requests

logger = logging.getLogger("meta_weekly_report")


def http_get(url: str, params: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    """共用 HTTP GET，含基本錯誤處理。"""
    response = requests.get(url, params=params or {}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def http_post(url: str, headers: dict[str, str], json_data: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    """共用 HTTP POST，含基本錯誤處理。"""
    response = requests.post(url, headers=headers, json=json_data, timeout=timeout)
    response.raise_for_status()
    return response.json()


def get_last_week_range() -> tuple[str, str]:
    """
    取得上一個完整週的日期範圍（週一到週日）。
    如果今天是週一，回傳上週一到上週日。
    """
    today = datetime.now().date()
    days_since_monday = today.weekday()  # 0=Mon, 6=Sun
    if days_since_monday == 0:
        last_monday = today - timedelta(days=7)
    else:
        last_monday = today - timedelta(days=days_since_monday + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday.isoformat(), last_sunday.isoformat()


def get_week_label(date_str: str) -> str:
    """
    將日期字串（YYYY-MM-DD）轉換為 ISO week label（例如 '2026-W14'）。
    用於 HTML 週報標題與 Notion 週次欄位對照。
    """
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return d.strftime("%G-W%V")
    except Exception:
        return date_str


def safe_float(value: Any, default: float = 0.0) -> float:
    """安全轉換為 float。"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """安全轉換為 int。"""
    if value is None:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default
