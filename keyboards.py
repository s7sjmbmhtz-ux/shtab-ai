from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from models import TextOperation


# ==================== ГЛАВНОЕ МЕНЮ ====================

def get_main_menu() -> ReplyKeyboardMarkup:
    buttons = [
        [
            KeyboardButton(text="🏢 Продажи"),
            KeyboardButton(text="📈 Маркетинг")
        ],
        [
            KeyboardButton(text="🖼 Изображения"),
            KeyboardButton(text="🎬 Видео")
        ],
        [
            KeyboardButton(text="🤖 AI Ассистент"),
            KeyboardButton(text="🛒 Маркетплейсы")
        ],
        [
            KeyboardButton(text="👤 Кабинет"),
            KeyboardButton(text="💎 Тарифы")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


# ==================== ПРОДАЖИ ====================

def get_sales_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [
            KeyboardButton(text="📞 Скрипт продаж"),
            KeyboardButton(text="💬 Ответ клиенту")
        ],
        [
            KeyboardButton(text="📑 Коммерческое предложение"),
            KeyboardButton(text="🛡️ Работа с возражениями")
        ],
        [
            KeyboardButton(text="📊 Анализ переписки"),
            KeyboardButton(text="⬅️ Назад")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_communication_format_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [
            KeyboardButton(text="📞 Холодный звонок"),
            KeyboardButton(text="☎️ Тёплый звонок")
        ],
        [
            KeyboardButton(text="💬 Переписка"),
            KeyboardButton(text="🤝 Личная встреча")
        ],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_script_result_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Переделать", callback_data="sales_refine_script")
    builder.button(text="🔄 Новый скрипт", callback_data="sales_new_script")
    builder.button(text="🏠 Меню", callback_data="sales_main_menu")
    builder.adjust(2, 1)
    return builder.as_markup()


# ==================== МАРКЕТИНГ ====================

PLATFORM_MAP = {
    "📱 Instagram": "Instagram",
    "✈️ Telegram": "Telegram",
    "📘 VK": "VK",
    "💼 LinkedIn": "LinkedIn",
    "🌐 Другое": "Другое"
}

STYLE_MAP = {
    "🎓 Экспертный": "Экспертный",
    "🤝 Дружелюбный": "Дружелюбный",
    "🔥 Провокационный": "Провокационный",
    "💎 Премиум": "Премиум"
}


def get_marketing_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [
            KeyboardButton(text="📝 Продающий пост"),
            KeyboardButton(text="📅 Контент-план")
        ],
        [
            KeyboardButton(text="🎯 Рекламный оффер"),
            KeyboardButton(text="📧 Email-рассылка")
        ],
        [
            KeyboardButton(text="💎 УТП"),
            KeyboardButton(text="🔍 Анализ ЦА")
        ],
        [
            KeyboardButton(text="⬅️ Назад")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_platform_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📱 Instagram"), KeyboardButton(text="✈️ Telegram")],
        [KeyboardButton(text="📘 VK"), KeyboardButton(text="💼 LinkedIn")],
        [KeyboardButton(text="🌐 Другое")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_style_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🎓 Экспертный"), KeyboardButton(text="🤝 Дружелюбный")],
        [KeyboardButton(text="🔥 Провокационный"), KeyboardButton(text="💎 Премиум")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_post_result_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Поделиться", callback_data="marketing_share_post")
    builder.button(text="✏️ Переделать", callback_data="marketing_refine_post")
    builder.button(text="🔄 Новый пост", callback_data="marketing_new_post")
    builder.button(text="🏠 Меню", callback_data="marketing_main_menu")
    builder.adjust(2, 2)
    return builder.as_markup()


# ==================== ИЗОБРАЖЕНИЯ ====================

PURPOSE_MAP = {
    "📢 Реклама": "реклама",
    "📱 Соцсети": "соцсети",
    "🌐 Сайт": "сайт",
    "🛒 Маркетплейс": "маркетплейс"
}

IMAGE_STYLE_MAP = {
    "🎨 Реалистичный": "Реалистичный",
    "✨ Минимализм": "Минимализм",
    "🎭 3D": "3D",
    "🖌 Иллюстрация": "Иллюстрация"
}

SIZE_MAP = {
    "⬜ Квадрат": {"label": "Квадрат (1024x1024)", "api": "1024x1024", "ratio": "1:1"},
    "⬆️ Вертикальный": {"label": "Вертикальный (768x1024)", "api": "768x1024", "ratio": "3:4"},
    "↔️ Горизонтальный": {"label": "Горизонтальный (1024x768)", "api": "1024x768", "ratio": "4:3"}
}


def get_images_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🖼 Создать изображение")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_purpose_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="📢 Реклама"), KeyboardButton(text="📱 Соцсети")],
        [KeyboardButton(text="🌐 Сайт"), KeyboardButton(text="🛒 Маркетплейс")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_image_style_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🎨 Реалистичный"), KeyboardButton(text="✨ Минимализм")],
        [KeyboardButton(text="🎭 3D"), KeyboardButton(text="🖌 Иллюстрация")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_image_size_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="⬜ Квадрат"), KeyboardButton(text="⬆️ Вертикальный")],
        [KeyboardButton(text="↔️ Горизонтальный")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_image_result_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Переделать", callback_data="image_refine")
    builder.button(text="🆕 Новое", callback_data="image_new")
    builder.button(text="🏠 Меню", callback_data="image_menu")
    builder.adjust(2, 1)
    return builder.as_markup()


# ==================== ВИДЕО ====================

def get_video_menu_keyboard() -> ReplyKeyboardMarkup:
    """Меню раздела «Видео»."""
    buttons = [
        [KeyboardButton(text="🎬 Создать видео")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_video_models_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора модели для видео."""
    buttons = [
        [KeyboardButton(text="⚡ LTX Video — 10 токенов/сек")],
        [KeyboardButton(text="🎬 CogVideoX — 35 токенов/сек")],
        [KeyboardButton(text="🎥 Kling Standard — 30 токенов/сек")],
        [KeyboardButton(text="🌟 Kling Pro — 56 токенов/сек")],
        [KeyboardButton(text="🌟 Veo 3.1 Lite — 35 токенов/сек")],
        [KeyboardButton(text="💎 Veo 3.1 — 200 токенов/сек")],
        [KeyboardButton(text="🌈 Luma Ray2 — 40 токенов/сек")],
        [KeyboardButton(text="🎞️ Runway Gen-4 — 60 токенов/сек")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_video_duration_keyboard(max_duration: int = 30) -> ReplyKeyboardMarkup:
    """Клавиатура выбора длительности видео."""
    durations = []
    
    if max_duration >= 5:
        durations.append(KeyboardButton(text="5 секунд"))
    if max_duration >= 8:
        durations.append(KeyboardButton(text="8 секунд"))
    if max_duration >= 10:
        durations.append(KeyboardButton(text="10 секунд"))
    if max_duration >= 15:
        durations.append(KeyboardButton(text="15 секунд"))
    if max_duration >= 20:
        durations.append(KeyboardButton(text="20 секунд"))
    if max_duration >= 30:
        durations.append(KeyboardButton(text="30 секунд"))
    
    buttons = []
    for i in range(0, len(durations), 2):
        row = durations[i:i+2]
        buttons.append(row)
    
    buttons.append([KeyboardButton(text="⬅️ Назад")])
    
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_skip_photo_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура пропуска фото."""
    buttons = [
        [KeyboardButton(text="⏭ Пропустить фото")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


# ==================== AI РЕДАКТОР ====================

OPERATION_MAP = {
    "✨ Улучшить": TextOperation.IMPROVE,
    "📝 Конспект": TextOperation.SUMMARY,
    "📋 Кратко": TextOperation.SHORT_SUMMARY,
    "🎯 Исправить": TextOperation.FIX,
    "🔄 Перефразировать": TextOperation.REWRITE,
    "📏 Сократить": TextOperation.SHORTEN,
    "➕ Расширить": TextOperation.EXPAND,
    "📌 Тезисы": TextOperation.BULLETS,
    "🌍 Перевести": TextOperation.TRANSLATE,
}

LANGUAGE_MAP = {
    "🇷🇺 Русский": "русский",
    "🇬🇧 Английский": "английский",
    "🇩🇪 Немецкий": "немецкий",
    "🇫🇷 Французский": "французский",
    "🇪🇸 Испанский": "испанский",
    "🇨🇳 Китайский": "китайский",
}


def get_editor_operations_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [
            KeyboardButton(text="✨ Улучшить"),
            KeyboardButton(text="📝 Конспект")
        ],
        [
            KeyboardButton(text="📋 Кратко"),
            KeyboardButton(text="🎯 Исправить")
        ],
        [
            KeyboardButton(text="🔄 Перефразировать"),
            KeyboardButton(text="📏 Сократить")
        ],
        [
            KeyboardButton(text="➕ Расширить"),
            KeyboardButton(text="📌 Тезисы")
        ],
        [
            KeyboardButton(text="🌍 Перевести"),
            KeyboardButton(text="⬅️ Назад")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_editor_result_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Копировать", callback_data="editor_copy")
    builder.button(text="📤 Отправить дальше", callback_data="editor_forward")
    builder.button(text="🔄 Ещё раз", callback_data="editor_again")
    builder.button(text="✏️ Переделать", callback_data="editor_refine")
    builder.button(text="🏠 Меню", callback_data="editor_menu")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_editor_language_keyboard() -> ReplyKeyboardMarkup:
    buttons = [
        [
            KeyboardButton(text="🇷🇺 Русский"),
            KeyboardButton(text="🇬🇧 Английский")
        ],
        [
            KeyboardButton(text="🇩🇪 Немецкий"),
            KeyboardButton(text="🇫🇷 Французский")
        ],
        [
            KeyboardButton(text="🇪🇸 Испанский"),
            KeyboardButton(text="🇨🇳 Китайский")
        ],
        [
            KeyboardButton(text="⬅️ Назад")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


# ==================== ТАРИФЫ ====================

def get_tariffs_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора тарифа."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⚪ FREE — 0 ₽", callback_data="tariff_free")
    builder.button(text="🟢 LITE — 499 ₽", callback_data="tariff_lite")
    builder.button(text="🔵 PRO — 1490 ₽", callback_data="tariff_pro")
    builder.button(text="🟣 BUSINESS — 3990 ₽", callback_data="tariff_business")
    builder.adjust(2, 2)
    return builder.as_markup()


# ==================== МАРКЕТПЛЕЙСЫ ====================

def get_marketplace_platform_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора площадки для маркетплейсов."""
    buttons = [
        [KeyboardButton(text="🛍️ Wildberries")],
        [KeyboardButton(text="🛒 Ozon")],
        [KeyboardButton(text="📦 Яндекс.Маркет")],
        [KeyboardButton(text="🛍️ AliExpress")],
        [KeyboardButton(text="🌐 Другое")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_marketplace_task_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора задачи для маркетплейсов."""
    buttons = [
        [KeyboardButton(text="📦 Карточка товара")],
        [KeyboardButton(text="📝 SEO-описание")],
        [KeyboardButton(text="🎯 Анализ конкурентов")],
        [KeyboardButton(text="💎 Улучшение названия")],
        [KeyboardButton(text="💬 Ответ клиенту")],
        [KeyboardButton(text="⬅️ Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


# ==================== ТОКЕНЫ ====================

def get_tokens_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура покупки токенов."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🪙 100 токенов — 49 ₽", callback_data="buy_tokens_100")
    builder.button(text="🪙 500 токенов — 199 ₽", callback_data="buy_tokens_500")
    builder.button(text="🪙 1000 токенов — 349 ₽", callback_data="buy_tokens_1000")
    builder.button(text="🪙 5000 токенов — 1499 ₽", callback_data="buy_tokens_5000")
    builder.button(text="🎁 Ввести промокод", callback_data="enter_promo")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def get_promo_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ввода промокода."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_tokens")
    return builder.as_markup()


# ==================== ОБЩИЕ ====================

def get_back_to_menu_keyboard() -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text="⬅️ Назад")]]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )
