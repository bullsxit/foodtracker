from __future__ import annotations

from telegram import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo


def main_menu_keyboard(web_app_url: str | None = None) -> ReplyKeyboardMarkup:
    """Build main menu. If web_app_url is set (production), add a button to open the Mini App."""
    keyboard = [
        [KeyboardButton("🏠 Acasă"), KeyboardButton("📊 Statistici")],
        [KeyboardButton("📖 Jurnal"), KeyboardButton("👤 Profil")],
        [KeyboardButton("⚙️ Setări")],
    ]
    if web_app_url:
        keyboard.insert(0, [KeyboardButton("📱 Deschide aplicația", web_app=WebAppInfo(url=web_app_url))])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main menu with Mini App button when BOT_WEBHOOK_URL is set."""
    try:
        from config import get_config
        config = get_config()
        url = (config.webhook_url.rstrip("/") + "/webapp/") if config.webhook_url else None
    except Exception:
        url = None
    return main_menu_keyboard(url)


def goals_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("Slăbire")],
        [KeyboardButton("Menținere")],
        [KeyboardButton("Creștere")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def activity_level_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("Sedentar")],
        [KeyboardButton("Ușor activ")],
        [KeyboardButton("Moderat activ")],
        [KeyboardButton("Foarte activ")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def confirmation_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("Da"), KeyboardButton("Modifică")],
        [KeyboardButton("Anulează")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


def history_navigation_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("Zi precedentă"), KeyboardButton("Zi următoare")],
        [KeyboardButton("🏠 Acasă")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def profile_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("Actualizează greutatea")],
        [KeyboardButton("Schimbă obiectivul")],
        [KeyboardButton("🏠 Acasă")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def settings_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("Resetează profil")],
        [KeyboardButton("Schimbă datele personale")],
        [KeyboardButton("Schimbă nivel activitate")],
        [KeyboardButton("🏠 Acasă")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

