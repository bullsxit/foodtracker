from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from io import BytesIO
from typing import Sequence

import matplotlib.pyplot as plt
import pandas as pd
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import DailyCalories, WeightHistory
from database.query_helpers import tid_literal


@dataclass
class DailyCaloriesStat:
    day: date
    total_calories: float


class StatisticsService:
    """Service for computing and visualizing calorie statistics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_daily_calories_range(
        self,
        telegram_id: int,
        days: int,
    ) -> list[DailyCaloriesStat]:
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        stmt: Select = (
            select(DailyCalories.date, DailyCalories.total_calories)
            .where(
                DailyCalories.telegram_id == tid_literal(telegram_id),
                DailyCalories.date >= start_date,
                DailyCalories.date <= end_date,
            )
            .order_by(DailyCalories.date)
        )
        result = await self._session.execute(stmt)
        rows: Sequence[tuple[date, float]] = result.all()

        stats = [
            DailyCaloriesStat(day=row[0], total_calories=row[1]) for row in rows
        ]
        return stats

    async def get_average_calories(self, telegram_id: int, days: int) -> float | None:
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        stmt = (
            select(func.avg(DailyCalories.total_calories))
            .where(
                DailyCalories.telegram_id == tid_literal(telegram_id),
                DailyCalories.date >= start_date,
                DailyCalories.date <= end_date,
            )
            .scalar_subquery()
        )
        avg_stmt = select(stmt)
        result = await self._session.execute(avg_stmt)
        avg_value = result.scalar_one_or_none()
        return float(avg_value) if avg_value is not None else None

    async def generate_calories_chart(
        self,
        telegram_id: int,
        days: int,
    ) -> bytes:
        stats = await self.get_daily_calories_range(telegram_id, days)

        if not stats:
            # Generate an empty chart with a message
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, "Nu există date suficiente.", ha="center", va="center")
            ax.axis("off")
        else:
            df = pd.DataFrame(
                {
                    "date": [s.day for s in stats],
                    "calories": [s.total_calories for s in stats],
                }
            )
            fig, ax = plt.subplots()
            ax.plot(df["date"], df["calories"], marker="o")
            ax.set_title(f"Calorii zilnice ultimele {days} zile")
            ax.set_xlabel("Data")
            ax.set_ylabel("Calorii")
            fig.autofmt_xdate()

        buffer = BytesIO()
        plt.tight_layout()
        fig.savefig(buffer, format="png")
        plt.close(fig)
        buffer.seek(0)
        return buffer.read()

    async def get_weight_range(
        self,
        telegram_id: int,
        days: int,
    ) -> list[tuple[date, float]]:
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        stmt: Select = (
            select(WeightHistory.date, WeightHistory.weight)
            .where(
                WeightHistory.telegram_id == tid_literal(telegram_id),
                WeightHistory.date >= start_date,
                WeightHistory.date <= end_date,
            )
            .order_by(WeightHistory.date)
        )
        result = await self._session.execute(stmt)
        return list(result.all())

    async def generate_weight_chart(
        self,
        telegram_id: int,
        days: int,
    ) -> bytes:
        rows = await self.get_weight_range(telegram_id, days)
        if not rows:
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, "Nu există date de greutate.", ha="center", va="center")
            ax.axis("off")
        else:
            df = pd.DataFrame({"date": [r[0] for r in rows], "weight": [r[1] for r in rows]})
            fig, ax = plt.subplots()
            ax.plot(df["date"], df["weight"], marker="o", color="#22c55e")
            ax.set_title(f"Greutate ultimele {days} zile")
            ax.set_xlabel("Data")
            ax.set_ylabel("Greutate (kg)")
            fig.autofmt_xdate()
        buffer = BytesIO()
        plt.tight_layout()
        fig.savefig(buffer, format="png")
        plt.close(fig)
        buffer.seek(0)
        return buffer.read()

