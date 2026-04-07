"""
Markdown 週報產生模組
完整輸出四個分類 + 彙總 + AI 摘要。
僅含 KOCSKIN 廣告數據。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


def _format_ad_row(row: dict[str, Any]) -> str:
    """格式化單筆廣告為 Markdown（含曝光/觸及/點擊等媒體指標）。"""
    return (
        f"- **{row['ad_name']}**（{row.get('account', '')}）\n"
        f"  花費 {row['spend']:,.0f}｜購買 {row['purchases']:.0f}｜"
        f"ROAS {row['roas']:.2f}｜CPA {row['cpa']:.0f}｜頻率 {row['frequency']:.1f}\n"
        f"  曝光 {row['impressions']:,}｜觸及 {row['reach']:,}｜"
        f"點擊 {row['clicks']:,}｜CTR {row['ctr']:.2f}%｜CPM {row['cpm']:.1f}"
    )


def _section_ads(title: str, emoji: str, ads: list[dict[str, Any]], max_show: int = 5) -> str:
    """產生一個分類區段的 Markdown。"""
    lines = [f"\n## {emoji} {title}（{len(ads)} 筆）\n"]
    if not ads:
        lines.append("本週無此分類廣告。\n")
        return "\n".join(lines)

    for ad in ads[:max_show]:
        lines.append(_format_ad_row(ad))
    if len(ads) > max_show:
        lines.append(f"\n> ...還有 {len(ads) - max_show} 筆未列出")
    lines.append("")
    return "\n".join(lines)


def build_markdown_report(
    summary: dict[str, Any],
    ai_summary_text: str | None,
    start_date: str,
    end_date: str,
) -> str:
    """產生完整的 Markdown 週報（僅廣告數據）。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    sections = []

    # ── 標題與總覽 ──
    sections.append(f"# Meta 廣告週報\n")
    sections.append(f"報告期間：{start_date} ~ {end_date}")
    sections.append(f"產生時間：{now}\n")
    sections.append(f"## 總覽\n")
    sections.append(f"| 指標 | 數值 |")
    sections.append(f"|------|------|")
    sections.append(f"| 總花費 | {summary['total_spend']:,.0f} 元 |")
    sections.append(f"| 總購買 | {summary['total_purchases']:,.0f} 筆 |")
    sections.append(f"| 總營收 | {summary['total_purchase_value']:,.0f} 元 |")
    sections.append(f"| 整體 ROAS | {summary['weighted_roas']:.2f}x |")
    sections.append(f"| 廣告總數 | {summary['total_ads']} |")
    sections.append("")

    # ── AI 決策摘要 ──
    if ai_summary_text:
        sections.append("\n## AI 決策摘要\n")
        sections.append(ai_summary_text)
        sections.append("")

    # ── 四個分類 ──
    sections.append(_section_ads("加碼候選", "🟢", summary["scale_candidates"]))
    sections.append(_section_ads("暫停候選", "🔴", summary["pause_candidates"]))
    sections.append(_section_ads("觀察名單", "🟡", summary["watch_list"], max_show=8))
    sections.append(
        _section_ads("數據不足", "⚪", summary["insufficient_data"], max_show=3)
    )

    return "\n".join(sections)
