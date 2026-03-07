from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import get_config
from .models import Base


class Database:
    """Database abstraction managing engine and sessions."""

    def __init__(self, database_url: str | None = None) -> None:
        cfg = get_config()
        self._database_url = database_url or cfg.database_url
        self._engine: AsyncEngine = create_async_engine(self._database_url, echo=False)
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    async def init_models(self) -> None:
        """Create all tables if they do not exist."""
        # Ensure the data/ directory exists for SQLite (no-op for PostgreSQL)
        if "sqlite" in self._database_url:
            import os
            os.makedirs("data", exist_ok=True)
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide an async context-managed session."""
        async with self._session_factory() as session:
            yield session


db = Database()

