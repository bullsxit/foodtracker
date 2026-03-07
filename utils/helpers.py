from __future__ import annotations

from datetime import date

from telegram import Update
from telegram.ext import ContextTypes


def get_telegram_id(update: Update) -> int:
    if update.effective_user is None:
        raise RuntimeError("No effective user in update.")
    return update.effective_user.id


def get_today() -> date:
    return date.today()


async def send_error_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str = "A apărut o eroare neașteptată. Te rog încearcă din nou.",
) -> None:
    if update.effective_chat is None:
        return
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

