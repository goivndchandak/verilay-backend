"""
Verilay — Configuration
Loads settings from .env using pydantic-settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Database ──
    # Default is local SQLite so the app runs out of the box.
    # In production set DATABASE_URL to your async Postgres DSN, e.g.
    #   postgresql+asyncpg://user:password@host:5432/verilay
    DATABASE_URL: str = "sqlite+aiosqlite:///verilay.db"

    # ── Auth / JWT ──
    # MUST be overridden in production. Generate one with:
    #   python -c "import secrets; print(secrets.token_urlsafe(48))"
    SECRET_KEY: str = "dev-only-insecure-key-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # ── OTP Email ──
    # If OTP_EMAIL_PASSWORD is set, OTPs are emailed via SMTP.
    # If left blank, OTPs are printed to the server console (dev mode).
    OTP_EMAIL: str = "noreply@verilay.co.in"
    OTP_EMAIL_PASSWORD: str = ""
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587

    # ── News APIs (optional — Google News + Reddit work without keys) ──
    NEWSDATA_API_KEY: str = ""
    GNEWS_API_KEY: str = ""

    # ── Reddit OAuth (optional; fixes the 403 from cloud IPs) ──
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = "Verilay/1.0 (reputation monitor)"

    # ── Redis (reserved for future use) ──
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Frontend ──
    FRONTEND_URL: str = "https://verilay.co.in"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — only reads .env once."""
    return Settings()
