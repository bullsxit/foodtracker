from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database.database import db
from database.models import Food
from database.query_helpers import tid_literal
from utils.keyboards import history_navigation_keyboard, get_main_menu_keyboard


async def _get_diary_date(context: ContextTypes.DEFAULT_TYPE) -> date:
    stored = context.user_data.get("history_date")
    if isinstance(stored, date):
        return stored
    today = date.today()
    context.user_data["history_date"] = today
    return today


async def _change_diary_date(
    context: ContextTypes.DEFAULT_TYPE,
    delta_days: int,
) -> date:
    current = await _get_diary_date(context)
    new_date = current + timedelta(days=delta_days)
    context.user_data["history_date"] = new_date
    return new_date


async def _render_diary_for_date(
    session: AsyncSession, telegram_id: int, target_date: date
) -> str:
    stmt: Select = (
        select(Food)
        .where(
            Food.telegram_id == tid_literal(telegram_id),
            Food.date == target_date,
        )
        .order_by(Food.id)
    )
    result = await session.execute(stmt)
    foods = result.scalars().all()
    if not foods:
        return (
            f"{target_date.strftime('%d %B %Y')}\n\nNu există înregistrări pentru această zi."
        )

    total = sum(f.calories for f in foods)

    lines: list[str] = [f"{target_date.strftime('%d %B %Y')}\n"]
    for food in foods:
        lines.append(f"- {food.food_name} – {food.calories:.0f} kcal")
    lines.append("\nTotal:\n")
    lines.append(f"{total:.0f} kcal")
    return "\n".join(lines)


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_chat:
        return ConversationHandler.END
    target_date = await _get_diary_date(context)
    async for session in db.session():
        text = await _render_diary_for_date(
            session=session,
            telegram_id=update.effective_user.id,  # type: ignore[arg-type]
            target_date=target_date,
        )
    await update.effective_chat.send_message(
        text,
        reply_markup=history_navigation_keyboard(),
    )
    return ConversationHandler.END


async def history_navigation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog alege o opțiune.")
        return ConversationHandler.END
    text = update.message.text.strip()
    if text == "Zi precedentă":
        target_date = await _change_diary_date(context, -1)
    elif text == "Zi următoare":
        target_date = await _change_diary_date(context, 1)
    else:
        await update.effective_chat.send_message(
            "Te întorc la meniu.", reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END

    async for session in db.session():
        content = await _render_diary_for_date(
            session=session,
            telegram_id=update.effective_user.id,  # type: ignore[arg-type]
            target_date=target_date,
        )
    await update.effective_chat.send_message(
        content,
        reply_markup=history_navigation_keyboard(),
    )
    return ConversationHandler.END


def build_history_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📖 Jurnal$"), show_history),
        ],
        states={},
        fallbacks=[
            MessageHandler(
                filters.Regex("^(Zi precedentă|Zi următoare)$"), history_navigation
            )
        ],
        allow_reentry=True,
    )

