"""Основные клавиатуры Shtab AI."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def get_welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать работу", callback_data="welcome:start")],
        [InlineKeyboardButton(text="🎁 Что доступно бесплатно", callback_data="welcome:free")],
    ])


def get_main_menu(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🤖 AI Ассистент")],
        [KeyboardButton(text="🖼 Создать картинку"), KeyboardButton(text="🎬 Создать видео")],
        [KeyboardButton(text="🏢 Продажи"), KeyboardButton(text="📈 Маркетинг")],
        [KeyboardButton(text="🛒 Маркетплейсы")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💎 Баланс")],
        [KeyboardButton(text="📜 История операций"), KeyboardButton(text="💳 Купить токены")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="👑 Статистика")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Выберите раздел")
