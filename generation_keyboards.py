"""Клавиатуры выбора моделей и режима генерации."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from model_catalog import GenerationKind, TOKEN_PACKAGES, get_model, list_models


def _models_keyboard(kind: GenerationKind, prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for model in list_models(kind):
        builder.button(
            text=f"{model.title} · {model.token_cost} 💎",
            callback_data=f"{prefix}:{model.key}",
        )
    builder.adjust(1)
    return builder.as_markup()


def get_text_models_keyboard() -> InlineKeyboardMarkup:
    return _models_keyboard(GenerationKind.TEXT, "newtext")


def get_image_models_keyboard() -> InlineKeyboardMarkup:
    return _models_keyboard(GenerationKind.IMAGE, "newimage")


def get_video_models_keyboard() -> InlineKeyboardMarkup:
    return _models_keyboard(GenerationKind.VIDEO, "newvideo")


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


def model_caption(model_key: str) -> str:
    model = get_model(model_key)
    return f"<b>{model.title}</b>\nСтоимость после бесплатной попытки: <b>{model.token_cost} 💎</b>"
