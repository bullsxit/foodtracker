from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database.database import db
from database.models import DailyCalories, Food, User, WeightHistory
from database.query_helpers import tid_literal
from utils.keyboards import get_main_menu_keyboard, settings_keyboard
from utils.validators import parse_float, parse_int


class SettingsState:
    CHANGE_PERSONAL_AGE = 1
    CHANGE_PERSONAL_HEIGHT = 2
    CHANGE_ACTIVITY = 3


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.effective_chat.send_message(
        "⚙️ Setări\n\nAlege o opțiune:", reply_markup=settings_keyboard()
    )
    return ConversationHandler.END


async def settings_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog alege o opțiune.")
        return ConversationHandler.END
    text = update.message.text.strip()
    if text == "Resetează profil":
        await reset_profile(update, context)
        return ConversationHandler.END
    if text == "Schimbă datele personale":
        await update.effective_chat.send_message(
            "Introdu noua ta vârstă:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return SettingsState.CHANGE_PERSONAL_AGE
    if text == "Schimbă nivel activitate":
        await update.effective_chat.send_message(
            "Scrie noul tău nivel de activitate (Sedentar, Ușor activ, Moderat activ, Foarte activ):",
            reply_markup=ReplyKeyboardRemove(),
        )
        return SettingsState.CHANGE_ACTIVITY
    return ConversationHandler.END


async def reset_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async for session in db.session():
        telegram_id = update.effective_user.id  # type: ignore[arg-type]
        await session.execute(delete(WeightHistory).where(WeightHistory.telegram_id == tid_literal(telegram_id)))
        await session.execute(delete(Food).where(Food.telegram_id == tid_literal(telegram_id)))
        await session.execute(delete(DailyCalories).where(DailyCalories.telegram_id == tid_literal(telegram_id)))
        await session.execute(delete(User).where(User.telegram_id == tid_literal(telegram_id)))
        await session.commit()
    await update.effective_chat.send_message(
        "Profilul tău a fost resetat complet. Folosește /start pentru a-l configura din nou.",
        reply_markup=get_main_menu_keyboard(),
    )


async def change_personal_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog introdu o vârstă validă.")
        return SettingsState.CHANGE_PERSONAL_AGE
    age = parse_int(update.message.text)
    if age is None or age <= 0 or age > 120:
        await update.effective_chat.send_message("Te rog introdu o vârstă validă.")
        return SettingsState.CHANGE_PERSONAL_AGE
    context.user_data["new_age"] = age
    await update.effective_chat.send_message("Introdu noua ta înălțime în cm:")
    return SettingsState.CHANGE_PERSONAL_HEIGHT


async def change_personal_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog introdu o înălțime validă.")
        return SettingsState.CHANGE_PERSONAL_HEIGHT
    height = parse_int(update.message.text)
    if height is None or height < 100 or height > 250:
        await update.effective_chat.send_message(
            "Te rog introdu o înălțime validă în centimetri."
        )
        return SettingsState.CHANGE_PERSONAL_HEIGHT
    async for session in db.session():
        stmt = select(User).where(User.telegram_id == tid_literal(update.effective_user.id))  # type: ignore[arg-type]
        result = await session.execute(stmt)
        user = result.scalars().first()
        if not user:
            await update.effective_chat.send_message(
                "Nu am găsit profilul tău. Folosește /start pentru a începe."
            )
            return ConversationHandler.END
        user.age = context.user_data.get("new_age", user.age)
        user.height_cm = height
        await session.commit()
    context.user_data.pop("new_age", None)
    await update.effective_chat.send_message(
        "Datele personale au fost actualizate.",
        reply_markup=get_main_menu_keyboard(),
    )
    return ConversationHandler.END


async def change_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog introdu un nivel valid.")
        return SettingsState.CHANGE_ACTIVITY
    level = update.message.text.strip()
    if level not in {"Sedentar", "Ușor activ", "Moderat activ", "Foarte activ"}:
        await update.effective_chat.send_message(
            "Te rog alege un nivel: Sedentar, Ușor activ, Moderat activ, Foarte activ."
        )
        return SettingsState.CHANGE_ACTIVITY
    async for session in db.session():
        stmt = select(User).where(User.telegram_id == tid_literal(update.effective_user.id))  # type: ignore[arg-type]
        result = await session.execute(stmt)
        user = result.scalars().first()
        if not user:
            await update.effective_chat.send_message(
                "Nu am găsit profilul tău. Folosește /start pentru a începe."
            )
            return ConversationHandler.END
        user.activity_level = level
        await session.commit()
    await update.effective_chat.send_message(
        "Nivelul de activitate a fost actualizat.",
        reply_markup=get_main_menu_keyboard(),
    )
    return ConversationHandler.END


def build_settings_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^⚙️ Setări$"), show_settings)],
        states={
            SettingsState.CHANGE_PERSONAL_AGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, change_personal_age)
            ],
            SettingsState.CHANGE_PERSONAL_HEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, change_personal_height)
            ],
            SettingsState.CHANGE_ACTIVITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, change_activity)
            ],
        },
        fallbacks=[
            MessageHandler(
                filters.Regex(
                    "^(Resetează profil|Schimbă datele personale|Schimbă nivel activitate)$"
                ),
                settings_router,
            )
        ],
        allow_reentry=True,
    )

