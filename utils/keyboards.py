from __future__ import annotations

from telegram import ReplyKeyboardMarkup, KeyboardButton


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("🏠 Acasă"), KeyboardButton("📊 Statistici")],
        [KeyboardButton("📖 Jurnal"), KeyboardButton("👤 Profil")],
        [KeyboardButton("⚙️ Setări")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


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

