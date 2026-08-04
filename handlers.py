"""Приветствие, главное меню и профиль пользователя."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import db_manager, token_repository, user_repository
from keyboards import get_main_menu, get_welcome_keyboard
from settings import settings

router = Router(name="main_router")


def _is_admin(user_id: int) -> bool:
    return user_id == settings.ADMIN_TELEGRAM_ID


async def _register_user(message: Message) -> None:
    if not message.from_user:
        return
    await user_repository.add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await user_repository.update_activity(message.from_user.id)


WELCOME = (
    "<b>👋 Добро пожаловать в Shtab AI</b>\n\n"
    "Ваш AI-помощник для бизнеса, контента и продаж.\n\n"
    "Здесь можно:\n"
    "• 💬 создавать тексты и общаться с AI;\n"
    "• 🖼 генерировать и улучшать изображения;\n"
    "• 🎬 создавать видео по тексту или фотографии;\n"
    "• 🛒 оформлять карточки товаров для маркетплейсов;\n"
    "• 📈 готовить маркетинговые материалы;\n"
    "• 🏢 писать скрипты продаж и коммерческие предложения.\n\n"
    "<b>🎁 Для знакомства каждому пользователю доступно:</b>\n"
    "• 1 текстовая генерация;\n"
    "• 1 изображение;\n"
    "• 1 видео.\n\n"
    "Сначала попробуйте возможности бесплатно. Покупка токенов понадобится только после исчерпания пробных генераций."
)


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _register_user(message)
    await message.answer(WELCOME, reply_markup=get_welcome_keyboard())


@router.callback_query(F.data == "welcome:start")
async def welcome_start(callback: CallbackQuery) -> None:
    await callback.answer()
    admin = _is_admin(callback.from_user.id)
    text = "<b>Главное меню</b>\n\nВыберите задачу."
    if admin:
        text += "\n\n👑 <b>Режим администратора:</b> генерации выполняются без списания токенов."
    await callback.message.answer(text, reply_markup=get_main_menu(is_admin=admin))


@router.callback_query(F.data == "welcome:free")
async def welcome_free(callback: CallbackQuery) -> None:
    await callback.answer()
    free = await db_manager.get_free_credits(callback.from_user.id)
    await callback.message.answer(
        "<b>Ваш бесплатный старт</b>\n\n"
        f"💬 Текст: <b>{free['text_left']}</b>\n"
        f"🖼 Изображение: <b>{free['image_left']}</b>\n"
        f"🎬 Видео: <b>{free['video_left']}</b>"
    )


@router.message(Command("menu"))
@router.message(F.text == "🔙 Назад")
async def show_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _register_user(message)
    await message.answer("<b>Главное меню</b>", reply_markup=get_main_menu(is_admin=_is_admin(message.from_user.id)))


@router.message(Command("balance"))
@router.message(F.text == "💎 Баланс")
@router.message(F.text == "💰 Мой баланс")
async def show_balance(message: Message) -> None:
    await _register_user(message)
    free = await db_manager.get_free_credits(message.from_user.id)
    if _is_admin(message.from_user.id):
        balance_text = "∞ <b>Тестовый режим</b>"
    else:
        balance = await token_repository.get_user_tokens(message.from_user.id)
        balance_text = f"<b>{balance} 💎</b>"
    await message.answer(
        "<b>💎 Баланс</b>\n\n"
        f"Доступно: {balance_text}\n\n"
        "<b>Бесплатные генерации:</b>\n"
        f"💬 Текст: {free['text_left']}\n"
        f"🖼 Изображение: {free['image_left']}\n"
        f"🎬 Видео: {free['video_left']}"
    )


@router.message(Command("profile"))
@router.message(F.text == "👤 Профиль")
async def profile(message: Message) -> None:
    await _register_user(message)
    user = await user_repository.get_user(message.from_user.id)
    free = await db_manager.get_free_credits(message.from_user.id)
    async with db_manager.connection() as conn:
        cur = await conn.execute("SELECT COUNT(*) AS c FROM token_transactions WHERE user_id = ? AND type IN ('spend','free_trial')", (message.from_user.id,))
        generations = int((await cur.fetchone())["c"])
        cur = await conn.execute("SELECT COUNT(*) AS c FROM payments WHERE user_id = ? AND status = 'succeeded'", (message.from_user.id,))
        payments = int((await cur.fetchone())["c"])
    name = (user.first_name if user else None) or message.from_user.full_name
    balance = "∞" if _is_admin(message.from_user.id) else str(await token_repository.get_user_tokens(message.from_user.id))
    role = "👑 Администратор\n" if _is_admin(message.from_user.id) else ""
    await message.answer(
        f"<b>👤 Профиль</b>\n\n{role}"
        f"Имя: <b>{name}</b>\n"
        f"Telegram ID: <code>{message.from_user.id}</code>\n"
        f"Баланс: <b>{balance} 💎</b>\n"
        f"Всего генераций: <b>{generations}</b>\n"
        f"Успешных оплат: <b>{payments}</b>\n\n"
        f"Бесплатно осталось: текст {free['text_left']}, изображение {free['image_left']}, видео {free['video_left']}"
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await _register_user(message)
    await message.answer(
        "<b>Команды</b>\n\n/start — знакомство\n/menu — главное меню\n/profile — профиль\n"
        "/balance — баланс\n/buy — купить токены\n/history — история операций"
    )


@router.message()
async def unknown_message(message: Message) -> None:
    await _register_user(message)
    await message.answer("Выберите раздел в меню или используйте /help.", reply_markup=get_main_menu(is_admin=_is_admin(message.from_user.id)))
