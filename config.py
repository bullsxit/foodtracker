from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass
class BotConfig:
    """Configuration for the Telegram bot."""

    bot_token: str
    database_url: str = "sqlite+aiosqlite:///data/database.db"
    # Public HTTPS base URL for webhook mode (empty = local polling)
    webhook_url: str = ""


def get_config() -> BotConfig:
    """Load configuration from environment variables."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Environment variable TELEGRAM_BOT_TOKEN is not set. "
            "Please create a bot in Telegram and set this variable."
        )

    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/database.db")
    # Render and Supabase provide postgres:// or postgresql:// —
    # SQLAlchemy's async engine requires the +asyncpg driver suffix.
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    webhook_url = os.getenv("BOT_WEBHOOK_URL", "").rstrip("/")

    return BotConfig(bot_token=token, database_url=db_url, webhook_url=webhook_url)


