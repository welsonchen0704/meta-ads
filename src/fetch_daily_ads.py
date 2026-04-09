"""
日報專用：抓取多時段廣告數據
針對每個帳戶，分別拉「昨日」「過去 3 天」「過去 7 天」三個時段
回傳結構：{account_name: {"yesterday": [rows], "last_3d": [rows], "last_7d": [rows]}}
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from config import settings
from utils import http_get
from analyze_ads import normalize_ad_row

logger = logging.getLogger("daily_briefing")

META_BASE = f"https://graph.facebook.com/{settings.meta_api_version}"

# 廣告組層級需要的欄位
ADSET_INSIGHT_FIELDS = [
    "campaign_name",
    "adset_name",
    "adset_id",
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
    """Meta Token 相關錯誤。"""
    pass


def _check_token() -> None:
    """確認 token 仍可用。"""
    try:
        data = http_get(
            f"{META_BASE}/me",
            {"access_token": settings.meta_user_access_token},
        )
        logger.info(f"Token 有效，帳號：{data.get('name', 'unknown')}")
    except Exception as e:
        raise MetaTokenError(
            f"Meta User Access Token 可能已過期。錯誤：{e}"
        ) from e


def _date_str(d: datetime) -> str:
    return d.date().isoformat()


def _fetch_period(
    ad_account_id: str,
    start_date: str,
    end_date: str,
    level: str = "adset",
) -> list[dict[str, Any]]:
    """對指定帳戶 + 時段拉取廣告組層級數據。"""
    url = f"{META_BASE}/{ad_account_id}/insights"
    params: dict[str, Any] = {
        "access_token": settings.meta_user_access_token,
        "fields": ",".join(ADSET_INSIGHT_FIELDS),
        "level": level,
        "time_range": f'{{"since":"{start_date}","until":"{end_date}"}}',
        "limit": 200,
    }

    rows: list[dict[str, Any]] = []
    while True:
        payload = http_get(url, params)
        rows.extend(payload.get("data", []))
        next_url = payload.get("paging", {}).get("next")
        if not next_url:
            break
        url = next_url
        params = {}
    return rows


def fetch_account_daily(account_name: str, ad_account_id: str) -> dict[str, list[dict]]:
    """
    對單一廣告帳戶抓三個時段的數據。
    回傳格式：
        {
            "yesterday": [normalized_adset, ...],
            "last_3d":   [normalized_adset, ...],
            "last_7d":   [normalized_adset, ...],
        }
    """
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    three_days_ago = today - timedelta(days=3)
    seven_days_ago = today - timedelta(days=7)

    periods = {
        "yesterday": (_date_str(yesterday), _date_str(yesterday)),
        "last_3d": (_date_str(three_days_ago), _date_str(yesterday)),
        "last_7d": (_date_str(seven_days_ago), _date_str(yesterday)),
    }

    result: dict[str, list[dict]] = {}
    for period_key, (start, end) in periods.items():
        logger.info(f"  [{account_name}] 抓取 {period_key} ({start} ~ {end})...")
        try:
            raw = _fetch_period(ad_account_id, start, end)
            normalized = [
                {**normalize_ad_row(r), "adset_id": r.get("adset_id", "")}
                for r in raw
            ]
            # 數據裡 ad_name 欄位是空的（因為 level=adset），改用 adset_name 當識別
            for n in normalized:
                n["display_name"] = n.get("adset_name") or n.get("ad_name") or "(未命名)"
            result[period_key] = normalized
            logger.info(f"    取得 {len(normalized)} 個廣告組")
        except Exception as e:
            logger.error(f"    失敗：{e}")
            result[period_key] = []

    return result


def fetch_all_accounts_daily() -> dict[str, dict[str, list[dict]]]:
    """
    抓兩個品牌的當日數據。
    回傳：
        {
            "KOCSKIN": {"yesterday": [...], "last_3d": [...], "last_7d": [...]},
            "露營瘋":  {"yesterday": [...], "last_3d": [...], "last_7d": [...]},
        }
    """
    _check_token()

    accounts = {
        "KOCSKIN": settings.meta_ad_account_id_kocskin,
        "露營瘋": settings.meta_ad_account_id_camping,
    }

    results: dict[str, dict[str, list[dict]]] = {}
    for name, account_id in accounts.items():
        logger.info(f"── 拉取 {name} ({account_id}) ──")
        try:
            results[name] = fetch_account_daily(name, account_id)
        except MetaTokenError:
            raise
        except Exception as e:
            logger.error(f"  {name} 整體失敗：{e}")
            results[name] = {"yesterday": [], "last_3d": [], "last_7d": []}

    return results
