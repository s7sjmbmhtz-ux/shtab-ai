"""Основные клавиатуры бота."""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🤖 AI Ассистент")],
            [KeyboardButton(text="🖼 Создать картинку"), KeyboardButton(text="🎬 Создать видео")],
            [KeyboardButton(text="🏢 Продажи"), KeyboardButton(text="📈 Маркетинг")],
            [KeyboardButton(text="🛒 Маркетплейсы")],
            [KeyboardButton(text="💰 Мой баланс"), KeyboardButton(text="💳 Купить кредиты")],
            [KeyboardButton(text="📜 История операций")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел",
    )
