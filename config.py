"""
設定ファイル
環境変数から読み込み
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LINE Bot
    LINE_CHANNEL_SECRET: str = ""
    LINE_CHANNEL_ACCESS_TOKEN: str = ""

    # KIE.AI
    KIEAI_API_KEY: str = ""

    # Database (Google Sheets or SQLite)
    # DATABASE_URL: str = "sqlite:///./users.db" # No longer used

    # Google Sheets
    GOOGLE_SHEETS_ID: str = ""
    GOOGLE_SERVICE_ACCOUNT_KEY: str = "./config/service-account.json"

    # 社内用のため利用制限は設定しない（無制限）
    # FREE_MONTHLY_LIMIT: int = 3
    # PREMIUM_MONTHLY_LIMIT: int = 20

    # 社内用のためStripe決済は不要
    # STRIPE_SECRET_KEY: str = ""
    # STRIPE_PRICE_ID: str = ""
    # STRIPE_PAYMENT_LINK_ID: str = ""
    # STRIPE_WEBHOOK_SECRET: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
