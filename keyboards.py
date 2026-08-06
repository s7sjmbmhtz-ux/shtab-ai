"""Основные клавиатуры Shtab AI."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def get_welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Изучить рекомендации", callback_data="onboarding:academy")],
        [InlineKeyboardButton(text="✅ Я ознакомился и продолжаю", callback_data="onboarding:accept")],
        [InlineKeyboardButton(text="🎁 Что доступно бесплатно", callback_data="welcome:free")],
    ])


def get_academy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Текстовые запросы", callback_data="academy:text")],
        [InlineKeyboardButton(text="🖼 Изображения", callback_data="academy:image")],
        [InlineKeyboardButton(text="🎬 Видео", callback_data="academy:video")],
        [InlineKeyboardButton(text="📦 Маркетплейсы", callback_data="academy:marketplace")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="academy:back")],
    ])


def get_main_menu(*, is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🤖 AI Ассистент")],
        [KeyboardButton(text="🖼 Создать картинку"), KeyboardButton(text="🎬 Создать видео")],
        [KeyboardButton(text="🏢 Продажи"), KeyboardButton(text="📈 Маркетинг")],
        [KeyboardButton(text="🛒 Маркетплейсы")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💎 Баланс")],
        [KeyboardButton(text="📜 История операций"), KeyboardButton(text="💳 Купить токены")],
        [KeyboardButton(text="📚 Как пользоваться AI")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="🛠 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Выберите раздел")
