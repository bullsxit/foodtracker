from __future__ import annotations

from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import ReplyKeyboardRemove, Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database.database import db
from database.models import User, WeightHistory
from utils.keyboards import get_main_menu_keyboard, profile_keyboard
from utils.validators import parse_float


class ProfileState:
    UPDATE_WEIGHT = 1
    CHANGE_GOAL = 2


async def _get_user(session: AsyncSession, telegram_id: int) -> User | None:
    stmt: Select = select(User).where(User.telegram_id == str(telegram_id))
    result = await session.execute(stmt)
    return result.scalars().first()


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    async for session in db.session():
        user = await _get_user(session, update.effective_user.id)  # type: ignore[arg-type]
    if not user:
        await update.effective_chat.send_message(
            "Nu ai încă un profil. Folosește comanda /start pentru a începe."
        )
        return ConversationHandler.END

    progress = user.current_weight - user.start_weight
    progress_text = f"{progress:+.1f} kg"

    text = (
        "Profilul tău\n\n"
        f"Greutate inițială:\n{user.start_weight:.1f} kg\n\n"
        f"Greutate curentă:\n{user.current_weight:.1f} kg\n\n"
        "Progres:\n"
        f"{progress_text}\n\n"
        f"Înălțime:\n{user.height_cm} cm\n\n"
        f"Vârstă:\n{user.age}\n\n"
        "Obiectiv:\n"
        f"{user.goal}\n"
    )
    await update.effective_chat.send_message(text, reply_markup=profile_keyboard())
    return ConversationHandler.END


async def profile_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog alege o opțiune.")
        return ConversationHandler.END
    text = update.message.text.strip()
    if text == "Actualizează greutatea":
        await update.effective_chat.send_message(
            "Introdu noua ta greutate în kg:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ProfileState.UPDATE_WEIGHT
    if text == "Schimbă obiectivul":
        await update.effective_chat.send_message(
            "Scrie noul tău obiectiv (Slăbire, Menținere, Creștere):",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ProfileState.CHANGE_GOAL
    return ConversationHandler.END


async def update_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog introdu un număr valid.")
        return ProfileState.UPDATE_WEIGHT
    weight = parse_float(update.message.text)
    if weight is None or weight <= 0 or weight > 400:
        await update.effective_chat.send_message(
            "Te rog introdu o greutate validă în kilograme."
        )
        return ProfileState.UPDATE_WEIGHT

    async for session in db.session():
        user = await _get_user(session, update.effective_user.id)  # type: ignore[arg-type]
        if not user:
            await update.effective_chat.send_message(
                "Nu am găsit profilul tău. Folosește /start pentru a începe."
            )
            return ConversationHandler.END
        user.current_weight = weight
        history = WeightHistory(
            user_id=user.id,
            weight=weight,
            date=date.today(),
        )
        session.add(history)
        await session.commit()

    await update.effective_chat.send_message(
        "Greutatea a fost actualizată.", reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END


async def change_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog introdu un obiectiv valid.")
        return ProfileState.CHANGE_GOAL
    goal = update.message.text.strip()
    if goal not in {"Slăbire", "Menținere", "Creștere"}:
        await update.effective_chat.send_message(
            "Te rog alege un obiectiv: Slăbire, Menținere sau Creștere."
        )
        return ProfileState.CHANGE_GOAL

    async for session in db.session():
        user = await _get_user(session, update.effective_user.id)  # type: ignore[arg-type]
        if not user:
            await update.effective_chat.send_message(
                "Nu am găsit profilul tău. Folosește /start pentru a începe."
            )
            return ConversationHandler.END
        user.goal = goal
        await session.commit()

    await update.effective_chat.send_message(
        "Obiectivul a fost actualizat.", reply_markup=get_main_menu_keyboard()
    )
    return ConversationHandler.END


def build_profile_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👤 Profil$"), show_profile)],
        states={
            ProfileState.UPDATE_WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_weight)
            ],
            ProfileState.CHANGE_GOAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, change_goal)
            ],
        },
        fallbacks=[
            MessageHandler(
                filters.Regex("^(Actualizează greutatea|Schimbă obiectivul)$"),
                profile_router,
            )
        ],
        allow_reentry=True,
    )

