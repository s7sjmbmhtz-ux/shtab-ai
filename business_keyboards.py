from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def sales_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Скрипт продаж"), KeyboardButton(text="💬 Ответ клиенту")],
            [KeyboardButton(text="📑 Коммерческое предложение"), KeyboardButton(text="🛡 Работа с возражениями")],
            [KeyboardButton(text="📊 Анализ переписки"), KeyboardButton(text="🔙 Назад")],
        ],
        resize_keyboard=True,
    )


def marketing_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Маркетинговый пост"), KeyboardButton(text="🗓 Контент-план")],
            [KeyboardButton(text="🎯 Анализ аудитории"), KeyboardButton(text="✉️ Email-рассылка")],
            [KeyboardButton(text="🔙 Назад")],
        ],
        resize_keyboard=True,
    )


def marketplace_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Карточка из фото"), KeyboardButton(text="✨ Концепт без фото")],
            [KeyboardButton(text="📝 Описание товара")],
            [KeyboardButton(text="🔙 Назад")],
        ],
        resize_keyboard=True,
    )


def marketplace_product_type() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for title, value in [
        ("📦 Главное фото · 80 💎", "main"),
        ("🏠 Lifestyle · 90 💎", "lifestyle"),
        ("📊 Основа инфографики · 140 💎", "infographic"),
        ("🚀 Комплект из 3 · 180 💎", "bundle"),
    ]:
        builder.button(text=title, callback_data=f"mp:type:{value}")
    builder.adjust(1)
    return builder.as_markup()


def marketplace_category() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for title, value in [
        ("🔨 Инструменты", "tools"),
        ("🍳 Кухня", "kitchen"),
        ("📱 Электроника", "electronics"),
        ("💄 Косметика", "cosmetics"),
        ("👕 Одежда", "clothing"),
        ("👟 Обувь", "shoes"),
        ("🪑 Мебель", "furniture"),
        ("🧸 Детские товары", "kids"),
        ("🐾 Зоотовары", "pets"),
        ("📦 Другое", "other"),
    ]:
        builder.button(text=title, callback_data=f"mp:category:{value}")
    builder.adjust(2)
    return builder.as_markup()


def marketplace_goal() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for title, value in [
        ("🔥 Максимум продаж", "sales"),
        ("✨ Премиальная подача", "premium"),
        ("📦 Классический каталог", "catalog"),
        ("📱 Реклама и соцсети", "social"),
    ]:
        builder.button(text=title, callback_data=f"mp:goal:{value}")
    builder.adjust(1)
    return builder.as_markup()


def marketplace_platform() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for title, value in [
        ("🟣 Wildberries", "wb"),
        ("🔵 Ozon", "ozon"),
        ("🟡 Яндекс Маркет", "yandex"),
        ("🌐 Универсально", "all"),
    ]:
        builder.button(text=title, callback_data=f"mp:platform:{value}")
    builder.adjust(2)
    return builder.as_markup()


def marketplace_style() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for title, value in [
        ("Светлый минимализм", "minimal"),
        ("Тёмный премиум", "premium"),
        ("Домашний уют", "cozy"),
        ("Яркая реклама", "bright"),
        ("Технический", "technical"),
        ("Натуральный", "natural"),
    ]:
        builder.button(text=title, callback_data=f"mp:style:{value}")
    builder.adjust(2)
    return builder.as_markup()


def marketplace_confirm() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Создать", callback_data="mp:confirm")
    builder.button(text="❌ Отмена", callback_data="mp:cancel")
    builder.adjust(2)
    return builder.as_markup()


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )


def marketplace_features_action() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Указать характеристики", callback_data="mp:features:write")
    builder.button(text="⏭ Пропустить", callback_data="mp:features:skip")
    builder.adjust(1)
    return builder.as_markup()
