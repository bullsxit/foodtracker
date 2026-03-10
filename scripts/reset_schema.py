#!/usr/bin/env python3
"""
Drop all app tables and recreate them with the current schema (e.g. user_id + telegram_id string).
Use this when migrating from the old schema (telegram_id as integer) to the new one.

Requires DATABASE_URL in the environment or in .env.
Usage:
  python scripts/reset_schema.py
  python scripts/reset_schema.py --yes   # skip confirmation

After running, redeploy the app on Render so it starts with the new empty tables.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env")
except ImportError:
    pass


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
    from sqlalchemy.ext.asyncio import create_async_engine

    from database.models import Base

    url = _get_database_url()
    yes = "--yes" in sys.argv or "-y" in sys.argv

    if not yes:
        print("This will DROP all app tables and recreate them (current schema). ALL DATA WILL BE LOST.")
        print("Database (masked):", url.split("@")[-1] if "@" in url else url[:50] + "...")
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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        print("Dropped all tables.")
        await conn.run_sync(Base.metadata.create_all)
        print("Created all tables with current schema.")

    await engine.dispose()
    print("Done. Redeploy the app on Render (or restart locally) so it uses the new schema.")


if __name__ == "__main__":
    asyncio.run(main())
