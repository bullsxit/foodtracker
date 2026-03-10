"""Shared helpers for DB queries. Use tid_literal() so asyncpg binds telegram_id as BIGINT."""

from __future__ import annotations

from sqlalchemy.sql.expression import literal
from sqlalchemy.types import BigInteger


def tid_literal(val: int):
    """Bind telegram_id as BIGINT so asyncpg does not cast to INTEGER (int32)."""
    return literal(val, BigInteger())
