"""
設定管理模組
所有環境變數集中在此，啟動時驗證必要欄位。
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


@dataclass(frozen=True)
class Settings:
    # ── Meta Ads（兩個品牌）──
    meta_user_access_token: str = field(default_factory=lambda: _env("META_USER_ACCESS_TOKEN"))
    meta_ad_account_id_kocskin: str = field(default_factory=lambda: _env("META_AD_ACCOUNT_ID_KOCSKIN"))
    meta_ad_account_id_camping: str = field(default_factory=lambda: _env("META_AD_ACCOUNT_ID_XIAOYAN"))

    # ── Notion ──
    notion_api_token: str = field(default_factory=lambda: _env("NOTION_API_TOKEN"))
    notion_database_id_weekly_report: str = field(default_factory=lambda: _env("NOTION_DATABASE_ID_WEEKLY_REPORT"))
    # 日報專用的兩個資料庫
    notion_db_kocskin_daily_ads: str = field(default_factory=lambda: _env("NOTION_DB_KOCSKIN_DAILY_ADS"))
    notion_db_camping_daily_ads: str = field(default_factory=lambda: _env("NOTION_DB_CAMPING_DAILY_ADS"))

    # ── Telegram ──
    telegram_bot_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN"))
    telegram_chat_id: str = field(default_factory=lambda: _env("TELEGRAM_CHAT_ID"))

    # ── Claude API ──
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))

    # ── 固定值 ──
    meta_api_version: str = "v21.0"

    # ── 週報判斷門檻（v1 規則，weekly 用）──
    threshold_insufficient_spend: float = 300.0
    threshold_insufficient_impressions: int = 1000
    threshold_insufficient_clicks: int = 30
    threshold_scale_spend: float = 1000.0
    threshold_scale_purchases: int = 3
    threshold_scale_roas: float = 4.0
    threshold_scale_frequency: float = 2.5
    threshold_pause_spend: float = 1000.0

    # ── 日報判斷門檻（v1，可調整）──
    # 紅色警示
    daily_red_no_purchase_spend: float = 1500.0    # 單組花費 > 1500 且 0 購買 → 紅
    daily_red_roas_threshold: float = 1.5           # ROAS < 1.5 連 3 天 → 紅
    daily_red_cpa_threshold: float = 1000.0         # CPA > 1000 連 3 天 → 紅（CPA 上限 NT$500 的 2 倍）
    daily_red_account_spend_cap: float = 10000.0   # 帳戶單日花費 > 10000 → 紅（防跑費）
    # 綠色加碼
    daily_green_roas_3day: float = 3.0              # ROAS > 3.0 連 3 天 → 綠
    daily_green_roas_2day: float = 4.0              # ROAS > 4.0 連 2 天 → 綠
    # 黃色觀察
    daily_yellow_roas_low: float = 1.5              # 1.5-2.0 連 2 天
    daily_yellow_roas_high: float = 2.0
    daily_yellow_frequency: float = 4.0             # frequency > 4 → 黃
    daily_yellow_ctr_drop_pct: float = 40.0         # CTR 7 天跌 40%+ → 黃
    # 數據量門檻（避免在量太小時誤判）
    daily_min_spend_for_judgment: float = 200.0    # 單日 spend < 200 不判斷

    def validate_weekly(self, require_ai: bool = True) -> list[str]:
        """驗證週報所需環境變數。"""
        required = {
            "META_USER_ACCESS_TOKEN": self.meta_user_access_token,
            "META_AD_ACCOUNT_ID_KOCSKIN": self.meta_ad_account_id_kocskin,
            "NOTION_API_TOKEN": self.notion_api_token,
            "NOTION_DATABASE_ID_WEEKLY_REPORT": self.notion_database_id_weekly_report,
            "TELEGRAM_BOT_TOKEN": self.telegram_bot_token,
            "TELEGRAM_CHAT_ID": self.telegram_chat_id,
        }
        if require_ai:
            required["ANTHROPIC_API_KEY"] = self.anthropic_api_key

        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")
        return missing

    # 向下相容
    def validate(self, require_ai: bool = True) -> list[str]:
        return self.validate_weekly(require_ai=require_ai)

    def validate_daily(self) -> list[str]:
        """驗證日報所需環境變數。"""
        required = {
            "META_USER_ACCESS_TOKEN": self.meta_user_access_token,
            "META_AD_ACCOUNT_ID_KOCSKIN": self.meta_ad_account_id_kocskin,
            "META_AD_ACCOUNT_ID_XIAOYAN": self.meta_ad_account_id_camping,
            "NOTION_API_TOKEN": self.notion_api_token,
            "NOTION_DB_KOCSKIN_DAILY_ADS": self.notion_db_kocskin_daily_ads,
            "NOTION_DB_CAMPING_DAILY_ADS": self.notion_db_camping_daily_ads,
            "TELEGRAM_BOT_TOKEN": self.telegram_bot_token,
            "TELEGRAM_CHAT_ID": self.telegram_chat_id,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")
        return missing


settings = Settings()
