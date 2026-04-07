"""
Meta Ads API 數據拉取模組
支援分頁、精確日期範圍、Token 過期偵測。
"""
from __future__ import annotations

import logging
from typing import Any

from config import settings
from utils import http_get, get_last_week_range

logger = logging.getLogger("meta_weekly_report")

META_BASE = f"https://graph.facebook.com/{settings.meta_api_version}"

AD_INSIGHT_FIELDS = [
    "campaign_name",
    "adset_name",
    "ad_name",
    "spend",
    "impressions",
    "reach",
    "clicks",
    "ctr",
    "cpm",
    "frequency",
    "actions",
    "action_values",
    "purchase_roas",
    "cost_per_action_type",
]


class MetaTokenError(Exception):
    """Meta API Token 相關錯誤。"""
    pass


def _check_token_validity() -> None:
    """呼叫 /me 確認 token 仍然有效。"""
    url = f"{META_BASE}/me"
    try:
        data = http_get(url, {"access_token": settings.meta_user_access_token})
        logger.info(f"Token 有效，帳號: {data.get('name', 'unknown')}")
    except Exception as e:
        raise MetaTokenError(
            f"Meta User Access Token 可能已過期或無效。"
            f"請到 Meta Developer 後台重新產生 token。錯誤: {e}"
        ) from e


def fetch_ad_insights(
    ad_account_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    拉取指定廣告帳戶的 ad-level insights。
    預設取上週一到上週日的完整週數據。
    """
    if start_date is None or end_date is None:
        start_date, end_date = get_last_week_range()

    url = f"{META_BASE}/{ad_account_id}/insights"
    params: dict[str, Any] = {
        "access_token": settings.meta_user_access_token,
        "fields": ",".join(AD_INSIGHT_FIELDS),
        "level": "ad",
        "time_range": f'{{"since":"{start_date}","until":"{end_date}"}}',
        "limit": limit,
    }

    rows: list[dict[str, Any]] = []
    page_count = 0

    while True:
        payload = http_get(url, params)
        data = payload.get("data", [])
        rows.extend(data)
        page_count += 1
        logger.info(f"  第 {page_count} 頁，取得 {len(data)} 筆")

        next_url = payload.get("paging", {}).get("next")
        if not next_url:
            break
        url = next_url
        params = {}

    logger.info(f"帳戶 {ad_account_id} 共取得 {len(rows)} 筆廣告數據")
    return rows


def fetch_all_ads(
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """拉取所有廣告帳戶的數據，回傳 {帳戶名: [rows]}。"""
    _check_token_validity()

    accounts = {
        "KOCSKIN": settings.meta_ad_account_id_kocskin,
        "小燕": settings.meta_ad_account_id_xiaoyan,
    }

    results: dict[str, list[dict[str, Any]]] = {}
    for name, account_id in accounts.items():
        logger.info(f"拉取 {name} 廣告數據...")
        try:
            results[name] = fetch_ad_insights(account_id, start_date, end_date)
        except MetaTokenError:
            raise
        except Exception as e:
            logger.error(f"拉取 {name} 失敗: {e}")
            results[name] = []

    return results
