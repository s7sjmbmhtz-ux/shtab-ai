from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from models import TextOperation


# ==================== ГЛАВНОЕ МЕНЮ ====================

def get_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню с кнопками-действиями."""
    buttons = [
        [
            KeyboardButton(text="🎬 Создать видео"),
            KeyboardButton(text="🖼 Создать картинку")
        ],
        [
            KeyboardButton(text="🏢 Продажи"),
            KeyboardButton(text="📈 Маркетинг")
        ],
        [
            KeyboardButton(text="🤖 AI Ассистент"),
            KeyboardButton(text="🛒 Маркетплейсы")
        ],
        [
            KeyboardButton(text="💰 Мой баланс"),
            KeyboardButton(text="💳 Купить кредиты")
        ],
        [
            KeyboardButton(text="💎 Тарифы"),
            KeyboardButton(text="📞 Поддержка")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_back_to_menu_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой назад."""
    buttons = [[KeyboardButton(text="🔙 Назад")]]
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
            KeyboardButton(text="🔙 Назад")
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
        [KeyboardButton(text="🔙 Назад")]
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
            KeyboardButton(text="🔙 Назад")
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
        [KeyboardButton(text="🔙 Назад")]
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
        [KeyboardButton(text="🔙 Назад")]
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
        [KeyboardButton(text="🔙 Назад")]
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
        [KeyboardButton(text="🔙 Назад")]
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
        [KeyboardButton(text="🔙 Назад")]
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
        [KeyboardButton(text="🔙 Назад")]
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
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_video_models_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора модели для видео."""
    buttons = [
        [KeyboardButton(text="⚡ LTX Video — 5 токенов/сек")],
        [KeyboardButton(text="🎬 CogVideoX — 12 токенов/сек")],
        [KeyboardButton(text="🎥 Kling Standard — 15 токенов/сек")],
        [KeyboardButton(text="🌈 Luma Ray2 — 20 токенов/сек")],
        [KeyboardButton(text="🌟 Kling Pro — 18 токенов/сек")],
        [KeyboardButton(text="🌟 Veo 3.1 Lite — 12 токенов/сек")],
        [KeyboardButton(text="💎 Veo 3.1 — 50 токенов/сек")],
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_video_duration_keyboard(max_duration: int = 15) -> ReplyKeyboardMarkup:
    """Клавиатура выбора длительности видео (5, 10, 15 сек)."""
    buttons = []
    
    buttons.append([KeyboardButton(text="5 секунд")])
    buttons.append([KeyboardButton(text="10 секунд")])
    
    if max_duration >= 15:
        buttons.append([KeyboardButton(text="15 секунд")])
    
    buttons.append([KeyboardButton(text="🔙 Назад")])
    
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_skip_photo_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура пропуска фото."""
    buttons = [
        [KeyboardButton(text="⏭ Пропустить фото")],
        [KeyboardButton(text="🔙 Назад")]
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
            KeyboardButton(text="🔙 Назад")
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
            KeyboardButton(text="🔙 Назад")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


# ==================== ТАРИФЫ И ТОКЕНЫ ====================

def get_tariffs_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора тарифа."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⚪ FREE — 0 ₽", callback_data="tariff_free")
    builder.button(text="🟢 LITE — 299 ₽", callback_data="tariff_lite")
    builder.button(text="🔵 PRO — 799 ₽", callback_data="tariff_pro")
    builder.button(text="🟣 BUSINESS — 1999 ₽", callback_data="tariff_business")
    builder.adjust(2, 2)
    return builder.as_markup()


def get_tariff_and_tokens_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора между тарифами и токенами."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Подписки", callback_data="show_subscriptions")
    builder.button(text="🪙 Пакеты токенов", callback_data="show_tokens")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_back_to_tariffs_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура возврата к выбору тарифов/токенов."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад к выбору", callback_data="back_to_tariffs")
    return builder.as_markup()


def get_back_to_subscriptions_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура возврата к подпискам."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 К подпискам", callback_data="show_subscriptions")
    return builder.as_markup()


def get_tokens_packages_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с пакетами токенов."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🪙 50 токенов — 69 ₽", callback_data="buy_tokens_50")
    builder.button(text="🪙 150 токенов — 179 ₽", callback_data="buy_tokens_150")
    builder.button(text="🪙 500 токенов — 499 ₽", callback_data="buy_tokens_500")
    builder.button(text="🪙 1500 токенов — 1299 ₽", callback_data="buy_tokens_1500")
    builder.button(text="🪙 5000 токенов — 3999 ₽", callback_data="buy_tokens_5000")
    builder.button(text="🔙 Назад", callback_data="back_to_tariffs")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_tokens_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура покупки токенов (упрощённая)."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🪙 50 токенов — 69 ₽", callback_data="buy_tokens_50")
    builder.button(text="🪙 150 токенов — 179 ₽", callback_data="buy_tokens_150")
    builder.button(text="🪙 500 токенов — 499 ₽", callback_data="buy_tokens_500")
    builder.button(text="🪙 1500 токенов — 1299 ₽", callback_data="buy_tokens_1500")
    builder.button(text="🪙 5000 токенов — 3999 ₽", callback_data="buy_tokens_5000")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_promo_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для ввода промокода."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_tariffs")
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
        [KeyboardButton(text="🔙 Назад")]
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
        [KeyboardButton(text="🔙 Назад")]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        one_time_keyboard=False
    )


# ==================== РЕФЕРАЛЬНАЯ СИСТЕМА ====================

def get_referral_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для реферальной системы."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Поделиться ссылкой", callback_data="share_referral")
    builder.button(text="📊 Мои рефералы", callback_data="my_referrals")
    builder.button(text="💰 Вывести", callback_data="withdraw_referral")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(2, 1, 1)
    return builder.as_markup()
