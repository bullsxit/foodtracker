from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Headless server: use non-GUI backend for matplotlib (e.g. Render, Docker).
os.environ.setdefault("MPLBACKEND", "Agg")

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Select, func, select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import literal
from sqlalchemy.types import BigInteger

# Ensure project root is in sys.path so imports from root modules work
# both at runtime (uvicorn runs from root) and in IDE / tests.
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from database.database import db  # noqa: E402
from database.models import (  # noqa: E402
    DailyCalories,
    Food,
    User,
    WeightHistory,
    WaterIntake,
    Workout,
)
from services.water_service import WaterService  # noqa: E402
from services.statistics_service import StatisticsService  # noqa: E402
from services.calorie_ai_service import CalorieAIService, serialize_food_analysis  # noqa: E402
from services.calorie_calculation_service import (  # noqa: E402
    CalorieCalculationService,
    CalorieCalculationInput,
)
from services.score_service import ScoreService  # noqa: E402
from config import get_config  # type: ignore[import-not-found]  # noqa: E402

_logger = logging.getLogger(__name__)


def _tid(val: int):
    """Bind telegram_id as BIGINT so asyncpg does not cast to INTEGER (int32)."""
    return literal(val, BigInteger())


# Telegram Application instance — set during lifespan startup in webhook mode.
_bot_app: Any = None  # type: Any avoids IDE needing telegram SDK installed


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):  # noqa: ARG001
    """FastAPI lifespan: initialise DB and (in production) the Telegram bot webhook."""
    global _bot_app

    # Always initialise database schema
    await db.init_models()

    config = get_config()
    if config.webhook_url:
        # ── Production: webhook mode ──────────────────────────────────────────
        # Lazy imports so the IDE doesn't complain when telegram is not
        # resolvable from the webapp/ subdirectory context.
        from bot import create_application  # type: ignore[import-not-found]  # noqa: PLC0415
        from telegram import Update  # type: ignore[import-untyped]  # noqa: PLC0415
        from telegram import MenuButtonWebApp, WebAppInfo  # type: ignore[import-untyped]  # noqa: PLC0415

        _bot_app = create_application()
        await _bot_app.initialize()
        await _bot_app.start()
        webhook_url = f"{config.webhook_url}/bot-webhook/{config.bot_token}"
        await _bot_app.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
        )
        _logger.info("Telegram webhook set: %s", webhook_url)
        # Set menu button so users can open the Mini App from the bot chat
        mini_app_url = config.webhook_url.rstrip("/") + "/webapp/"
        await _bot_app.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp("Deschide aplicația", WebAppInfo(url=mini_app_url)),
        )
        _logger.info("Telegram menu button set to Mini App: %s", mini_app_url)
    else:
        # ── Local dev: polling handled by main.py ─────────────────────────────
        _logger.info("BOT_WEBHOOK_URL not set – webhook mode off (use main.py for polling)")

    yield  # ── app running ───────────────────────────────────────────────────

    if _bot_app is not None:
        if config.webhook_url:
            await _bot_app.bot.delete_webhook()
        await _bot_app.stop()
        await _bot_app.shutdown()
        _logger.info("Telegram bot shut down cleanly")


