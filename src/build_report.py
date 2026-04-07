"""
Markdown 週報產生模組
完整輸出四個分類 + 彙總 + AI 摘要 + 粉專貼文 insights。
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


def _format_post_row(post: dict[str, Any]) -> str:
    """格式化單篇粉專貼文為 Markdown（含 insights）。"""
    message = str(post.get("message") or "").replace("\n", " ")[:80]
    created = post.get("created_time", "")[:10]
    link = post.get("permalink_url", "")

    # 基本資訊行
    if link:
        line1 = f"- {created}｜[{message}]({link})"
    else:
        line1 = f"- {created}｜{message}"

    # Insights 行
    reach = post.get("reach", 0)
    impressions = post.get("impressions", 0)
    clicks = post.get("clicks", 0)
    engaged = post.get("engaged_users", 0)
    reactions = post.get("reactions", 0)
    comments = post.get("comments_count", 0)
    shares = post.get("shares_count", 0)

    line2 = (
        f"  觸及 {reach:,}｜曝光 {impressions:,}｜"
        f"點擊 {clicks:,}｜互動 {engaged:,}｜"
        f"按讚 {reactions:,}｜留言 {comments:,}｜分享 {shares:,}"
    )

    return f"{line1}\n{line2}"


def build_markdown_report(
    summary: dict[str, Any],
    page_posts: dict[str, list[dict[str, Any]]],
    ai_summary_text: str | None,
    start_date: str,
    end_date: str,
) -> str:
    """產生完整的 Markdown 週報。"""
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

    # ── 粉專貼文（含 insights）──
    sections.append("\n## 粉專近期貼文\n")
    for source_name, posts in page_posts.items():
        sections.append(f"### {source_name}\n")
        if not posts:
            sections.append("無資料\n")
            continue
        for post in posts[:5]:
            sections.append(_format_post_row(post))
        sections.append("")

    return "\n".join(sections)
