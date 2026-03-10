from __future__ import annotations

from enum import IntEnum, auto

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database.database import db
from database.models import User
from services.calorie_calculation_service import (
    CalorieCalculationInput,
    CalorieCalculationService,
)
from utils.keyboards import activity_level_keyboard, goals_keyboard, get_main_menu_keyboard
from utils.validators import parse_float, parse_int


class RegistrationState(IntEnum):
    NAME = auto()
    AGE = auto()
    HEIGHT = auto()
    WEIGHT = auto()
    GENDER = auto()
    GOAL = auto()
    ACTIVITY = auto()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.effective_chat
    async for session in db.session():
        existing = await _get_user(session, update.effective_user.id)  # type: ignore[arg-type]
    if existing:
        await update.effective_chat.send_message(
            "Bun venit înapoi! Alege o opțiune din meniu.",
            reply_markup=get_main_menu_keyboard(),
        )
        return ConversationHandler.END

    await update.effective_chat.send_message(
        "Bun venit la trackerul tău de calorii! Hai să începem cu câteva detalii.\n\n"
        "Cum te numești?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return RegistrationState.NAME


async def registration_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog introdu un nume valid.")
        return RegistrationState.NAME
    context.user_data["name"] = update.message.text.strip()
    await update.effective_chat.send_message("Ce vârstă ai?")
    return RegistrationState.AGE


async def registration_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog introdu un număr valid.")
        return RegistrationState.AGE
    age = parse_int(update.message.text)
    if age is None or age <= 0 or age > 120:
        await update.effective_chat.send_message("Te rog introdu o vârstă validă.")
        return RegistrationState.AGE
    context.user_data["age"] = age
    await update.effective_chat.send_message("Înălțimea ta în cm:")
    return RegistrationState.HEIGHT


async def registration_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog introdu un număr valid.")
        return RegistrationState.HEIGHT
    height = parse_int(update.message.text)
    if height is None or height < 100 or height > 250:
        await update.effective_chat.send_message(
            "Te rog introdu o înălțime validă în centimetri."
        )
        return RegistrationState.HEIGHT
    context.user_data["height_cm"] = height
    await update.effective_chat.send_message("Greutatea ta în kg:")
    return RegistrationState.WEIGHT


async def registration_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog introdu un număr valid.")
        return RegistrationState.WEIGHT
    weight = parse_float(update.message.text)
    if weight is None or weight <= 0 or weight > 400:
        await update.effective_chat.send_message(
            "Te rog introdu o greutate validă în kilograme."
        )
        return RegistrationState.WEIGHT
    context.user_data["weight_kg"] = weight
    await update.effective_chat.send_message(
        "Care este sexul tău biologic? (scrie 'masculin' sau 'feminin')"
    )
    return RegistrationState.GENDER


async def registration_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message(
            "Te rog scrie 'masculin' sau 'feminin'."
        )
        return RegistrationState.GENDER
    gender_text = update.message.text.strip().lower()
    if gender_text not in {"masculin", "feminin"}:
        await update.effective_chat.send_message(
            "Te rog scrie 'masculin' sau 'feminin'."
        )
        return RegistrationState.GENDER
    context.user_data["gender"] = "male" if gender_text == "masculin" else "female"
    await update.effective_chat.send_message(
        "Care este obiectivul tău?",
        reply_markup=goals_keyboard(),
    )
    return RegistrationState.GOAL


async def registration_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog alege un obiectiv din butoane.")
        return RegistrationState.GOAL
    goal = update.message.text.strip()
    if goal not in {"Slăbire", "Menținere", "Creștere"}:
        await update.effective_chat.send_message(
            "Te rog alege un obiectiv folosind butoanele.",
            reply_markup=goals_keyboard(),
        )
        return RegistrationState.GOAL
    context.user_data["goal"] = goal
    await update.effective_chat.send_message(
        "Alege nivelul tău de activitate:",
        reply_markup=activity_level_keyboard(),
    )
    return RegistrationState.ACTIVITY


async def registration_activity(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message(
            "Te rog alege un nivel de activitate din butoane."
        )
        return RegistrationState.ACTIVITY
    activity = update.message.text.strip()
    if activity not in {"Sedentar", "Ușor activ", "Moderat activ", "Foarte activ"}:
        await update.effective_chat.send_message(
            "Te rog alege un nivel de activitate folosind butoanele.",
            reply_markup=activity_level_keyboard(),
        )
        return RegistrationState.ACTIVITY
    context.user_data["activity_level"] = activity

    # Persist user
    async for session in db.session():
        await _create_user_from_context(
            session=session,
            telegram_id=update.effective_user.id,  # type: ignore[arg-type]
            data=context.user_data,
        )
        await session.commit()

    await update.effective_chat.send_message(
        "Profilul tău a fost creat! Poți folosi acum meniul principal.",
        reply_markup=get_main_menu_keyboard(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def _get_user(session: AsyncSession, telegram_id: int) -> User | None:
    stmt = select(User).where(User.telegram_id == str(telegram_id))
    result = await session.execute(stmt)
    return result.scalars().first()


async def _create_user_from_context(
    session: AsyncSession,
    telegram_id: int,
    data: dict,
) -> User:
    calc_service = CalorieCalculationService()
    calc_input = CalorieCalculationInput(
        age=data["age"],
        height_cm=data["height_cm"],
        weight_kg=data["weight_kg"],
        gender=data["gender"],
        activity_level=data["activity_level"],
        goal=data["goal"],
    )
    target_calories = calc_service.calculate_target_calories(calc_input)

    user = User(
        telegram_id=str(telegram_id),
        name=data["name"],
        age=data["age"],
        height_cm=data["height_cm"],
        current_weight=data["weight_kg"],
        start_weight=data["weight_kg"],
        goal=data["goal"],
        activity_level=data["activity_level"],
        gender=data["gender"],
        target_calories=target_calories,
    )
    session.add(user)
    return user


def build_start_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            RegistrationState.NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, registration_name)
            ],
            RegistrationState.AGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, registration_age)
            ],
            RegistrationState.HEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, registration_height)
            ],
            RegistrationState.WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, registration_weight)
            ],
            RegistrationState.GENDER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, registration_gender)
            ],
            RegistrationState.GOAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, registration_goal)
            ],
            RegistrationState.ACTIVITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, registration_activity)
            ],
        },
        fallbacks=[],
    )

