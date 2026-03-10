#!/usr/bin/env python3
"""
Wipe all app data from the database (Neon PostgreSQL or SQLite).
Use this for a fresh start, e.g. before opening the app to users.

Requires only DATABASE_URL in the environment (or in .env).
Usage:
  DATABASE_URL="postgresql://user:pass@host/db?sslmode=require" python scripts/wipe_database.py
  # Or from project root with .env containing DATABASE_URL:
  python scripts/wipe_database.py

Asks for confirmation unless --yes is passed.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Project root
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# Load .env without requiring TELEGRAM_BOT_TOKEN
try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env")
except ImportError:
    pass

# Build database URL like config does (asyncpg for PostgreSQL)
def _get_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("ERROR: DATABASE_URL is not set. Set it in .env or the environment.")
        sys.exit(1)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "+asyncpg" in url:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        for key in ("sslmode", "channel_binding", "ssl"):
            qs.pop(key, None)
        new_query = urlencode(qs, doseq=True) if qs else ""
        url = urlunparse(parsed._replace(query=new_query))
    return url


async def main() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    url = _get_database_url()
    yes = "--yes" in sys.argv or "-y" in sys.argv

    if not yes:
        print("This will DELETE ALL data in the database (users, meals, water, workouts, etc.).")
        print("Database URL (masked):", url.split("@")[-1] if "@" in url else url[:50] + "...")
        if "sqlite" in url.lower():
            print("WARNING: This looks like SQLite. If your Mini App on Telegram uses Neon (Render), you are about to wipe the WRONG database. Use DATABASE_URL from Render's Environment instead.")
        try:
            answer = input("Type 'yes' to confirm: ").strip().lower()
        except EOFError:
            answer = ""
        if answer != "yes":
            print("Aborted.")
            sys.exit(0)

    connect_args = {}
    if "postgresql+asyncpg" in url:
        connect_args["ssl"] = True

    engine = create_async_engine(url, echo=False, connect_args=connect_args)

    # Tables in dependency-safe order (no FKs between them, but order is harmless)
    tables = [
        "water_intake",
        "workouts",
        "foods",
        "daily_calories",
        "weight_history",
        "users",
    ]

    async with engine.begin() as conn:
        if "postgresql" in url:
            # Single TRUNCATE for PostgreSQL (fast)
            await conn.execute(text("TRUNCATE TABLE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"))
            print("Truncated all tables (PostgreSQL).")
        else:
            # SQLite: DELETE FROM each table
            for table in tables:
                await conn.execute(text(f"DELETE FROM {table}"))
            print("Deleted all rows from all tables (SQLite).")

    await engine.dispose()
    print("Done. Database is empty. You can re-register users from the Mini App.")


if __name__ == "__main__":
    asyncio.run(main())
