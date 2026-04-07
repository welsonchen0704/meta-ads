"""
Meta 廣告週報自動產生器 — 主流程
僅拉取 KOCSKIN 廣告數據，不含粉專貼文。
每週一自動執行，或手動觸發。
"""
from __future__ import annotations

import logging
import sys
import os
import traceback
from datetime import datetime

# ── 確保 src/ 目錄在 Python path 中 ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from fetch_ads import fetch_all_ads, MetaTokenError
from analyze_ads import analyze_account, compute_summary
from ai_summary import generate_ai_summary
from build_report import build_markdown_report
from send_to_notion import create_weekly_report_page, create_error_report_page
from send_telegram import (
    send_report_notification,
    send_error_notification,
    send_token_expiry_warning,
)
from generate_pdf import generate_pdf_report
from utils import get_last_week_range

# ── Logging 設定 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("meta_weekly_report")


def main() -> None:
    logger.info("=" * 60)
    logger.info("Meta 廣告週報自動產生器 啟動")
    logger.info("=" * 60)

    try:
        # 1. 驗證環境變數
        settings.validate(require_ai=bool(settings.anthropic_api_key))
        logger.info("環境變數驗證通過")

        # 2. 計算日期範圍
        start_date, end_date = get_last_week_range()
        logger.info(f"報告期間: {start_date} ~ {end_date}")

        # 3. 拉取廣告數據
        logger.info("── 拉取廣告數據 ──")
        raw_ads = fetch_all_ads(start_date, end_date)

        # 4. 分析與分類
        logger.info("── 分析廣告數據 ──")
        all_analyzed: list[dict] = []
        for account_name, rows in raw_ads.items():
            analyzed = analyze_account(rows, account_name)
            all_analyzed.extend(analyzed)

        summary = compute_summary(all_analyzed)
        logger.info(
            f"彙總: 花費 {summary['total_spend']:,.0f}｜"
            f"購買 {summary['total_purchases']:,.0f}｜"
            f"ROAS {summary['weighted_roas']:.2f}"
        )

        # 5. AI 決策摘要（失敗不阻斷）
        logger.info("── 產生 AI 摘要 ──")
        ai_text = generate_ai_summary(summary, start_date, end_date)

        # 6. 產生 Markdown 報告
        logger.info("── 產生報告 ──")
        markdown_report = build_markdown_report(
            summary, ai_text, start_date, end_date
        )

        # 7. 寫入 Notion
        logger.info("── 寫入 Notion ──")
        title = f"Meta 廣告週報 {end_date}"
        notion_url = create_weekly_report_page(
            title, markdown_report, summary, start_date, end_date,
            ai_summary_text=ai_text,
        )

        # 8. 產生 PDF
        logger.info("── 產生 PDF ──")
        pdf_path = generate_pdf_report(
            summary, ai_text, start_date, end_date,
            output_path=f"weekly_report_{end_date}.pdf",
        )

        # 9. 發送 Telegram 通知
        logger.info("── 發送 Telegram 通知 ──")
        send_report_notification(title, summary, notion_url, ai_text)

        # 完成
        logger.info("=" * 60)
        logger.info("週報產生完成！")
        logger.info(f"Notion: {notion_url}")
        logger.info(f"PDF: {pdf_path}")
        logger.info("=" * 60)

        # 輸出報告到 stdout（方便 GitHub Actions 查看）
        print("\n" + markdown_report)

    except MetaTokenError as e:
        logger.error(f"Meta Token 錯誤: {e}")
        send_token_expiry_warning()
        try:
            start_date, end_date = get_last_week_range()
            create_error_report_page(start_date, end_date, f"Token 錯誤: {e}")
        except Exception:
            pass
        sys.exit(1)

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        logger.error(f"執行失敗:\n{error_msg}")
        try:
            send_error_notification(str(e))
            start_date, end_date = get_last_week_range()
            create_error_report_page(start_date, end_date, str(e))
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
