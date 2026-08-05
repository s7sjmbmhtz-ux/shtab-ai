"""Клавиатуры выбора моделей и параметров генерации."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from model_catalog import GenerationKind, TOKEN_PACKAGES, get_model, list_models

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
    for model in list_models(kind):
        if kind == GenerationKind.IMAGE:
            text_models = {"nano-banana-lite", "nano-banana-2"}
            photo_models = {"nano-banana-lite", "nano-banana-2", "flux-kontext", "qwen-image-edit-plus", "cartoonify"}
            allowed = photo_models if image_mode == "photo" else text_models
            if model.key not in allowed:
                continue
        icon = TIER_ICON.get(model.tier, "💎")
        if kind == GenerationKind.VIDEO:
            modes = "📝"
            if model.supports_input_image:
                modes += "+🖼"
            if model.requires_input_image:
                modes = "🖼"
            if model.video_durations:
                minimum = min(model.cost_for_duration(d) for d in model.video_durations)
                price = f"от {minimum} 💎"
            else:
                price = f"{model.token_cost} 💎"
            text = f"{icon} {model.title} · {modes} · {price}"
        elif kind == GenerationKind.IMAGE:
            text = f"{model.title} · {model.token_cost} 💎"
        else:
            text = f"{icon} {model.title} · {model.token_cost} 💎"
        builder.button(text=text, callback_data=f"{prefix}:{model.key}")
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


def get_video_models_keyboard() -> InlineKeyboardMarkup:
    return _models_keyboard(GenerationKind.VIDEO, "newvideo")


def get_video_duration_keyboard(model_key: str) -> InlineKeyboardMarkup:
    model = get_model(model_key)
    rows = [[InlineKeyboardButton(
        text=f"{seconds} сек · {model.cost_for_duration(seconds)} 💎",
        callback_data=f"video_duration:{model_key}:{seconds}",
    )] for seconds in model.video_durations]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="generation_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_generation_confirm_keyboard(*, video: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="✅ Создать", callback_data="generation_confirm")]]
    if video:
        rows.append([InlineKeyboardButton(text="✏️ Изменить длительность", callback_data="video_change_duration")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="generation_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_input_image_keyboard(model_key: str, *, required: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📷 Отправить изображение", callback_data=f"media_image:{model_key}")]]
    if not required:
        rows.append([InlineKeyboardButton(text="➡️ Продолжить без изображения", callback_data=f"media_skip:{model_key}")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="generation_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_token_packages_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, package in TOKEN_PACKAGES.items():
        builder.button(
            text=f"{package['title']}: {package['tokens']} 💎 — {package['price_rub']} ₽",
            callback_data=f"buytokens:{key}",
        )
    builder.adjust(1)
    return builder.as_markup()


def model_caption(model_key: str, duration: int | None = None) -> str:
    model = get_model(model_key)
    icon = TIER_ICON.get(model.tier, "💎")
    cost = model.cost_for_duration(duration)
    lines = [f"<b>{icon} {model.title}</b>"]

    if model.kind == GenerationKind.TEXT:
        if model.description:
            lines.append(model.description)
        lines.append("📝 Текстовые задачи")
    elif model.kind == GenerationKind.IMAGE:
        return (
            f"<b>{model.title}</b>\n"
            f"💎 Стоимость после бесплатной попытки: <b>{cost} 💎</b>"
        )
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
    lines.append(f"💎 Стоимость после бесплатной попытки: <b>{cost} 💎</b>")
    return "\n".join(lines)
