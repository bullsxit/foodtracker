from __future__ import annotations

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database.database import db
from services.statistics_service import StatisticsService
from utils.keyboards import main_menu_keyboard


async def show_statistics_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not update.effective_chat:
        return ConversationHandler.END
    await update.effective_chat.send_message(
        "📊 Statistici\n\nTrimit acum graficele tale.",
        reply_markup=main_menu_keyboard(),
    )

    async for session in db.session():
        service = StatisticsService(session)
        img7 = await service.generate_calories_chart(
            telegram_id=update.effective_user.id,  # type: ignore[arg-type]
            days=7,
        )
        img30 = await service.generate_calories_chart(
            telegram_id=update.effective_user.id,  # type: ignore[arg-type]
            days=30,
        )
        avg7 = await service.get_average_calories(
            telegram_id=update.effective_user.id, days=7  # type: ignore[arg-type]
        )

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=img7,
        caption="Statistici ultimele 7 zile",
    )
    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=img30,
        caption="Statistici ultimele 30 zile",
    )
    if avg7 is not None:
        await update.effective_chat.send_message(
            f"Media caloriilor în ultimele 7 zile: {avg7:.0f} kcal"
        )

    return ConversationHandler.END


def build_statistics_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📊 Statistici$"), show_statistics_menu)
        ],
        states={},
        fallbacks=[],
        allow_reentry=True,
    )

