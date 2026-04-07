"""
Meta Page API 粉專貼文拉取模組
"""
from __future__ import annotations

import logging
from typing import Any

from config import settings
from utils import http_get

logger = logging.getLogger("meta_weekly_report")

META_BASE = f"https://graph.facebook.com/{settings.meta_api_version}"


def fetch_page_posts(
    page_id: str,
    page_access_token: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """拉取粉專最近的貼文。"""
    fields = ["id", "message", "created_time", "permalink_url"]
    url = f"{META_BASE}/{page_id}/posts"
    params = {
        "access_token": page_access_token,
        "fields": ",".join(fields),
        "limit": limit,
    }
    payload = http_get(url, params)
    posts = payload.get("data", [])
    logger.info(f"粉專 {page_id} 取得 {len(posts)} 篇貼文")
    return posts


def fetch_all_pages() -> dict[str, list[dict[str, Any]]]:
    """拉取所有粉專的貼文。"""
    pages = {
        "KOCSKIN": (settings.meta_page_id_kocskin, settings.meta_page_access_token_kocskin),
        "露營瘋": (settings.meta_page_id_camping, settings.meta_page_access_token_camping),
    }

    results: dict[str, list[dict[str, Any]]] = {}
    for name, (page_id, token) in pages.items():
        logger.info(f"拉取 {name} 粉專貼文...")
        try:
            results[name] = fetch_page_posts(page_id, token)
        except Exception as e:
            logger.error(f"拉取 {name} 粉專貼文失敗: {e}")
            results[name] = []

    return results
