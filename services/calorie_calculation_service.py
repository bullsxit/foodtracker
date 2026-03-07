from __future__ import annotations

from dataclasses import dataclass


ActivityLevel = dict[str, float]


ACTIVITY_MULTIPLIERS: ActivityLevel = {
    "Sedentar": 1.2,
    "Ușor activ": 1.375,
    "Moderat activ": 1.55,
    "Foarte activ": 1.725,
}


GOAL_ADJUSTMENTS: dict[str, int] = {
    "Slăbire": -500,
    "Menținere": 0,
    "Creștere": 300,
}


@dataclass
class CalorieCalculationInput:
    age: int
    height_cm: int
    weight_kg: float
    gender: str
    activity_level: str
    goal: str


class CalorieCalculationService:
    """Service responsible for calculating target calories using Mifflin-St Jeor."""

    @staticmethod
    def calculate_bmr(age: int, height_cm: int, weight_kg: float, gender: str) -> float:
        gender = gender.lower()
        if gender == "female":
            return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5

    def calculate_target_calories(self, data: CalorieCalculationInput) -> float:
        bmr = self.calculate_bmr(
            age=data.age,
            height_cm=data.height_cm,
            weight_kg=data.weight_kg,
            gender=data.gender,
        )
        activity_multiplier = ACTIVITY_MULTIPLIERS.get(data.activity_level, 1.2)
        goal_adjustment = GOAL_ADJUSTMENTS.get(data.goal, 0)
        return max(1000.0, bmr * activity_multiplier + goal_adjustment)