app = FastAPI(title="FoodTracker WebApp API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_webapp(request: Request, call_next):
    """Prevent Mini App static files from being cached so each user gets fresh JS."""
    response = await call_next(request)
    if request.url.path.rstrip("/").startswith("/webapp"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response


# Serve static front-end files for the mini app
static_dir = Path(__file__).parent / "static"
app.mount(
    "/webapp",
    StaticFiles(directory=str(static_dir), html=True),
    name="webapp",
)


# ── Telegram Webhook (production) ─────────────────────────────────────────────

@app.post("/bot-webhook/{token}")
async def telegram_webhook(token: str, request: Request) -> dict[str, str]:
    """Receive Telegram update pushes in webhook mode."""
    config = get_config()
    if token != config.bot_token:
        raise HTTPException(status_code=403, detail="Forbidden")
    if _bot_app is None:
        raise HTTPException(status_code=503, detail="Bot not initialised")
    from telegram import Update  # type: ignore[import-untyped]  # noqa: PLC0415
    data = await request.json()
    update = Update.de_json(data, _bot_app.bot)
    await _bot_app.process_update(update)
    return {"ok": "true"}


async def get_session() -> AsyncSession:
    try:
        async for session in db.session():
            yield session
    except Exception as e:
        _logger.exception("get_session failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail="Serviciu ocupat. Încearcă din nou în câteva secunde.",
        )


def _serialize_user(user: User) -> dict[str, Any]:
    return {
        "telegram_id": user.telegram_id,
        "name": user.name,
        "age": user.age,
        "height_cm": user.height_cm,
        "current_weight": user.current_weight,
        "start_weight": user.start_weight,
        "goal": user.goal,
        "activity_level": user.activity_level,
        "target_calories": user.target_calories,
    }


def _recalculate_target_calories(user: User) -> float:
    """Recalculate target calories based on current profile data."""
    service = CalorieCalculationService()
    calc_input = CalorieCalculationInput(
        age=user.age,
        height_cm=user.height_cm,
        weight_kg=user.current_weight,
        gender=user.gender,
        activity_level=user.activity_level,
        goal=user.goal,
    )
    return service.calculate_target_calories(calc_input)


@app.get("/api/dashboard/{telegram_id}")
async def get_dashboard(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        user_stmt: Select = select(User).where(User.telegram_id == _tid(telegram_id))
        user_result = await session.execute(user_stmt)
        user = user_result.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not (user.name and user.name.strip()):
            await session.execute(delete(User).where(User.telegram_id == _tid(telegram_id)))
            await session.commit()
            raise HTTPException(status_code=404, detail="User not found")

        today = date.today()
        calories_stmt: Select = select(DailyCalories).where(
            DailyCalories.telegram_id == _tid(telegram_id),
            DailyCalories.date == today,
        )
        calories_result = await session.execute(calories_stmt)
        daily = calories_result.scalars().first()
        consumed = daily.total_calories if daily else 0.0

        weight_today_stmt: Select = select(WeightHistory).where(
            WeightHistory.telegram_id == _tid(telegram_id),
            WeightHistory.date == today,
        )
        weight_today_result = await session.execute(weight_today_stmt)
        weight_logged_today = weight_today_result.scalars().first() is not None

        macros_stmt: Select = select(
            func.coalesce(func.sum(Food.protein), 0),
            func.coalesce(func.sum(Food.carbs), 0),
            func.coalesce(func.sum(Food.fat), 0),
        ).where(
            Food.telegram_id == _tid(telegram_id),
            Food.date == today,
        )
        macros_result = await session.execute(macros_stmt)
        row = macros_result.one()
        consumed_protein = float(row[0])
        consumed_carbs = float(row[1])
        consumed_fat = float(row[2])

        target = user.target_calories or 2000.0
        target_protein_g = (target * 0.30) / 4.0
        target_carbs_g = (target * 0.40) / 4.0
        target_fat_g = (target * 0.30) / 9.0

        water_service = WaterService(session)
        water_today = await water_service.get_today_total(telegram_id)

        payload = {
            "user": _serialize_user(user),
            "today": str(today),
            "calories_today": consumed,
            "water_today_ml": water_today,
            "weight_logged_today": weight_logged_today,
            "consumed_protein": consumed_protein,
            "consumed_carbs": consumed_carbs,
            "consumed_fat": consumed_fat,
            "target_protein_g": target_protein_g,
            "target_carbs_g": target_carbs_g,
            "target_fat_g": target_fat_g,
        }
        return JSONResponse(
            content=payload,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )
    except HTTPException:
        raise
    except Exception as e:
        _logger.exception("Dashboard error for telegram_id=%s: %s", telegram_id, e)
        raise HTTPException(status_code=404, detail="User not found")


@app.post("/api/register")
async def register(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Create a new user profile (onboarding from mini app)."""
    try:
        body = await request.form()
    except Exception as e:
        _logger.warning("Register form read failed: %s", e)
        raise HTTPException(status_code=400, detail="Date invalide. Încearcă din nou.")

    def _get(name: str, default: str = "") -> str:
        v = body.get(name)
        if v is None:
            return default
        if isinstance(v, str):
            return v
        if isinstance(v, (list, tuple)) and v:
            return str(v[0]) if v[0] is not None else default
        return str(v) if v is not None else default

    try:
        telegram_id = int(_get("telegram_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="ID invalid. Deschide aplicația din Menu-ul botului.")
    name = (_get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Numele este obligatoriu.")
    try:
        age = int(_get("age") or "0")
        height_cm = int(_get("height_cm") or "0")
        w_str = (_get("weight_kg") or "0").replace(",", ".")
        weight_kg = float(w_str)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Vârstă, înălțime sau greutate invalide.")
    if age < 1 or age > 120:
        raise HTTPException(status_code=400, detail="Vârsta trebuie să fie între 1 și 120.")
    if height_cm < 100 or height_cm > 250:
        raise HTTPException(status_code=400, detail="Înălțimea trebuie să fie între 100 și 250 cm.")
    if weight_kg < 1 or weight_kg > 400:
        raise HTTPException(status_code=400, detail="Greutatea trebuie să fie între 1 și 400 kg.")

    gender = (_get("gender") or "").strip().lower()
    if gender not in ("male", "female"):
        raise HTTPException(status_code=400, detail="Alege sexul biologic.")
    goal = (_get("goal") or "").strip()
    if goal not in ("Slăbire", "Menținere", "Creștere"):
        raise HTTPException(status_code=400, detail="Alege obiectivul.")
    activity_level = (_get("activity_level") or "").strip()
    if activity_level not in ("Sedentar", "Ușor activ", "Moderat activ", "Foarte activ"):
        raise HTTPException(status_code=400, detail="Alege nivelul de activitate.")

    try:
        stmt: Select = select(User).where(User.telegram_id == _tid(telegram_id))
        result = await session.execute(stmt)
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="Contul există deja. Deschide aplicația din Menu – ar trebui să vezi panoul.")

        calc = CalorieCalculationService()
        inp = CalorieCalculationInput(
            age=age,
            height_cm=height_cm,
            weight_kg=weight_kg,
            gender=gender,
            activity_level=activity_level,
            goal=goal,
        )
        target = calc.calculate_target_calories(inp)
        user = User(
            telegram_id=telegram_id,
            name=name,
            age=age,
            height_cm=height_cm,
            current_weight=weight_kg,
            start_weight=weight_kg,
            goal=goal,
            activity_level=activity_level,
            target_calories=target,
            gender=gender,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return {"user": _serialize_user(user)}
    except HTTPException:
        raise
    except IntegrityError as e:
        await session.rollback()
        _logger.warning("Register IntegrityError telegram_id=%s: %s", telegram_id, e)
        raise HTTPException(status_code=400, detail="Contul există deja. Deschide aplicația din Menu.")
    except Exception as e:
        await session.rollback()
        _logger.exception("Register failed telegram_id=%s: %s", telegram_id, e)
        raise HTTPException(
            status_code=400,
            detail="Nu am putut crea profilul. Încearcă din nou sau deschide aplicația din Menu-ul botului.",
        )


@app.post("/api/water/{telegram_id}/add")
async def add_water(
    telegram_id: int,
    amount_ml: float,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    water_service = WaterService(session)
    await water_service.add_water(telegram_id, amount_ml)
    await session.commit()
    total = await water_service.get_today_total(telegram_id)
    return {"water_today_ml": total}


@app.get("/api/meals/{telegram_id}/{for_date}")
async def meals_for_date(
    telegram_id: int,
    for_date: date,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    stmt: Select = (
        select(Food)
        .where(
            Food.telegram_id == _tid(telegram_id),
            Food.date == for_date,
        )
        .order_by(Food.id)
    )
    result = await session.execute(stmt)
    foods = result.scalars().all()
    total = sum(f.calories for f in foods)
    items = [
        {
            "id": f.id,
            "name": f.food_name,
            "calories": f.calories,
            "protein": f.protein,
            "carbs": f.carbs,
            "fat": f.fat,
            "meal_type": f.meal_type,
            "date": str(f.date),
        }
        for f in foods
    ]
    return {
        "date": str(for_date),
        "total_calories": total,
        "items": items,
    }


async def _save_food_and_update_daily(
    session: AsyncSession,
    telegram_id: int,
    name: str,
    calories: float,
    protein: float | None,
    carbs: float | None,
    fat: float | None,
    meal_type: str | None,
    entry_date: date,
) -> None:
    calories_safe = _clamp_calories(calories, 15000.0)
    food = Food(
        telegram_id=telegram_id,
        food_name=name,
        calories=calories_safe,
        protein=protein,
        carbs=carbs,
        fat=fat,
        meal_type=meal_type,
        date=entry_date,
    )
    session.add(food)

    stmt: Select = select(DailyCalories).where(
        DailyCalories.telegram_id == _tid(telegram_id),
        DailyCalories.date == entry_date,
    )
    result = await session.execute(stmt)
    daily = result.scalars().first()
    if not daily:
        daily = DailyCalories(
            telegram_id=telegram_id,
            date=entry_date,
            total_calories=calories_safe,
        )
        session.add(daily)
    else:
        daily.total_calories = _clamp_calories(
            daily.total_calories + calories_safe, 50000.0
        )


def _clamp_calories(value: float, max_val: float = 15000.0) -> float:
    """Ensure calorie values are in a reasonable range for display and storage."""
    if value is None or value < 0:
        return 0.0
    return min(float(value), max_val)


@app.post("/api/meals/{telegram_id}/add_manual")
async def add_manual_meal(
    telegram_id: int,
    name: str = Form(...),
    calories: float = Form(...),
    protein: float | None = Form(None),
    carbs: float | None = Form(None),
    fat: float | None = Form(None),
    meal_type: str = Form("Neclasificat"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if calories < 0 or calories > 15000:
        raise HTTPException(
            status_code=400,
            detail="Caloriile trebuie să fie între 0 și 15000.",
        )
    calories = _clamp_calories(calories, 15000.0)
    await _save_food_and_update_daily(
        session=session,
        telegram_id=telegram_id,
        name=name,
        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat,
        meal_type=meal_type,
        entry_date=date.today(),
    )
    await session.commit()
    return {"status": "ok"}


@app.post("/api/meals/{telegram_id}/analyze_image")
async def analyze_meal_image(
    telegram_id: int,  # unused, dar păstrat pentru consistență și audit
    file: UploadFile = File(...),
    meal_type: str = Form("Neclasificat"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    _ = session  # not used yet, dar păstrăm semnătura pentru extensii viitoare
    image_bytes = await file.read()
    ai_service = CalorieAIService()
    result = await ai_service.analyze_food_image(image_bytes)
    payload = serialize_food_analysis(result)
    payload["meal_type"] = meal_type
    return {"analysis": payload}


@app.post("/api/user/{telegram_id}/log_weight")
async def log_weight(
    telegram_id: int,
    weight: float = Form(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    user_stmt: Select = select(User).where(User.telegram_id == _tid(telegram_id))
    user_result = await session.execute(user_stmt)
    user = user_result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.current_weight = weight
    history = WeightHistory(
        telegram_id=telegram_id,
        weight=weight,
        date=date.today(),
    )
    session.add(history)
    # Recalculate target calories when weight changes
    user.target_calories = _recalculate_target_calories(user)
    await session.commit()
    return {
        "user": _serialize_user(user),
    }


@app.post("/api/user/{telegram_id}/update_personal")
async def update_personal(
    telegram_id: int,
    age: int = Form(...),
    height_cm: int = Form(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    stmt: Select = select(User).where(User.telegram_id == _tid(telegram_id))
    result = await session.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.age = age
    user.height_cm = height_cm
    user.target_calories = _recalculate_target_calories(user)
    await session.commit()
    return {"user": _serialize_user(user)}


@app.post("/api/user/{telegram_id}/update_goal")
async def update_goal(
    telegram_id: int,
    goal: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if goal not in {"Slăbire", "Menținere", "Creștere"}:
        raise HTTPException(status_code=400, detail="Goal invalid")
    stmt: Select = select(User).where(User.telegram_id == _tid(telegram_id))
    result = await session.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.goal = goal
    user.target_calories = _recalculate_target_calories(user)
    await session.commit()
    return {"user": _serialize_user(user)}


@app.post("/api/user/{telegram_id}/update_activity")
async def update_activity(
    telegram_id: int,
    activity_level: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if activity_level not in {
        "Sedentar",
        "Ușor activ",
        "Moderat activ",
        "Foarte activ",
    }:
        raise HTTPException(status_code=400, detail="Nivel de activitate invalid")
    stmt: Select = select(User).where(User.telegram_id == _tid(telegram_id))
    result = await session.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.activity_level = activity_level
    user.target_calories = _recalculate_target_calories(user)
    await session.commit()
    return {"user": _serialize_user(user)}


@app.post("/api/user/{telegram_id}/reset")
async def reset_profile_api(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Delete all data for this user from the database."""
    try:
        await session.execute(
            delete(WeightHistory).where(WeightHistory.telegram_id == _tid(telegram_id))
        )
        await session.execute(
            delete(Food).where(Food.telegram_id == _tid(telegram_id))
        )
        await session.execute(
            delete(DailyCalories).where(
                DailyCalories.telegram_id == _tid(telegram_id)
            )
        )
        await session.execute(
            delete(WaterIntake).where(WaterIntake.telegram_id == _tid(telegram_id))
        )
        await session.execute(
            delete(User).where(User.telegram_id == _tid(telegram_id))
        )
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"status": "reset"}


@app.get("/api/stats/{telegram_id}")
async def get_stats(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    today = date.today()
    start_7 = today - timedelta(days=6)
    start_30 = today - timedelta(days=29)

    # Calories
    def calories_stmt(start: date, end: date) -> Select:
        return (
            select(DailyCalories.date, DailyCalories.total_calories)
            .where(
                DailyCalories.telegram_id == _tid(telegram_id),
                DailyCalories.date >= start,
                DailyCalories.date <= end,
            )
            .order_by(DailyCalories.date)
        )

    result_7 = await session.execute(calories_stmt(start_7, today))
    cal_7 = [
        {"date": str(row[0]), "calories": _clamp_calories(float(row[1]))}
        for row in result_7.all()
    ]
    result_30 = await session.execute(calories_stmt(start_30, today))
    cal_30 = [
        {"date": str(row[0]), "calories": _clamp_calories(float(row[1]))}
        for row in result_30.all()
    ]

    # Weight
    weight_stmt: Select = (
        select(WeightHistory.date, WeightHistory.weight)
        .where(
            WeightHistory.telegram_id == _tid(telegram_id),
            WeightHistory.date >= start_30,
            WeightHistory.date <= today,
        )
        .order_by(WeightHistory.date)
    )
    weight_result = await session.execute(weight_stmt)
    weights = [
        {"date": str(row[0]), "weight": float(row[1])} for row in weight_result.all()
    ]

    # Water
    water_service = WaterService(session)
    water_range = await water_service.get_range(telegram_id, start_30, today)
    water = [
        {"date": str(s.day), "water_ml": float(s.amount_ml)} for s in water_range
    ]

    # Average calories (capped to avoid absurd values from bad data)
    avg_cal_7_stmt = (
        select(func.avg(DailyCalories.total_calories))
        .where(
            DailyCalories.telegram_id == _tid(telegram_id),
            DailyCalories.date >= start_7,
            DailyCalories.date <= today,
        )
        .scalar_subquery()
    )
    avg_result = await session.execute(select(avg_cal_7_stmt))
    avg_7 = avg_result.scalar_one_or_none()
    avg_7_safe = None
    if avg_7 is not None:
        avg_7_safe = _clamp_calories(float(avg_7))

    user_stmt: Select = select(User).where(User.telegram_id == _tid(telegram_id))
    user_result = await session.execute(user_stmt)
    user = user_result.scalars().first()
    target_cal = user.target_calories if user else 2000.0
    target_protein_g = (target_cal * 0.30) / 4.0
    target_carbs_g = (target_cal * 0.40) / 4.0
    target_fat_g = (target_cal * 0.30) / 9.0

    macro_stmt: Select = select(
        func.coalesce(func.sum(Food.protein), 0),
        func.coalesce(func.sum(Food.carbs), 0),
        func.coalesce(func.sum(Food.fat), 0),
    ).where(
        Food.telegram_id == _tid(telegram_id),
        Food.date >= start_7,
        Food.date <= today,
    )
    macro_result = await session.execute(macro_stmt)
    macro_row = macro_result.one()
    total_p = float(macro_row[0])
    total_c = float(macro_row[1])
    total_f = float(macro_row[2])
    days_with_food = max(1, len(cal_7))
    macro_avg_7d = {
        "protein": total_p / days_with_food,
        "carbs": total_c / days_with_food,
        "fat": total_f / days_with_food,
    }
    target_macros = {
        "protein": target_protein_g,
        "carbs": target_carbs_g,
        "fat": target_fat_g,
    }

    suggestions: list[str] = []
    if macro_avg_7d["protein"] < target_protein_g * 0.8:
        suggestions.append("Mănâncă mai multe proteine.")
    if macro_avg_7d["protein"] > target_protein_g * 1.25:
        suggestions.append("Ai consumat multe proteine – poți reduce ușor.")
    if macro_avg_7d["carbs"] < target_carbs_g * 0.8:
        suggestions.append("Adaugă mai mulți carbohidrați (cereale, fructe).")
    if macro_avg_7d["carbs"] > target_carbs_g * 1.25:
        suggestions.append("Mai puțini carbohidrați în ultimele zile.")
    if macro_avg_7d["fat"] < target_fat_g * 0.8:
        suggestions.append("Adaugă grăsimi sănătoase (nuci, avocado, ulei).")
    if macro_avg_7d["fat"] > target_fat_g * 1.2:
        suggestions.append("Încearcă să reduci grăsimile.")
    if not suggestions:
        suggestions.append("Macronutrienții tăi sunt echilibrați. Continuă așa!")

    return {
        "calories_7_days": cal_7,
        "calories_30_days": cal_30,
        "weights_30_days": weights,
        "water_30_days": water,
        "average_calories_7_days": avg_7_safe,
        "macro_avg_7d": macro_avg_7d,
        "target_macros": target_macros,
        "suggestions": suggestions,
    }


@app.get("/api/chart/weight/{telegram_id}", response_class=Response)
async def chart_weight(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> Response:
    stats_service = StatisticsService(session)
    img_bytes = await stats_service.generate_weight_chart(telegram_id, 30)
    return Response(content=img_bytes, media_type="image/png")


@app.get("/api/chart/calories/{telegram_id}", response_class=Response)
async def chart_calories(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> Response:
    stats_service = StatisticsService(session)
    img_bytes = await stats_service.generate_calories_chart(telegram_id, 30)
    return Response(content=img_bytes, media_type="image/png")


@app.get("/api/user/{telegram_id}")
async def get_user(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    stmt: Select = select(User).where(User.telegram_id == _tid(telegram_id))
    result = await session.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _serialize_user(user)


# ── Day summary (history tab) ─────────────────────────────────────────────────

@app.get("/api/day/{telegram_id}/{for_date}")
async def get_day_summary(
    telegram_id: int,
    for_date: date,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Return a full day summary: meals, macros, water, weight, workouts."""

    # Meals
    foods_result = await session.execute(
        select(Food)
        .where(Food.telegram_id == _tid(telegram_id), Food.date == for_date)
        .order_by(Food.id)
    )
    foods = foods_result.scalars().all()
    total_calories = sum(f.calories for f in foods)
    total_protein  = sum(f.protein or 0.0 for f in foods)
    total_carbs    = sum(f.carbs or 0.0 for f in foods)
    total_fat      = sum(f.fat or 0.0 for f in foods)

    # Group meals by meal_type
    groups: dict[str, list[dict[str, Any]]] = {}
    for f in foods:
        key = f.meal_type or "Neclasificat"
        groups.setdefault(key, []).append({
            "id": f.id,
            "name": f.food_name,
            "calories": f.calories,
            "protein": f.protein,
            "carbs": f.carbs,
            "fat": f.fat,
        })
    meal_groups = [{"meal_type": k, "items": v} for k, v in groups.items()]

    # Water
    water_result = await session.execute(
        select(func.sum(WaterIntake.amount_ml)).where(
            WaterIntake.telegram_id == _tid(telegram_id),
            WaterIntake.date == for_date,
        )
    )
    water_ml = float(water_result.scalar_one_or_none() or 0.0)

    # Weight logged that day
    weight_result = await session.execute(
        select(WeightHistory.weight).where(
            WeightHistory.telegram_id == _tid(telegram_id),
            WeightHistory.date == for_date,
        ).order_by(WeightHistory.id.desc())
    )
    weight_row = weight_result.scalars().first()
    weight_kg = float(weight_row) if weight_row is not None else None

    # Workouts
    workouts_result = await session.execute(
        select(Workout)
        .where(Workout.telegram_id == _tid(telegram_id), Workout.date == for_date)
        .order_by(Workout.id)
    )
    workouts = workouts_result.scalars().all()
    workout_items = [
        {"name": w.name, "calories_burned": w.calories_burned, "duration_min": w.duration_min}
        for w in workouts
    ]
    total_burned = sum(w.calories_burned for w in workouts)

    return {
        "date": str(for_date),
        "total_calories": total_calories,
        "total_protein": total_protein,
        "total_carbs": total_carbs,
        "total_fat": total_fat,
        "water_ml": water_ml,
        "weight_kg": weight_kg,
        "total_burned": total_burned,
        "meal_groups": meal_groups,
        "workouts": workout_items,
    }


# ── Score & Streak ─────────────────────────────────────────────────────────────


@app.get("/api/score/{telegram_id}")
async def get_score(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    svc = ScoreService(session)
    return await svc.compute(telegram_id)


# ── Leaderboard ────────────────────────────────────────────────────────────────

@app.get("/api/leaderboard")
async def get_leaderboard(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Return all users ranked by score (desc), streak (desc) as tiebreaker."""
    users_result = await session.execute(select(User).order_by(User.name))
    users = users_result.scalars().all()

    entries = []
    for user in users:
        svc = ScoreService(session)
        data = await svc.compute(user.telegram_id)
        entries.append(
            {
                "telegram_id": user.telegram_id,
                "name": user.name,
                "score": data["score"],
                "streak": data["streak"],
                "goal": user.goal,
            }
        )

    # Sort by score desc, then streak desc
    entries.sort(key=lambda e: (-e["score"], -e["streak"]))

    # Assign rank (ties share same rank)
    ranked = []
    for idx, entry in enumerate(entries):
        rank = idx + 1
        if idx > 0 and entry["score"] == entries[idx - 1]["score"] and entry["streak"] == entries[idx - 1]["streak"]:
            rank = ranked[-1]["rank"]
        ranked.append({**entry, "rank": rank})

    return {"leaderboard": ranked}


# ── Workouts ───────────────────────────────────────────────────────────────────

@app.post("/api/workout/{telegram_id}/add")
async def add_workout(
    telegram_id: int,
    name: str = Form(...),
    calories_burned: float = Form(...),
    duration_min: int | None = Form(None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if calories_burned < 0 or calories_burned > 5000:
        raise HTTPException(status_code=400, detail="Calorii arse invalide (0-5000).")
    workout = Workout(
        telegram_id=telegram_id,
        name=name.strip(),
        calories_burned=calories_burned,
        duration_min=duration_min,
        date=date.today(),
    )
    session.add(workout)
    await session.commit()
    return {"status": "ok"}


@app.get("/api/workout/{telegram_id}/week")
async def get_week_workouts(
    telegram_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    today = date.today()
    start_week = today - timedelta(days=today.weekday())  # Monday
    result = await session.execute(
        select(Workout)
        .where(
            Workout.telegram_id == _tid(telegram_id),
            Workout.date >= start_week,
            Workout.date <= today,
        )
        .order_by(Workout.date.desc(), Workout.id.desc())
    )
    workouts = result.scalars().all()
    total_burned = sum(w.calories_burned for w in workouts)
    items = [
        {
            "id": w.id,
            "name": w.name,
            "calories_burned": w.calories_burned,
            "duration_min": w.duration_min,
            "date": str(w.date),
        }
        for w in workouts
    ]
    return {
        "count": len(items),
        "total_calories_burned": total_burned,
        "items": items,
    }


