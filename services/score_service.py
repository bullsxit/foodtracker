from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import DailyCalories, Food, User, WaterIntake, Workout


class ScoreService:
    """Computes the user discipline score (1-100) and consecutive streak."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def compute(self, telegram_id: int) -> dict[str, Any]:
        today = date.today()
        start_7 = today - timedelta(days=6)
        start_week = today - timedelta(days=today.weekday())  # Monday

        # ── Fetch user target calories ─────────────────────────────────────
        user_result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalars().first()
        if not user:
            return {"score": 0, "streak": 0, "breakdown": {}}

        target_cal = user.target_calories or 2000.0
        target_protein_g = (target_cal * 0.30) / 4.0
        target_carbs_g = (target_cal * 0.40) / 4.0
        target_fat_g = (target_cal * 0.30) / 9.0

        # ── Calorie adherence – last 7 days average ────────────────────────
        cal_result = await self._session.execute(
            select(func.avg(DailyCalories.total_calories)).where(
                DailyCalories.telegram_id == telegram_id,
                DailyCalories.date >= start_7,
                DailyCalories.date <= today,
            )
        )
        avg_cal = float(cal_result.scalar_one_or_none() or 0.0)
        if avg_cal > 0 and target_cal > 0:
            ratio = abs(avg_cal - target_cal) / target_cal
            if ratio <= 0.05:
                cal_score = 35
            elif ratio <= 0.10:
                cal_score = 28
            elif ratio <= 0.20:
                cal_score = 20
            elif ratio <= 0.30:
                cal_score = 10
            else:
                cal_score = 0
        else:
            cal_score = 0

        # ── Macro balance – last 7 days totals ────────────────────────────
        macro_result = await self._session.execute(
            select(
                func.coalesce(func.avg(Food.protein), 0),
                func.coalesce(func.avg(Food.carbs), 0),
                func.coalesce(func.avg(Food.fat), 0),
            ).where(
                Food.telegram_id == telegram_id,
                Food.date >= start_7,
                Food.date <= today,
            )
        )
        macro_row = macro_result.one()
        avg_protein = float(macro_row[0])
        avg_carbs = float(macro_row[1])
        avg_fat = float(macro_row[2])

        macro_score = 0
        for actual, target in [
            (avg_protein, target_protein_g),
            (avg_carbs, target_carbs_g),
            (avg_fat, target_fat_g),
        ]:
            if target > 0 and actual > 0:
                ratio = abs(actual - target) / target
                if ratio <= 0.15:
                    macro_score += 7
                elif ratio <= 0.30:
                    macro_score += 3
        # cap at 20
        macro_score = min(20, macro_score)

        # ── Water average – last 7 days ────────────────────────────────────
        water_result = await self._session.execute(
            select(WaterIntake.date, func.sum(WaterIntake.amount_ml))
            .where(
                WaterIntake.telegram_id == telegram_id,
                WaterIntake.date >= start_7,
                WaterIntake.date <= today,
            )
            .group_by(WaterIntake.date)
        )
        water_days = water_result.all()
        if water_days:
            avg_water = sum(float(r[1]) for r in water_days) / len(water_days)
        else:
            avg_water = 0.0
        if avg_water >= 2000:
            water_score = 15
        elif avg_water >= 1500:
            water_score = 10
        elif avg_water >= 1000:
            water_score = 5
        else:
            water_score = 0

        # ── Streak – consecutive disciplined days ──────────────────────────
        streak = await self._compute_streak(telegram_id, today, target_cal)
        # logarithmic: 1 day ≈ 2 pts, 7 days ≈ 10 pts, 30 days = 20 pts
        if streak > 0:
            streak_score = min(20, round(20 * math.log(streak + 1) / math.log(31)))
        else:
            streak_score = 0

        # ── Workouts this week ─────────────────────────────────────────────
        workout_result = await self._session.execute(
            select(func.count(Workout.id)).where(
                Workout.telegram_id == telegram_id,
                Workout.date >= start_week,
                Workout.date <= today,
            )
        )
        workout_count = int(workout_result.scalar_one_or_none() or 0)
        if workout_count >= 5:
            workout_score = 10
        elif workout_count >= 3:
            workout_score = 7
        elif workout_count >= 2:
            workout_score = 5
        elif workout_count >= 1:
            workout_score = 3
        else:
            workout_score = 0

        # ── Total ─────────────────────────────────────────────────────────
        total = cal_score + macro_score + water_score + streak_score + workout_score
        total = max(1, min(100, total))

        return {
            "score": total,
            "streak": streak,
            "breakdown": {
                "calories": cal_score,
                "macros": macro_score,
                "water": water_score,
                "streak": streak_score,
                "workouts": workout_score,
            },
        }

    async def _compute_streak(
        self, telegram_id: int, today: date, target_cal: float
    ) -> int:
        """Count consecutive disciplined days ending today (or yesterday if today has no data)."""
        streak = 0
        check_date = today
        # allow today to be in-progress – only count fully finished days
        # but if today has data, include it
        for _ in range(365):
            disciplined = await self._is_disciplined_day(
                telegram_id, check_date, target_cal
            )
            if disciplined:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break
        return streak

    async def _is_disciplined_day(
        self, telegram_id: int, day: date, target_cal: float
    ) -> bool:
        """A day is disciplined if calories were logged and ≤ 110% of target, and water ≥ 1500ml."""
        # Calories check
        cal_result = await self._session.execute(
            select(DailyCalories.total_calories).where(
                DailyCalories.telegram_id == telegram_id,
                DailyCalories.date == day,
            )
        )
        row = cal_result.scalars().first()
        if row is None:
            return False
        if float(row) > target_cal * 1.10:
            return False

        # Water check
        water_result = await self._session.execute(
            select(func.sum(WaterIntake.amount_ml)).where(
                WaterIntake.telegram_id == telegram_id,
                WaterIntake.date == day,
            )
        )
        water = float(water_result.scalar_one_or_none() or 0.0)
        return water >= 1500
