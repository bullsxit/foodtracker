from __future__ import annotations

from telegram.ext import Application, ApplicationBuilder

from config import get_config
from handlers.history_handler import build_history_handler
from handlers.home_handler import build_home_conversation_handler
from handlers.profile_handler import build_profile_handler
from handlers.settings_handler import build_settings_handler
from handlers.start_handler import build_start_conversation_handler
from handlers.statistics_handler import build_statistics_handler


def create_application() -> Application:
    """Build and return the Telegram Application with all handlers registered."""
    config = get_config()
    application: Application = (
        ApplicationBuilder()
        .token(config.bot_token)
        .concurrent_updates(True)
        .build()
    )
    application.add_handler(build_start_conversation_handler())
    application.add_handler(build_home_conversation_handler())
    application.add_handler(build_statistics_handler())
    application.add_handler(build_history_handler())
    application.add_handler(build_profile_handler())
    application.add_handler(build_settings_handler())
    return application
