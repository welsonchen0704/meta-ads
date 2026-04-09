"""
日報判斷規則引擎
規則設計（Welson 月預算 NT$200K, CPA 目標 200-500, ~10 廣告組）：

🔴 紅色（立刻處理）
  A1: 廣告組「過去 3 天」ROAS < 1.5
  A2: 廣告組「昨日」花費 > 1500 且 0 購買
  A3: 廣告組「過去 3 天」CPA > 1000（CPA 目標的 2 倍）
  A4: 帳戶「昨日」總花費 > 10000（防跑費）

🟢 綠色（加碼建議）
  C1: 廣告組「過去 3 天」ROAS > 3.0
  C2: 廣告組「過去 2 天 ≈ last_3d 取後 2 段不切確，改用 last_3d」ROAS > 4.0

🟡 黃色（注意觀察）
  B1: 廣告組「過去 3 天」ROAS 1.5-2.0
  B2: 廣告組「昨日」frequency > 4
  B3: 廣告組「過去 7 天 vs 過去 3 天」CTR 下跌 > 40%
"""
from __future__ import annotations

import logging
from typing import Any

from config import settings

logger = logging.getLogger("daily_briefing")


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    """彙總多廣告組數據（用於帳戶層級判斷）。"""
    total_spend = sum(r.get("spend", 0) for r in rows)
    total_purchases = sum(r.get("purchases", 0) for r in rows)
    total_purchase_value = sum(r.get("purchase_value", 0) for r in rows)
    total_impressions = sum(r.get("impressions", 0) for r in rows)
    total_clicks = sum(r.get("clicks", 0) for r in rows)

    weighted_roas = (
        sum(r.get("roas", 0) * r.get("spend", 0) for r in rows) / total_spend
        if total_spend > 0 else 0
    )
    avg_cpa = total_spend / total_purchases if total_purchases > 0 else 0
    overall_ctr = total_clicks / total_impressions * 100 if total_impressions > 0 else 0

    return {
        "spend": round(total_spend, 0),
        "purchases": int(total_purchases),
        "purchase_value": round(total_purchase_value, 0),
        "roas": round(weighted_roas, 2),
        "cpa": round(avg_cpa, 0),
        "ctr": round(overall_ctr, 2),
        "ad_count": len(rows),
    }


def _build_index(rows: list[dict[str, Any]]) -> dict[str, dict]:
    """以 adset_id 為 key 建立索引，方便跨時段比對。"""
    return {r.get("adset_id", "") or r.get("display_name", ""): r for r in rows}


