from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def sales_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📞 Скрипт продаж"), KeyboardButton(text="💬 Ответ клиенту")],
        [KeyboardButton(text="📑 Коммерческое предложение"), KeyboardButton(text="🛡 Работа с возражениями")],
        [KeyboardButton(text="📊 Анализ переписки"), KeyboardButton(text="🔙 Назад")],
    ], resize_keyboard=True)


def marketing_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📝 Маркетинговый пост"), KeyboardButton(text="🗓 Контент-план")],
        [KeyboardButton(text="🎯 Анализ аудитории"), KeyboardButton(text="✉️ Email-рассылка")],
        [KeyboardButton(text="🔙 Назад")],
    ], resize_keyboard=True)


def marketplace_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📸 Карточка из фото"), KeyboardButton(text="✨ Карточка без фото")],
        [KeyboardButton(text="📝 Описание товара")],
        [KeyboardButton(text="🔙 Назад")],
    ], resize_keyboard=True)


def marketplace_product_type() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    items = [
        ("Главное фото — 80 💎", "main"),
        ("Lifestyle-сцена — 90 💎", "lifestyle"),
        ("Инфографика — 140 💎", "infographic"),
        ("Комплект из 3 — 180 💎", "bundle"),
    ]
    for title, value in items:
        builder.button(text=title, callback_data=f"mp:type:{value}")
    builder.adjust(1)
    return builder.as_markup()


def marketplace_style() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for title, value in [
        ("Светлый минимализм", "minimal"),
        ("Премиальный", "premium"),
        ("Домашний уют", "cozy"),
        ("Яркий рекламный", "bright"),
    ]:
        builder.button(text=title, callback_data=f"mp:style:{value}")
    builder.adjust(2)
    return builder.as_markup()


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True
    )
