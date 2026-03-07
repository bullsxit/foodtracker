from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import WaterIntake


@dataclass
class DailyWaterStat:
    day: date
    amount_ml: float


class WaterService:
    """Service for tracking and aggregating water intake."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_water(self, telegram_id: int, amount_ml: float) -> None:
        entry = WaterIntake(
            telegram_id=telegram_id,
            date=date.today(),
            amount_ml=amount_ml,
        )
        self._session.add(entry)

    async def get_today_total(self, telegram_id: int) -> float:
        stmt = (
            select(func.sum(WaterIntake.amount_ml))
            .where(
                WaterIntake.telegram_id == telegram_id,
                WaterIntake.date == date.today(),
            )
            .scalar_subquery()
        )
        result = await self._session.execute(select(stmt))
        total = result.scalar_one_or_none()
        return float(total) if total is not None else 0.0

    async def get_range(
        self,
        telegram_id: int,
        start_date: date,
        end_date: date,
    ) -> list[DailyWaterStat]:
        stmt: Select = (
            select(WaterIntake.date, func.sum(WaterIntake.amount_ml))
            .where(
                WaterIntake.telegram_id == telegram_id,
                WaterIntake.date >= start_date,
                WaterIntake.date <= end_date,
            )
            .group_by(WaterIntake.date)
            .order_by(WaterIntake.date)
        )
        result = await self._session.execute(stmt)
        rows: Sequence[tuple[date, float]] = result.all()
        return [DailyWaterStat(day=row[0], amount_ml=row[1]) for row in rows]

