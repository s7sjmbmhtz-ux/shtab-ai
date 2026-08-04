"""Клавиатуры выбора моделей и параметров генерации."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from model_catalog import GenerationKind, TOKEN_PACKAGES, get_model, list_models


def _models_keyboard(kind: GenerationKind, prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for model in list_models(kind):
        if kind == GenerationKind.VIDEO:
            modes = "📝"
            if model.supports_input_image:
                modes += " + 🖼"
            price = f"от {min(model.cost_for_duration(d) for d in model.video_durations)} 💎" if model.video_durations else f"{model.token_cost} 💎"
            text = f"{model.title} · {modes} · {price}"
        else:
            text = f"{model.title} · {model.token_cost} 💎"
        builder.button(text=text, callback_data=f"{prefix}:{model.key}")
    builder.adjust(1)
    return builder.as_markup()


def get_text_models_keyboard() -> InlineKeyboardMarkup:
    return _models_keyboard(GenerationKind.TEXT, "newtext")


def get_image_models_keyboard() -> InlineKeyboardMarkup:
    return _models_keyboard(GenerationKind.IMAGE, "newimage")


def get_video_models_keyboard() -> InlineKeyboardMarkup:
    return _models_keyboard(GenerationKind.VIDEO, "newvideo")


def get_video_duration_keyboard(model_key: str) -> InlineKeyboardMarkup:
    model = get_model(model_key)
    rows = [
        [InlineKeyboardButton(
            text=f"{seconds} сек · {model.cost_for_duration(seconds)} 💎",
            callback_data=f"video_duration:{model_key}:{seconds}",
        )]
        for seconds in model.video_durations
    ]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="generation_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_generation_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Создать", callback_data="video_confirm")],
        [InlineKeyboardButton(text="✏️ Изменить длительность", callback_data="video_change_duration")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="generation_cancel")],
    ])


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
    cost = model.cost_for_duration(duration)
    lines = [f"<b>{model.title}</b>"]
    if model.description:
        lines.append(model.description)
    if model.kind == GenerationKind.VIDEO:
        modes = "📝 По тексту"
        if model.supports_input_image:
            modes += " · 🖼 По фото"
        if model.requires_input_image:
            modes = "🖼 Только по фото"
        lines.append(modes)
        if duration is not None:
            lines.append(f"⏱ Длительность: <b>{duration} сек.</b>")
    lines.append(f"Стоимость после бесплатной попытки: <b>{cost} 💎</b>")
    return "\n".join(lines)
