"""Базовые команды и главное меню.

Старая подписочная логика удалена. Генерации обслуживает generation_handlers.py,
а история и админские команды — token_admin_handlers.py.
"""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import db_manager, token_repository, user_repository
from keyboards import get_main_menu

router = Router(name="main_router")


async def _register_user(message: Message) -> None:
    if not message.from_user:
        return
    await user_repository.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
    )
    await user_repository.update_activity(message.from_user.id)


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _register_user(message)
    free = await db_manager.get_free_credits(message.from_user.id)
    balance = await token_repository.get_user_tokens(message.from_user.id)
    await message.answer(
        "<b>Добро пожаловать в ШТАБ AI</b>\n\n"
        "Здесь можно работать с текстом, создавать изображения и видео.\n\n"
        "Новый пользователь получает бесплатно:\n"
        f"• текст: <b>{free['text_left']}</b>\n"
        f"• изображение: <b>{free['image_left']}</b>\n"
        f"• видео: <b>{free['video_left']}</b>\n\n"
        f"Баланс: <b>{balance} 💎</b>",
        reply_markup=get_main_menu(),
    )


@router.message(Command("menu"))
@router.message(F.text == "🔙 Назад")
async def show_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _register_user(message)
    await message.answer("Главное меню:", reply_markup=get_main_menu())


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await _register_user(message)
    await message.answer(
        "<b>Команды</b>\n\n"
        "/start — запуск бота\n"
        "/menu — главное меню\n"
        "/balance — баланс и бесплатные попытки\n"
        "/buy — пакеты токенов\n"
        "/history — история операций\n"
        "/ai — выбор текстовой модели"
    )


@router.message()
async def unknown_message(message: Message) -> None:
    await _register_user(message)
    await message.answer(
        "Выберите раздел в меню или используйте /help.",
        reply_markup=get_main_menu(),
    )
