"""
Verilay — Configuration
Loads settings from .env using pydantic-settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Database ──
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/verilay"

    # ── Auth / JWT ──
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # ── OTP Email ──
    OTP_EMAIL: str = "noreply@verilay.in"
    OTP_EMAIL_PASSWORD: str = ""
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587

    # ── News APIs ──
    NEWSDATA_API_KEY: str = ""
    GNEWS_API_KEY: str = ""

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Frontend ──
    FRONTEND_URL: str = "https://verilay.in"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — only reads .env once."""
    return Settings()
