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
    # ── Meta Ads（僅 KOCSKIN）──
    meta_user_access_token: str = field(default_factory=lambda: _env("META_USER_ACCESS_TOKEN"))
    meta_ad_account_id_kocskin: str = field(default_factory=lambda: _env("META_AD_ACCOUNT_ID_KOCSKIN"))

    # ── Notion ──
    notion_api_token: str = field(default_factory=lambda: _env("NOTION_API_TOKEN"))
    notion_database_id_weekly_report: str = field(default_factory=lambda: _env("NOTION_DATABASE_ID_WEEKLY_REPORT"))

    # ── Telegram ──
    telegram_bot_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN"))
    telegram_chat_id: str = field(default_factory=lambda: _env("TELEGRAM_CHAT_ID"))

    # ── Claude API ──
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))

    # ── 固定值 ──
    meta_api_version: str = "v21.0"

    # ── 廣告判斷門檻（v1 規則，可調整）──
    threshold_insufficient_spend: float = 300.0
    threshold_insufficient_impressions: int = 1000
    threshold_insufficient_clicks: int = 30
    threshold_scale_spend: float = 1000.0
    threshold_scale_purchases: int = 3
    threshold_scale_roas: float = 4.0
    threshold_scale_frequency: float = 2.5
    threshold_pause_spend: float = 1000.0

    def validate(self, require_ai: bool = True) -> list[str]:
        """驗證必要環境變數，回傳缺少的變數名稱列表。"""
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


settings = Settings()
