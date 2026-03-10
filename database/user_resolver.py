"""Resolve Telegram ID (any size) to internal user_id (small integer). At Python level only."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User


async def get_user_id(session: AsyncSession, telegram_id: int) -> int | None:
    """Return users.id for the user with this telegram_id, or None. Uses string comparison."""
    stmt = select(User.id).where(User.telegram_id == str(telegram_id))
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return int(row) if row is not None else None


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Return User by internal id."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalars().first()