def evaluate_account(periods: dict[str, list[dict]]) -> dict[str, Any]:
    """
    對單一帳戶的多時段資料跑判斷規則。
    回傳：
        {
            "account_summary": {昨日彙總},
            "alerts_red": [警示廣告組...],
            "alerts_green": [加碼建議...],
            "alerts_yellow": [觀察項目...],
            "trends": {7天趨勢比較},
        }
    """
    yesterday = periods.get("yesterday", [])
    last_3d = periods.get("last_3d", [])
    last_7d = periods.get("last_7d", [])

    s = settings

    # 彙總
    yesterday_summary = _aggregate(yesterday)
    last_3d_summary = _aggregate(last_3d)
    last_7d_summary = _aggregate(last_7d)

    yesterday_idx = _build_index(yesterday)
    last_3d_idx = _build_index(last_3d)
    last_7d_idx = _build_index(last_7d)

    alerts_red: list[dict] = []
    alerts_green: list[dict] = []
    alerts_yellow: list[dict] = []

    # ── 帳戶層級規則 (A4) ─────────────────────
    if yesterday_summary["spend"] > s.daily_red_account_spend_cap:
        alerts_red.append({
            "rule": "A4",
            "level": "account",
            "name": "帳戶總花費",
            "message": f"昨日總花費 NT${yesterday_summary['spend']:,.0f} 超過警戒線 NT${s.daily_red_account_spend_cap:,.0f}",
        })

    # ── 廣告組層級規則 ─────────────────────
    # 以 last_3d 為主迴圈（過去 3 天活躍的廣告組）
    for adset_id, ad_3d in last_3d_idx.items():
        name = ad_3d.get("display_name") or ad_3d.get("adset_name") or "(未命名)"
        spend_3d = ad_3d.get("spend", 0)
        roas_3d = ad_3d.get("roas", 0)
        cpa_3d = ad_3d.get("cpa", 0)
        purchases_3d = ad_3d.get("purchases", 0)

        # 數據量太小不判斷
        if spend_3d < s.daily_min_spend_for_judgment * 3:
            continue

        ad_yesterday = yesterday_idx.get(adset_id, {})
        ad_7d = last_7d_idx.get(adset_id, {})

        # ── A1: ROAS < 1.5 連 3 天 ──
        if roas_3d > 0 and roas_3d < s.daily_red_roas_threshold:
            alerts_red.append({
                "rule": "A1",
                "level": "adset",
                "name": name,
                "spend": spend_3d,
                "roas": roas_3d,
                "purchases": purchases_3d,
                "message": f"{name}：過去 3 天 ROAS {roas_3d:.2f}（警戒 < {s.daily_red_roas_threshold}），花 NT${spend_3d:,.0f}",
            })
            continue

        # ── A2: 昨日花費 > 1500 且 0 購買 ──
        yesterday_spend = ad_yesterday.get("spend", 0)
        yesterday_purchases = ad_yesterday.get("purchases", 0)
        if yesterday_spend > s.daily_red_no_purchase_spend and yesterday_purchases == 0:
            alerts_red.append({
                "rule": "A2",
                "level": "adset",
                "name": name,
                "spend": yesterday_spend,
                "roas": 0,
                "purchases": 0,
                "message": f"{name}：昨日花 NT${yesterday_spend:,.0f}、0 購買",
            })
            continue

        # ── A3: CPA > 1000 連 3 天 ──
        if cpa_3d > 0 and cpa_3d > s.daily_red_cpa_threshold:
            alerts_red.append({
                "rule": "A3",
                "level": "adset",
                "name": name,
                "spend": spend_3d,
                "cpa": cpa_3d,
                "roas": roas_3d,
                "purchases": purchases_3d,
                "message": f"{name}：過去 3 天 CPA NT${cpa_3d:,.0f}（目標 < NT${s.daily_red_cpa_threshold:,.0f}）",
            })
            continue

        # ── C2: ROAS > 4.0（強訊號）──
        if roas_3d >= s.daily_green_roas_2day:
            alerts_green.append({
                "rule": "C2",
                "level": "adset",
                "name": name,
                "spend": spend_3d,
                "roas": roas_3d,
                "purchases": purchases_3d,
                "message": f"{name}：過去 3 天 ROAS {roas_3d:.2f} ✨ → 建議加碼",
            })
            continue

        # ── C1: ROAS > 3.0 ──
        if roas_3d >= s.daily_green_roas_3day:
            alerts_green.append({
                "rule": "C1",
                "level": "adset",
                "name": name,
                "spend": spend_3d,
                "roas": roas_3d,
                "purchases": purchases_3d,
                "message": f"{name}：過去 3 天 ROAS {roas_3d:.2f} → 建議加碼 30%",
            })
            continue

        # ── B1: ROAS 1.5-2.0 ──
        if s.daily_yellow_roas_low <= roas_3d < s.daily_yellow_roas_high:
            alerts_yellow.append({
                "rule": "B1",
                "level": "adset",
                "name": name,
                "spend": spend_3d,
                "roas": roas_3d,
                "purchases": purchases_3d,
                "message": f"{name}：ROAS {roas_3d:.2f}（接近警戒線）",
            })

        # ── B2: frequency > 4 ──
        freq = ad_yesterday.get("frequency", 0)
        if freq > s.daily_yellow_frequency:
            alerts_yellow.append({
                "rule": "B2",
                "level": "adset",
                "name": name,
                "frequency": freq,
                "message": f"{name}：Frequency {freq:.2f}，建議換素材或受眾",
            })

        # ── B3: CTR 下滑 > 40% (7d vs 3d) ──
        ctr_7d = ad_7d.get("ctr", 0)
        ctr_3d = ad_3d.get("ctr", 0)
        if ctr_7d > 0.5 and ctr_3d > 0:
            drop_pct = (ctr_7d - ctr_3d) / ctr_7d * 100
            if drop_pct > s.daily_yellow_ctr_drop_pct:
                alerts_yellow.append({
                    "rule": "B3",
                    "level": "adset",
                    "name": name,
                    "ctr_7d": ctr_7d,
                    "ctr_3d": ctr_3d,
                    "drop_pct": drop_pct,
                    "message": f"{name}：CTR {ctr_7d:.2f}% → {ctr_3d:.2f}%（-{drop_pct:.0f}%），疑似創意疲勞",
                })

    # 7 天 vs 3 天的趨勢
    trends = {
        "spend_7d_avg": last_7d_summary["spend"] / 7 if last_7d_summary["spend"] else 0,
        "roas_7d": last_7d_summary["roas"],
        "roas_3d": last_3d_summary["roas"],
        "cpa_7d": last_7d_summary["cpa"],
        "cpa_3d": last_3d_summary["cpa"],
    }

    return {
        "yesterday_summary": yesterday_summary,
        "last_3d_summary": last_3d_summary,
        "last_7d_summary": last_7d_summary,
        "alerts_red": alerts_red,
        "alerts_green": alerts_green,
        "alerts_yellow": alerts_yellow,
        "trends": trends,
    }
