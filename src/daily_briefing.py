"""
Meta 廣告每日早報 — 主程式
每天 09:00 (UTC+8) 由 GitHub Actions 觸發

流程：
  1. 抓兩個品牌（KOCSKIN, 露營瘋）的廣告數據（昨日 / 過去 3 天 / 過去 7 天）
  2. 套用判斷規則（A1-A4 紅色 / C1-C2 綠色 / B1-B3 黃色）
  3. 寫入 Notion 廣告每日數據資料庫
  4. 透過 Telegram 推送早報

每個品牌獨立跑，互不影響。
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from fetch_daily_ads import fetch_all_accounts_daily, MetaTokenError
from daily_rules import evaluate_account
from notion_daily_writer import write_daily_record
from send_telegram import (
    send_daily_briefing,
    send_error_notification,
    send_token_expiry_warning,
    get_daily_briefing_text,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("daily_briefing")


# 品牌 → Notion DB ID 的對應
BRAND_TO_DB = {
    "KOCSKIN": settings.notion_db_kocskin_daily_ads,
    "露營瘋": settings.notion_db_camping_daily_ads,
}


def main() -> None:
    logger.info("=" * 60)
    logger.info("Meta 廣告每日早報 啟動")
    logger.info("=" * 60)

    try:
        # 1. 驗證環境變數
        settings.validate_daily()
        logger.info("環境變數驗證通過")

        # 2. 抓取兩個品牌的廣告數據
        logger.info("── 拉取廣告數據 ──")
        all_data = fetch_all_accounts_daily()

        # 3. 對每個品牌獨立跑判斷與通知
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        for brand, periods in all_data.items():
            logger.info(f"── 處理 {brand} ──")
            try:
                # 判斷規則
                eval_result = evaluate_account(periods)
                summary = eval_result["yesterday_summary"]

                logger.info(
                    f"  彙總：花費 NT${summary['spend']:,.0f}｜"
                    f"購買 {summary['purchases']}｜"
                    f"ROAS {summary['roas']:.2f}｜"
                    f"廣告組 {summary['ad_count']}"
                )
                logger.info(
                    f"  警示：紅 {len(eval_result['alerts_red'])}｜"
                    f"綠 {len(eval_result['alerts_green'])}｜"
                    f"黃 {len(eval_result['alerts_yellow'])}"
                )

                # 寫入 Notion
                db_id = BRAND_TO_DB.get(brand)
                if not db_id:
                    logger.warning(f"  {brand} 沒有對應的 Notion DB，跳過寫入")
                    notion_url = ""
                else:
                    briefing_text = get_daily_briefing_text(brand, eval_result)
                    page_id = write_daily_record(
                        database_id=db_id,
                        date_str=yesterday_str,
                        summary=summary,
                        alerts=eval_result,
                        briefing_text=briefing_text,
                    )
                    notion_url = f"https://www.notion.so/{db_id.replace('-', '')}"

                # Telegram 通知
                send_daily_briefing(brand, eval_result, notion_url)

            except Exception as e:
                logger.error(f"  ✗ {brand} 處理失敗：{e}")
                logger.error(traceback.format_exc())

        logger.info("=" * 60)
        logger.info("每日早報執行完成")
        logger.info("=" * 60)

    except MetaTokenError as e:
        logger.error(f"Meta Token 錯誤：{e}")
        send_token_expiry_warning()
        sys.exit(1)

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        logger.error(f"執行失敗：\n{error_msg}")
        try:
            send_error_notification(str(e))
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
