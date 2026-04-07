"""
Claude AI 決策摘要模組
將結構化廣告數據交給 Claude 產生中文決策建議。
失敗時不阻斷主流程。
"""
from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from config import settings

logger = logging.getLogger("meta_weekly_report")

SYSTEM_PROMPT = """你是 KOCSKIN 和露營瘋的 Meta 廣告分析助手。
你的任務是根據提供的週報數據，產出一段簡潔的決策摘要。

規則：
1. 用繁體中文
2. 直接講結論，不要廢話
3. 分三段：本週重點、建議操作、風險提醒
4. 每段最多 3-4 句話
5. 低樣本的廣告不要亂下結論
6. 具體提到廣告名稱和數字
7. 不要用「建議持續觀察」這種沒用的話，要給明確的 action item
"""

USER_PROMPT_TEMPLATE = """以下是本週 Meta 廣告週報數據：

報告期間：{start_date} ~ {end_date}

總花費：{total_spend:,.0f} 元
總購買：{total_purchases:,.0f} 筆
總營收：{total_purchase_value:,.0f} 元
整體 ROAS：{weighted_roas:.2f}x

加碼候選（{scale_count} 筆）：
{scale_detail}

暫停候選（{pause_count} 筆）：
{pause_detail}

觀察名單（{watch_count} 筆）：
{watch_detail}

數據不足（{insufficient_count} 筆）：不列出

請產出決策摘要。
"""


def _format_ad_list(ads: list[dict[str, Any]], max_items: int = 5) -> str:
    """格式化廣告列表給 Claude。"""
    if not ads:
        return "無"
    lines = []
    for ad in ads[:max_items]:
        lines.append(
            f"- {ad['ad_name']}（{ad['account']}）"
            f"｜花費 {ad['spend']:,.0f}｜購買 {ad['purchases']:.0f}"
            f"｜ROAS {ad['roas']:.2f}｜CPA {ad['cpa']:.0f}"
        )
    if len(ads) > max_items:
        lines.append(f"  ...還有 {len(ads) - max_items} 筆")
    return "\n".join(lines)


def generate_ai_summary(
    summary: dict[str, Any],
    start_date: str,
    end_date: str,
) -> str | None:
    """
    呼叫 Claude API 產生決策摘要。
    失敗時回傳 None，不阻斷主流程。
    """
    if not settings.anthropic_api_key:
        logger.warning("未設定 ANTHROPIC_API_KEY，跳過 AI 摘要")
        return None

    try:
        user_message = USER_PROMPT_TEMPLATE.format(
            start_date=start_date,
            end_date=end_date,
            total_spend=summary["total_spend"],
            total_purchases=summary["total_purchases"],
            total_purchase_value=summary["total_purchase_value"],
            weighted_roas=summary["weighted_roas"],
            scale_count=len(summary["scale_candidates"]),
            scale_detail=_format_ad_list(summary["scale_candidates"]),
            pause_count=len(summary["pause_candidates"]),
            pause_detail=_format_ad_list(summary["pause_candidates"]),
            watch_count=len(summary["watch_list"]),
            watch_detail=_format_ad_list(summary["watch_list"], max_items=8),
            insufficient_count=len(summary["insufficient_data"]),
        )

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        ai_text = response.content[0].text
        logger.info(f"AI 摘要產生成功（{len(ai_text)} 字）")
        return ai_text

    except Exception as e:
        logger.error(f"AI 摘要產生失敗: {e}")
        return None
