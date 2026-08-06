"""Клавиатуры выбора моделей и параметров генерации."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from model_catalog import (
    GenerationKind,
    TOKEN_PACKAGES,
    get_image_model_profile,
    get_model,
    list_image_models,
    list_models,
)
from video_options import (
    default_video_selection,
    get_video_options,
    video_cost_tokens,
    video_min_cost_tokens,
)

TIER_ICON = {
    "economy": "⚡",
    "standard": "💎",
    "premium": "👑",
}


def _models_keyboard(
    kind: GenerationKind,
    prefix: str,
    *,
    image_mode: str | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    models = (
        list_image_models(image_mode or "text")
        if kind == GenerationKind.IMAGE
        else list_models(kind)
    )

    for model in models:
        icon = TIER_ICON.get(model.tier, "💎")

        if kind == GenerationKind.VIDEO:
            modes = "📝"
            if model.supports_input_image:
                modes += "+🖼"
            if model.requires_input_image:
                modes = "🖼"
            try:
                minimum = video_min_cost_tokens(model.key)
                price = f"от {minimum} 💎"
            except ValueError:
                price = f"{model.token_cost} 💎"
            text = f"{icon} {model.title} · {modes} · {price}"
        elif kind == GenerationKind.IMAGE:
            text = f"{model.title} · {model.token_cost} 💎"
        else:
            text = f"{icon} {model.title} · {model.token_cost} 💎"

        builder.button(
            text=text,
            callback_data=f"{prefix}:{model.key}",
        )

    builder.adjust(1)
    return builder.as_markup()


def get_text_models_keyboard() -> InlineKeyboardMarkup:
    return _models_keyboard(GenerationKind.TEXT, "newtext")


def get_image_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 По описанию",
                    callback_data="image_mode:text",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📸 По фотографии",
                    callback_data="image_mode:photo",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="generation_cancel",
                )
            ],
        ]
    )


def get_image_models_keyboard(
    mode: str | None = None,
) -> InlineKeyboardMarkup:
    return _models_keyboard(
        GenerationKind.IMAGE,
        "newimage",
        image_mode=mode,
    )


def get_image_model_card_keyboard(
    model_key: str,
    mode: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Выбрать эту модель",
                    callback_data=f"image_use:{mode}:{model_key}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ К списку моделей",
                    callback_data=f"image_models_back:{mode}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="generation_cancel",
                )
            ],
        ]
    )


def get_cartoonify_strength_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🙂 Лёгкий эффект · 110 💎",
                    callback_data="cartoonify_strength:light",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎨 Средний эффект · 110 💎",
                    callback_data="cartoonify_strength:medium",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧸 Сильный эффект · 110 💎",
                    callback_data="cartoonify_strength:strong",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="generation_cancel",
                )
            ],
        ]
    )


def get_video_models_keyboard() -> InlineKeyboardMarkup:
    return _models_keyboard(GenerationKind.VIDEO, "newvideo")


def get_video_duration_keyboard(model_key: str) -> InlineKeyboardMarkup:
    options = get_video_options(model_key)
    base = default_video_selection(model_key)
    rows = []
    for seconds in options.durations:
        selection = dict(base)
        selection["duration"] = seconds
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{seconds} сек · {video_cost_tokens(model_key, selection)} 💎",
                    callback_data=f"video_duration:{model_key}:{seconds}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="❌ Отмена", callback_data="generation_cancel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_generation_confirm_keyboard(
    *,
    video: bool = False,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="✅ Создать",
                callback_data="generation_confirm",
            )
        ]
    ]
    if video:
        rows.append(
            [
                InlineKeyboardButton(
                    text="✏️ Изменить параметры",
                    callback_data="video_change_duration",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="generation_cancel",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_input_image_keyboard(
    model_key: str,
    *,
    required: bool = False,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="📷 Отправить изображение",
                callback_data=f"media_image:{model_key}",
            )
        ]
    ]
    if not required:
        rows.append(
            [
                InlineKeyboardButton(
                    text="➡️ Продолжить без изображения",
                    callback_data=f"media_skip:{model_key}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="generation_cancel",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_token_packages_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, package in TOKEN_PACKAGES.items():
        builder.button(
            text=(
                f"{package['title']}: {package['tokens']} 💎 — "
                f"{package['price_rub']} ₽"
            ),
            callback_data=f"buytokens:{key}",
        )
    builder.adjust(1)
    return builder.as_markup()


def model_caption(
    model_key: str,
    duration: int | None = None,
    *,
    image_mode: str | None = None,
) -> str:
    model = get_model(model_key)
    icon = TIER_ICON.get(model.tier, "💎")
    if model.kind == GenerationKind.VIDEO:
        try:
            selection = default_video_selection(model_key)
            if duration is not None:
                selection["duration"] = duration
            cost = video_cost_tokens(model_key, selection)
        except (ValueError, KeyError):
            cost = model.cost_for_duration(duration)
    else:
        cost = model.cost_for_duration(duration)
    lines = [f"<b>{icon} {model.title}</b>"]

    if model.kind == GenerationKind.TEXT:
        if model.description:
            lines.append(model.description)
        lines.append("📝 Текстовые задачи")

    elif model.kind == GenerationKind.IMAGE:
        mode = image_mode or "text"
        profile = get_image_model_profile(model_key)
        mode_title = (
            "📝 Создание по описанию"
            if mode == "text"
            else "📸 Работа по фотографии"
        )
        description = profile.get(f"{mode}_description") or model.description
        use_cases = profile.get(f"{mode}_use_cases", ())
        note = profile.get(f"{mode}_note", "")

        lines.append(f"💎 Стоимость: <b>{cost} 💎</b>")
        lines.append(f"<b>{mode_title}</b>")
        if description:
            lines.append(description)
        if use_cases:
            lines.append("<b>Подходит для:</b>")
            lines.extend(f"• {item}" for item in use_cases)
        if note:
            lines.append(f"<b>Особенность:</b> {note}")
        lines.append(
            f"⚙️ Скорость: <b>{model.speed}</b> · "
            f"⭐ Качество: <b>{model.quality}</b>"
        )
        return "\n".join(lines)

    else:
        if model.description:
            lines.append(model.description)
        modes = "📝 По тексту"
        if model.supports_input_image:
            modes += " · 🖼 По фото"
        if model.requires_input_image:
            modes = "🖼 Только по фото"
        lines.append(modes)
        if duration is not None:
            lines.append(f"⏱ Длительность: <b>{duration} сек.</b>")

    lines.append(f"⚙️ Скорость: <b>{model.speed}</b>")
    lines.append(f"⭐ Качество: <b>{model.quality}</b>")
    if model.use_cases:
        lines.append("Подходит для: " + ", ".join(model.use_cases))
    lines.append(
        "💎 Стоимость после бесплатной попытки: "
        f"<b>{cost} 💎</b>"
    )
    return "\n".join(lines)
