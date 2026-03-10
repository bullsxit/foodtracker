from __future__ import annotations

from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from database.database import db
from database.models import DailyCalories, Food, User
from database.query_helpers import tid_literal
from services.calorie_ai_service import (
    CalorieAIService,
    FoodAnalysisResult,
    format_food_analysis,
)
from utils.keyboards import confirmation_keyboard, get_main_menu_keyboard
from utils.validators import parse_float


class HomeState:
    FOOD_NAME = 1
    FOOD_CALORIES = 2
    FOOD_PROTEIN = 3
    FOOD_CARBS = 4
    FOOD_FAT = 5
    AI_CONFIRM = 6


async def show_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.effective_chat:
        return ConversationHandler.END
    keyboard = ReplyKeyboardMarkup(
        [
            ["Adaugă mâncare manual"],
            ["Caloriile de azi"],
            ["Încărcă fotografie cu mâncare"],
        ],
        resize_keyboard=True,
    )
    await update.effective_chat.send_message(
        "🏠 Acasă\n\nAlege o acțiune:",
        reply_markup=keyboard,
    )
    return ConversationHandler.END


async def home_entry_router(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog alege o opțiune din meniu.")
        return ConversationHandler.END
    text = update.message.text.strip()
    if text == "Adaugă mâncare manual":
        await update.effective_chat.send_message(
            "Numele mâncării:", reply_markup=ReplyKeyboardRemove()
        )
        return HomeState.FOOD_NAME
    if text == "Caloriile de azi":
        return await show_today_calories(update, context)
    if text == "Încărcă fotografie cu mâncare":
        await update.effective_chat.send_message(
            "Trimite o fotografie cu mâncarea ta."
        )
        return ConversationHandler.END
    return ConversationHandler.END


async def handle_food_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.photo:
        await update.effective_chat.send_message("Te rog trimite o fotografie validă.")
        return ConversationHandler.END

    photo = update.message.photo[-1]
    file = await photo.get_file()
    image_bytes = await file.download_as_bytearray()

    ai_service = CalorieAIService()
    analysis: FoodAnalysisResult = await ai_service.analyze_food_image(bytes(image_bytes))
    context.user_data["ai_food_analysis"] = analysis

    await update.effective_chat.send_message(
        format_food_analysis(analysis) + "\n\nConfirmi salvarea?",
        reply_markup=confirmation_keyboard(),
    )
    return HomeState.AI_CONFIRM


async def confirm_ai_food(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog alege o opțiune.")
        return HomeState.AI_CONFIRM
    choice = update.message.text.strip()
    analysis: FoodAnalysisResult | None = context.user_data.get("ai_food_analysis")
    if not analysis:
        await update.effective_chat.send_message(
            "Nu există o analiză disponibilă. Te rog încearcă din nou.",
            reply_markup=get_main_menu_keyboard(),
        )
        return ConversationHandler.END

    if choice == "Da":
        async for session in db.session():
            await _save_food_and_update_daily(
                session=session,
                telegram_id=update.effective_user.id,  # type: ignore[arg-type]
                name=analysis.name,
                calories=analysis.calories,
                protein=analysis.protein,
                carbs=analysis.carbs,
                fat=analysis.fat,
                entry_date=date.today(),
            )
            await session.commit()
        await update.effective_chat.send_message(
            "Am salvat mâncarea în jurnalul tău.",
            reply_markup=get_main_menu_keyboard(),
        )
        context.user_data.pop("ai_food_analysis", None)
        return ConversationHandler.END

    if choice == "Modifică":
        context.user_data["manual_from_ai"] = analysis
        await update.effective_chat.send_message(
            "Poți modifica valorile. Începe cu numele mâncării:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return HomeState.FOOD_NAME

    await update.effective_chat.send_message(
        "Am anulat salvarea.", reply_markup=get_main_menu_keyboard()
    )
    context.user_data.pop("ai_food_analysis", None)
    return ConversationHandler.END


async def manual_food_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog introdu un nume valid.")
        return HomeState.FOOD_NAME
    context.user_data["food_name"] = update.message.text.strip()
    await update.effective_chat.send_message("Calorii:")
    return HomeState.FOOD_CALORIES


async def manual_food_calories(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    if not update.message or not update.message.text:
        await update.effective_chat.send_message("Te rog introdu un număr valid.")
        return HomeState.FOOD_CALORIES
    calories = parse_float(update.message.text)
    if calories is None or calories <= 0:
        await update.effective_chat.send_message("Te rog introdu un număr valid.")
        return HomeState.FOOD_CALORIES
    context.user_data["calories"] = calories
    await update.effective_chat.send_message("Proteine (opțional):")
    return HomeState.FOOD_PROTEIN


async def manual_food_protein(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    protein = None
    if update.message and update.message.text:
        protein = parse_float(update.message.text)
    context.user_data["protein"] = protein
    await update.effective_chat.send_message("Carbohidrați (opțional):")
    return HomeState.FOOD_CARBS


async def manual_food_carbs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    carbs = None
    if update.message and update.message.text:
        carbs = parse_float(update.message.text)
    context.user_data["carbs"] = carbs
    await update.effective_chat.send_message("Grăsimi (opțional):")
    return HomeState.FOOD_FAT


async def manual_food_fat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    fat = None
    if update.message and update.message.text:
        fat = parse_float(update.message.text)
    context.user_data["fat"] = fat

    name = context.user_data.get("food_name")
    calories = context.user_data.get("calories")
    protein = context.user_data.get("protein")
    carbs = context.user_data.get("carbs")
    fat_val = context.user_data.get("fat")

    async for session in db.session():
        await _save_food_and_update_daily(
            session=session,
            telegram_id=update.effective_user.id,  # type: ignore[arg-type]
            name=name,
            calories=calories,
            protein=protein,
            carbs=carbs,
            fat=fat_val,
            entry_date=date.today(),
        )
        await session.commit()

    await update.effective_chat.send_message(
        "Mâncarea a fost salvată.",
        reply_markup=get_main_menu_keyboard(),
    )
    for key in ["food_name", "calories", "protein", "carbs", "fat", "manual_from_ai"]:
        context.user_data.pop(key, None)
    return ConversationHandler.END


async def show_today_calories(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    async for session in db.session():
        stmt: Select = select(DailyCalories).where(
            DailyCalories.telegram_id == tid_literal(update.effective_user.id),  # type: ignore[arg-type]
            DailyCalories.date == date.today(),
        )
        result = await session.execute(stmt)
        daily = result.scalars().first()

        user_stmt: Select = select(User).where(
            User.telegram_id == tid_literal(update.effective_user.id)  # type: ignore[arg-type]
        )
        user_result = await session.execute(user_stmt)
        user = user_result.scalars().first()

    consumed = daily.total_calories if daily else 0.0
    target = user.target_calories if user else 0.0
    remaining = max(0.0, target - consumed)

    await update.effective_chat.send_message(
        "Calorii consumate azi:\n\n"
        f"{consumed:.0f} / {target:.0f} kcal\n\n"
        "Au mai rămas:\n\n"
        f"{remaining:.0f} kcal",
        reply_markup=get_main_menu_keyboard(),
    )
    return ConversationHandler.END


async def _save_food_and_update_daily(
    session: AsyncSession,
    telegram_id: int,
    name: str,
    calories: float,
    protein: float | None,
    carbs: float | None,
    fat: float | None,
    entry_date: date,
) -> None:
    food = Food(
        telegram_id=telegram_id,
        food_name=name,
        calories=calories,
        protein=protein,
        carbs=carbs,
        fat=fat,
        date=entry_date,
    )
    session.add(food)

    stmt: Select = select(DailyCalories).where(
        DailyCalories.telegram_id == tid_literal(telegram_id),
        DailyCalories.date == entry_date,
    )
    result = await session.execute(stmt)
    daily = result.scalars().first()
    if not daily:
        daily = DailyCalories(
            telegram_id=telegram_id,
            date=entry_date,
            total_calories=calories,
        )
        session.add(daily)
    else:
        daily.total_calories += calories


def build_home_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🏠 Acasă$"), show_home),
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, home_entry_router
            ),
            MessageHandler(filters.PHOTO, handle_food_photo),
        ],
        states={
            HomeState.FOOD_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_food_name)
            ],
            HomeState.FOOD_CALORIES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_food_calories)
            ],
            HomeState.FOOD_PROTEIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_food_protein)
            ],
            HomeState.FOOD_CARBS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_food_carbs)
            ],
            HomeState.FOOD_FAT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_food_fat)
            ],
            HomeState.AI_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_ai_food)
            ],
        },
        fallbacks=[],
        allow_reentry=True,
    )

