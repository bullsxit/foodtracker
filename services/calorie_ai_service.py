from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import base64
import os

import httpx


@dataclass
class FoodAnalysisResult:
    name: str
    calories: float
    protein: float
    carbs: float
    fat: float


class CalorieAIService:
    """Mockable AI service for food image analysis.

    The implementation is intentionally simple and can later be replaced
    with real HTTP calls to an external API without changing the rest of
    the codebase.
    """

    async def analyze_food_image(self, image_bytes: bytes) -> FoodAnalysisResult:
        """Analyze a food image and return nutritional estimation.

        Behaviour is controlled through environment variables:
        - FOOD_AI_PROVIDER: "mock" (default) or "openai"
        - OPENAI_API_KEY: required when provider is "openai"
        """
        provider = os.getenv("FOOD_AI_PROVIDER", "mock").lower()
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                # Fallback to mock if key is missing
                return self._mock_result()
            try:
                return await self._analyze_with_openai(image_bytes, api_key)
            except Exception:
                # In production you might want to log this properly.
                return self._mock_result()
        # Default: deterministic mock
        return self._mock_result()

    async def _analyze_with_openai(
        self, image_bytes: bytes, api_key: str
    ) -> FoodAnalysisResult:
        """Call OpenAI vision model to estimate nutrition from an image."""
        # Encode image as base64 for the API
        b64_image = base64.b64encode(image_bytes).decode("utf-8")
        prompt = (
            "Analizează această fotografie de mâncare și întoarce un obiect JSON "
            "STRICT cu câmpurile: name (string, denumirea felului), "
            "calories (număr, kcal estimate), protein (număr, grame), "
            "carbs (număr, grame), fat (număr, grame). "
            "Nu adăuga alt text în răspuns, doar JSON-ul."
        )

        payload: dict[str, Any] = {
            "model": os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini"),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64_image}"
                            },
                        },
                    ],
                }
            ],
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(
            timeout=30.0,
        ) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        # We expect pure JSON; if the model wraps it in markdown, strip common wrappers.
        content = content.strip()
        if content.startswith("```"):
            # Remove ```json ... ``` fences if present
            content = content.strip("`")
            # After stripping, try to cut after first newline
            if "\n" in content:
                content = "\n".join(content.split("\n")[1:])

        import json

        parsed = json.loads(content)
        return FoodAnalysisResult(
            name=str(parsed.get("name", "Mâncare detectată")),
            calories=float(parsed.get("calories", 0.0)),
            protein=float(parsed.get("protein", 0.0)),
            carbs=float(parsed.get("carbs", 0.0)),
            fat=float(parsed.get("fat", 0.0)),
        )

    @staticmethod
    def _mock_result() -> FoodAnalysisResult:
        return FoodAnalysisResult(
            name="Mâncare detectată",
            calories=450.0,
            protein=25.0,
            carbs=40.0,
            fat=18.0,
        )


def format_food_analysis(result: FoodAnalysisResult) -> str:
    return (
        "Am detectat:\n\n"
        f"Mâncare: {result.name}\n"
        f"Calorii: {result.calories:.0f} kcal\n\n"
        f"Proteine: {result.protein:.0f} g\n"
        f"Carbohidrați: {result.carbs:.0f} g\n"
        f"Grăsimi: {result.fat:.0f} g"
    )


def serialize_food_analysis(result: FoodAnalysisResult) -> dict[str, Any]:
    return {
        "name": result.name,
        "calories": result.calories,
        "protein": result.protein,
        "carbs": result.carbs,
        "fat": result.fat,
    }

