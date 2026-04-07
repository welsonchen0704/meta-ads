"""
廣告數據正規化與分類模組
根據 SPEC v1 規則判斷：數據不足、加碼候選、暫停候選、觀察。
"""
from __future__ import annotations

import logging
from typing import Any

from config import settings
from utils import safe_float, safe_int

logger = logging.getLogger("meta_weekly_report")


def _find_action_value(
    items: list[dict[str, Any]] | None,
    action_type: str,
) -> float:
    """從 Meta actions / action_values / purchase_roas / cost_per_action_type 中找特定指標。"""
    if not items:
        return 0.0
    for item in items:
        if item.get("action_type") == action_type:
            return safe_float(item.get("value", 0))
    return 0.0


def normalize_ad_row(raw: dict[str, Any]) -> dict[str, Any]:
    """將 Meta API 回傳的 raw row 正規化為統一格式。"""
    spend = safe_float(raw.get("spend"))
    impressions = safe_int(raw.get("impressions"))
    clicks = safe_int(raw.get("clicks"))
    ctr = safe_float(raw.get("ctr"))
    cpm = safe_float(raw.get("cpm"))
    reach = safe_int(raw.get("reach"))
    frequency = safe_float(raw.get("frequency"))

    actions = raw.get("actions") or []
    action_values = raw.get("action_values") or []
    purchase_roas_list = raw.get("purchase_roas") or []
    cost_per_action = raw.get("cost_per_action_type") or []

    purchases = _find_action_value(actions, "purchase")
    landing_page_views = _find_action_value(actions, "landing_page_view")
    add_to_cart = _find_action_value(actions, "add_to_cart")
    initiate_checkout = _find_action_value(actions, "initiate_checkout")
    roas = _find_action_value(purchase_roas_list, "omni_purchase")
    cpa = _find_action_value(cost_per_action, "purchase")
    purchase_value = _find_action_value(action_values, "omni_purchase")

    return {
        "campaign_name": raw.get("campaign_name", ""),
        "adset_name": raw.get("adset_name", ""),
        "ad_name": raw.get("ad_name", ""),
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "ctr": round(ctr, 2),
        "cpm": round(cpm, 2),
        "reach": reach,
        "frequency": round(frequency, 2),
        "purchases": purchases,
        "landing_page_views": landing_page_views,
        "add_to_cart": add_to_cart,
        "initiate_checkout": initiate_checkout,
        "roas": round(roas, 2),
        "cpa": round(cpa, 2),
        "purchase_value": round(purchase_value, 2),
    }


def classify_ad(row: dict[str, Any]) -> str:
    """
    根據 SPEC v1 規則分類廣告。

    數據不足：spend < 300 或 impressions < 1000 或 clicks < 30
    加碼候選：spend >= 1000 且 purchases >= 3 且 roas >= 4 且 frequency < 2.5
    暫停候選：spend >= 1000 且 purchases == 0
    觀察：其他
    """
    s = settings

    # 數據不足
    if (
        row["spend"] < s.threshold_insufficient_spend
        or row["impressions"] < s.threshold_insufficient_impressions
        or row["clicks"] < s.threshold_insufficient_clicks
    ):
        return "數據不足"

    # 加碼候選（必須同時符合所有條件，含 spend >= 1000）
    if (
        row["spend"] >= s.threshold_scale_spend
        and row["purchases"] >= s.threshold_scale_purchases
        and row["roas"] >= s.threshold_scale_roas
        and row["frequency"] < s.threshold_scale_frequency
    ):
        return "加碼候選"

    # 暫停候選
    if row["spend"] >= s.threshold_pause_spend and row["purchases"] == 0:
        return "暫停候選"

    # 其他一律觀察
    return "觀察"


def analyze_account(
    rows: list[dict[str, Any]],
    account_name: str = "",
) -> list[dict[str, Any]]:
    """正規化並分類一個帳戶的所有廣告。"""
    results = []
    for raw in rows:
        normalized = normalize_ad_row(raw)
        normalized["decision"] = classify_ad(normalized)
        normalized["account"] = account_name
        results.append(normalized)

    from collections import Counter
    counts = Counter(r["decision"] for r in results)
    logger.info(
        f"{account_name}: 共 {len(results)} 筆廣告 — "
        + ", ".join(f"{k}: {v}" for k, v in counts.items())
    )

    return results


def compute_summary(all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """計算所有帳戶的彙總數據。"""
    total_spend = sum(r["spend"] for r in all_rows)
    total_purchases = sum(r["purchases"] for r in all_rows)
    total_purchase_value = sum(r["purchase_value"] for r in all_rows)

    weighted_roas_num = sum(r["roas"] * r["spend"] for r in all_rows if r["spend"] > 0)
    weighted_roas = weighted_roas_num / total_spend if total_spend > 0 else 0

    by_decision: dict[str, list[dict[str, Any]]] = {}
    for r in all_rows:
        by_decision.setdefault(r["decision"], []).append(r)

    scale_candidates = sorted(
        by_decision.get("加碼候選", []),
        key=lambda x: (x["roas"], x["spend"]),
        reverse=True,
    )

    pause_candidates = sorted(
        by_decision.get("暫停候選", []),
        key=lambda x: x["spend"],
        reverse=True,
    )

    watch_list = sorted(
        by_decision.get("觀察", []),
        key=lambda x: x["spend"],
        reverse=True,
    )

    insufficient = by_decision.get("數據不足", [])

    return {
        "total_spend": round(total_spend, 0),
        "total_purchases": total_purchases,
        "total_purchase_value": round(total_purchase_value, 0),
        "weighted_roas": round(weighted_roas, 2),
        "scale_candidates": scale_candidates,
        "pause_candidates": pause_candidates,
        "watch_list": watch_list,
        "insufficient_data": insufficient,
        "total_ads": len(all_rows),
    }
