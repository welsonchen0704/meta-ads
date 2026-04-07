"""
Meta Page API 粉專貼文拉取模組
含貼文 insights（觸及、互動、點擊等）。
"""
from __future__ import annotations

import logging
from typing import Any

from config import settings
from utils import http_get, safe_int

logger = logging.getLogger("meta_weekly_report")

META_BASE = f"https://graph.facebook.com/{settings.meta_api_version}"

# 要拉取的貼文 insights 指標
POST_INSIGHT_METRICS = [
    "post_impressions",              # 曝光次數
    "post_impressions_unique",       # 觸及人數
    "post_engaged_users",            # 互動人數
    "post_clicks",                   # 貼文點擊次數
    "post_reactions_like_total",     # 按讚數
    "post_activity",                 # 所有互動（留言+分享+點擊）
]


def _fetch_post_insights(
    post_id: str,
    page_access_token: str,
) -> dict[str, int]:
    """拉取單篇貼文的 insights 指標。"""
    url = f"{META_BASE}/{post_id}/insights"
    params = {
        "access_token": page_access_token,
        "metric": ",".join(POST_INSIGHT_METRICS),
    }
    try:
        payload = http_get(url, params)
        result: dict[str, int] = {}
        for item in payload.get("data", []):
            name = item.get("name", "")
            values = item.get("values", [])
            if values:
                result[name] = safe_int(values[0].get("value", 0))
        return result
    except Exception as e:
        logger.warning(f"拉取貼文 {post_id} insights 失敗: {e}")
        return {}


def fetch_page_posts(
    page_id: str,
    page_access_token: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """拉取粉專最近的貼文，並附加 insights 數據。"""
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

    # 為每篇貼文拉取 insights
    for post in posts:
        post_id = post.get("id", "")
        if not post_id:
            continue

        # 從 insights API 取詳細指標
        insights = _fetch_post_insights(post_id, page_access_token)
        post["post_impressions"] = insights.get("post_impressions", 0)
        post["post_impressions_unique"] = insights.get("post_impressions_unique", 0)
        post["post_engaged_users"] = insights.get("post_engaged_users", 0)
        post["post_clicks"] = insights.get("post_clicks", 0)
        post["post_reactions_like_total"] = insights.get("post_reactions_like_total", 0)
        post["post_activity"] = insights.get("post_activity", 0)

        # 用 insights 數據填入顯示欄位
        post["likes_count"] = insights.get("post_reactions_like_total", 0)
        post["comments_count"] = 0  # insights 無單獨留言數，用 activity 替代
        post["shares_count"] = 0    # insights 無單獨分享數

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
