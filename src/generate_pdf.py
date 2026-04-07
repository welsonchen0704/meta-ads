"""
PDF 報告產生模組
使用 reportlab 產生 A4 格式的週報 PDF。
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

logger = logging.getLogger("meta_weekly_report")

# ── 嘗試註冊中文字型 ──
_FONT_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/PingFang.ttc",  # macOS
]
_CJK_FONT = "Helvetica"  # fallback

for path in _FONT_PATHS:
    if os.path.exists(path):
        try:
            pdfmetrics.registerFont(TTFont("NotoSansCJK", path, subfontIndex=0))
            _CJK_FONT = "NotoSansCJK"
            break
        except Exception:
            continue


def _styles() -> dict[str, ParagraphStyle]:
    """建立 PDF 樣式。"""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "CustomTitle",
            parent=base["Title"],
            fontName=_CJK_FONT,
            fontSize=18,
            spaceAfter=12,
        ),
        "heading": ParagraphStyle(
            "CustomHeading",
            parent=base["Heading2"],
            fontName=_CJK_FONT,
            fontSize=14,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "CustomBody",
            parent=base["Normal"],
            fontName=_CJK_FONT,
            fontSize=10,
            leading=14,
        ),
        "small": ParagraphStyle(
            "CustomSmall",
            parent=base["Normal"],
            fontName=_CJK_FONT,
            fontSize=8,
            leading=10,
            textColor=colors.grey,
        ),
    }


def _summary_table(summary: dict[str, Any], styles: dict) -> Table:
    """產生總覽表格。"""
    data = [
        ["指標", "數值"],
        ["總花費", f"{summary['total_spend']:,.0f} 元"],
        ["總購買", f"{summary['total_purchases']:,.0f} 筆"],
        ["總營收", f"{summary['total_purchase_value']:,.0f} 元"],
        ["整體 ROAS", f"{summary['weighted_roas']:.2f}x"],
        ["廣告總數", str(summary["total_ads"])],
    ]

    wrapped = []
    for row in data:
        wrapped.append([Paragraph(cell, styles["body"]) for cell in row])

    table = Table(wrapped, colWidths=[60 * mm, 80 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), _CJK_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
    ]))
    return table


def _ads_table(
    ads: list[dict[str, Any]],
    styles: dict,
    max_rows: int = 10,
) -> Table | None:
    """產生廣告明細表格。"""
    if not ads:
        return None

    header = ["廣告名稱", "帳戶", "花費", "購買", "ROAS", "CPA", "判定"]
    data = [header]

    for ad in ads[:max_rows]:
        ad_name = ad["ad_name"][:25] + "..." if len(ad["ad_name"]) > 25 else ad["ad_name"]
        data.append([
            ad_name,
            ad.get("account", ""),
            f"{ad['spend']:,.0f}",
            f"{ad['purchases']:.0f}",
            f"{ad['roas']:.2f}",
            f"{ad['cpa']:.0f}",
            ad["decision"],
        ])

    wrapped = []
    for row in data:
        wrapped.append([Paragraph(str(cell), styles["small"]) for cell in row])

    col_widths = [45 * mm, 20 * mm, 22 * mm, 16 * mm, 18 * mm, 18 * mm, 22 * mm]
    table = Table(wrapped, colWidths=col_widths)

    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ALIGN", (2, 1), (5, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), _CJK_FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
    ]

    table.setStyle(TableStyle(style_commands))
    return table


def generate_pdf_report(
    summary: dict[str, Any],
    ai_summary_text: str | None,
    start_date: str,
    end_date: str,
    output_path: str = "weekly_report.pdf",
) -> str:
    """產生 PDF 週報，回傳檔案路徑。"""
    styles = _styles()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    story = []

    story.append(Paragraph("Meta 廣告週報", styles["title"]))
    story.append(Paragraph(
        f"報告期間：{start_date} ~ {end_date}　｜　"
        f"產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        styles["small"],
    ))
    story.append(Spacer(1, 10 * mm))

    story.append(Paragraph("總覽", styles["heading"]))
    story.append(_summary_table(summary, styles))
    story.append(Spacer(1, 8 * mm))

    if ai_summary_text:
        story.append(Paragraph("AI 決策摘要", styles["heading"]))
        for line in ai_summary_text.split("\n"):
            if line.strip():
                story.append(Paragraph(line.strip(), styles["body"]))
        story.append(Spacer(1, 8 * mm))

    if summary["scale_candidates"]:
        story.append(Paragraph("🟢 加碼候選", styles["heading"]))
        table = _ads_table(summary["scale_candidates"], styles)
        if table:
            story.append(table)
        story.append(Spacer(1, 6 * mm))

    if summary["pause_candidates"]:
        story.append(Paragraph("🔴 暫停候選", styles["heading"]))
        table = _ads_table(summary["pause_candidates"], styles)
        if table:
            story.append(table)
        story.append(Spacer(1, 6 * mm))

    if summary["watch_list"]:
        story.append(Paragraph("🟡 觀察名單", styles["heading"]))
        table = _ads_table(summary["watch_list"], styles, max_rows=15)
        if table:
            story.append(table)

    doc.build(story)
    logger.info(f"PDF 報告已產生: {output_path}")
    return output_path
