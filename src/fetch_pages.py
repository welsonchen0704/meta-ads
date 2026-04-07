"""
Meta Page API 粉專貼文拉取模組
動態從 /me/accounts 取得 Page Access Token，不需額外設定。
含貼文 insights（觸及、互動、點擊等）。

Note: 2025/11 起 Meta 廢棄 post_impressions 系列，改用 post_media_view。
"""
from __future__ import annotations

import logging
from typing import Any

from config import settings
from utils import http_get, safe_int

logger = logging.getLogger("meta_weekly_report")

META_BASE = f"https://graph.facebook.com/{settings.meta_api_version}"


def _get_page_access_tokens() -> dict[str, str]:
    """
    用 User Access Token 從 /me/accounts 動態取得所有粉專的 Page Access Token。
    回傳 {page_id: page_access_token}。
    """
    url = f"{META_BASE}/me/accounts"
    params = {
        "access_token": settings.meta_user_access_token,
        "fields": "id,name,access_token",
        "limit": 100,
    }
    try:
        payload = http_get(url, params)
        tokens = {}
        for page in payload.get("data", []):
            page_id = page.get("id", "")
            token = page.get("access_token", "")
            name = page.get("name", "")
            if page_id and token:
                tokens[page_id] = token
                logger.info(f"取得粉專 Token: {name} ({page_id})")
        return tokens
    except Exception as e:
        logger.error(f"取得 Page Access Token 失敗: {e}")
        return {}


def _fetch_post_insights(
    post_id: str,
    page_access_token: str,
) -> dict[str, Any]:
    """
    拉取單篇貼文的 insights 指標。
    2025/11 起 post_impressions 已廢棄，改用 post_media_view。
    逐一嘗試不同指標，任一失敗不影響其他。
    """
    result: dict[str, Any] = {}
    url = f"{META_BASE}/{post_id}/insights"

    # 逐一嘗試各指標（避免一個壞掉整批失敗）
    metrics_to_try = [
        ("post_media_view", "lifetime"),          # 觀看數（取代 impressions）
        ("post_clicks", "lifetime"),              # 點擊數
        ("post_engaged_users", "lifetime"),       # 互動人數
        ("post_reactions_by_type_total", "lifetime"),  # 各類反應
    ]

    for metric_name, period in metrics_to_try:
        params = {
            "access_token": page_access_token,
            "metric": metric_name,
            "period": period,
        }
        try:
            payload = http_get(url, params)
            for item in payload.get("data", []):
                name = item.get("name", "")
                values = item.get("values", [])
                if values:
                    val = values[0].get("value", 0)
                    if isinstance(val, dict):
                        result[name] = val
                        result["total_reactions"] = sum(val.values())
                    else:
                        result[name] = safe_int(val)
        except Exception:
            pass  # 靜默跳過，避免洗 log

    if result:
        logger.info(f"貼文 {post_id} insights: {list(result.keys())}")

    return result


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

        insights = _fetch_post_insights(post_id, page_access_token)

        # 映射到報告欄位（相容原有格式）
        views = insights.get("post_media_view", 0)
        post["post_impressions"] = views          # 用 views 取代 impressions
        post["post_impressions_unique"] = views   # 無獨立觸及，用 views 代替
        post["post_engaged_users"] = insights.get("post_engaged_users", 0)
        post["post_clicks"] = insights.get("post_clicks", 0)
        post["post_reactions_like_total"] = insights.get("total_reactions", 0)
        post["post_activity"] = insights.get("post_engaged_users", 0)

        post["likes_count"] = insights.get("total_reactions", 0)
        post["comments_count"] = 0
        post["shares_count"] = 0

    return posts


def fetch_all_pages() -> dict[str, list[dict[str, Any]]]:
    """拉取所有粉專的貼文。動態取得 Page Access Token。"""
    page_tokens = _get_page_access_tokens()
    if not page_tokens:
        logger.warning("無法取得任何粉專的 Page Access Token")
        return {}

    pages = {
        "KOCSKIN": settings.meta_page_id_kocskin,
        "露營瘋": settings.meta_page_id_camping,
    }

    results: dict[str, list[dict[str, Any]]] = {}
    for name, page_id in pages.items():
        token = page_tokens.get(page_id, "")
        if not token:
            logger.warning(f"找不到 {name} ({page_id}) 的 Page Access Token，跳過")
            results[name] = []
            continue

        logger.info(f"拉取 {name} 粉專貼文...")
        try:
            results[name] = fetch_page_posts(page_id, token)
        except Exception as e:
            logger.error(f"拉取 {name} 粉專貼文失敗: {e}")
            results[name] = []

    return results
