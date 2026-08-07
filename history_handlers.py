"""История пользовательских генераций и безопасный повтор."""
from __future__ import annotations

import html
import json
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import db_manager
from generation_keyboards import (
    get_generation_confirm_keyboard,
    get_image_mode_keyboard,
    get_video_models_keyboard,
)
from generation_states import ImageGenerationStates, VideoGenerationStates
from model_catalog import GenerationKind, get_model
from services.funnel_service import funnel_service
from services.generation_service import generation_service
from video_options import build_video_overrides, video_cost_tokens

router = Router(name="history_router")

KIND_LABELS = {
    "text": "💬 Текст",
    "image": "🖼 Изображение",
    "video": "🎬 Видео",
}
STATUS_LABELS = {
    "processing": "⏳ выполняется",
    "completed": "✅ готово",
    "refunded": "↩️ возвращено",
}


def _list_keyboard(rows: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    for row in rows:
        title = KIND_LABELS.get(str(row["kind"]), str(row["kind"]))
        prompt = str(row.get("prompt") or "Без описания").replace("\n", " ")[:32]
        buttons.append([
            InlineKeyboardButton(
                text=f"{title} · {prompt}",
                callback_data=f"history:view:{row['id']}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _card_keyboard(history_id: int, status: str) -> InlineKeyboardMarkup:
    rows = []
    if status == "completed":
        rows.append([
            InlineKeyboardButton(
                text="🔁 Повторить",
                callback_data=f"history:repeat:{history_id}",
            )
        ])
    rows.append([InlineKeyboardButton(text="⬅️ К истории", callback_data="history:list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _decode_settings(raw: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(raw or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def _show_list(target: Message) -> None:
    rows = await db_manager.list_generation_history(target.from_user.id, 10)
    if not rows:
        await target.answer(
            "<b>🕘 Мои генерации</b>\n\n"
            "Здесь появятся новые тексты, изображения и видео."
        )
        return
    await target.answer(
        "<b>🕘 Мои генерации</b>\n\nПоследние 10 запросов:",
        reply_markup=_list_keyboard(rows),
    )


@router.message(Command("history"))
@router.message(F.text == "🕘 Мои генерации")
async def history_list(message: Message) -> None:
    await _show_list(message)


@router.callback_query(F.data == "history:list")
async def history_list_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    rows = await db_manager.list_generation_history(callback.from_user.id, 10)
    text = "<b>🕘 Мои генерации</b>\n\nПоследние 10 запросов:"
    if not rows:
        text = "<b>🕘 Мои генерации</b>\n\nИстория пока пуста."
    await callback.message.edit_text(
        text,
        reply_markup=_list_keyboard(rows) if rows else None,
    )


@router.callback_query(F.data.startswith("history:view:"))
async def history_card(callback: CallbackQuery) -> None:
    try:
        history_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Некорректная запись", show_alert=True)
        return
    row = await db_manager.get_generation_history(
        history_id,
        user_id=callback.from_user.id,
    )
    if not row:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    try:
        title = get_model(str(row["model_key"])).title
    except (KeyError, ValueError):
        title = str(row["model_key"])
    prompt = html.escape(str(row.get("prompt") or "—")[:1000])
    preview = html.escape(str(row.get("response_preview") or "")[:1200])
    text = (
        f"<b>{KIND_LABELS.get(str(row['kind']), str(row['kind']))}</b>\n\n"
        f"Модель: <b>{html.escape(title)}</b>\n"
        f"Статус: <b>{STATUS_LABELS.get(str(row['status']), html.escape(str(row['status'])))}</b>\n"
        f"Дата: <code>{str(row.get('created_at') or '')[:16]}</code>\n\n"
        f"<b>Запрос:</b>\n{prompt}"
    )
    if preview:
        text += f"\n\n<b>Результат:</b>\n{preview}"
    await callback.answer()
    await callback.message.edit_text(
        text,
        reply_markup=_card_keyboard(history_id, str(row["status"])),
    )


@router.callback_query(F.data.startswith("history:repeat:"))
async def repeat_generation(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        history_id = int(callback.data.rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Некорректная запись", show_alert=True)
        return
    row = await db_manager.get_generation_history(history_id, user_id=callback.from_user.id)
    if not row:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    model_key = str(row["model_key"])
    try:
        model = get_model(model_key)
    except (KeyError, ValueError):
        await callback.answer("Эта модель больше недоступна", show_alert=True)
        return
    if not db_manager.is_model_enabled_cached(model_key):
        await callback.answer("Модель временно отключена", show_alert=True)
        return

    prompt = str(row.get("prompt") or "")
    settings_data = _decode_settings(row.get("settings_json"))
    await funnel_service.track(
        callback.from_user.id,
        "repeat_generation",
        {"history_id": history_id, "model_key": model_key},
    )

    if model.kind == GenerationKind.TEXT:
        await callback.answer("Повтор запущен")
        status = await callback.message.answer("⏳ Формирую новый ответ…")
        try:
            response = await generation_service.generate_text(
                callback.from_user.id,
                model_key,
                [{"role": "user", "content": prompt}],
            )
            preview = generation_service._text_preview(response) or "Ответ получен."
            await status.edit_text(html.escape(preview[:3000]))
        except Exception as exc:
            await status.edit_text(
                "Не удалось повторить запрос. Списание возвращено; попробуйте позже."
            )
        return

    if settings_data.get("has_input_image"):
        await state.clear()
        if model.kind == GenerationKind.IMAGE:
            await state.set_state(ImageGenerationStates.choosing_mode)
            keyboard = get_image_mode_keyboard()
        else:
            keyboard = get_video_models_keyboard()
        await callback.answer()
        await callback.message.answer(
            "Для этого запроса использовалась фотография. Telegram не позволяет "
            "безопасно восстановить локальный файл, поэтому загрузите фото заново.",
            reply_markup=keyboard,
        )
        return

    data: dict[str, Any] = {
        "model_key": model_key,
        "prompt": prompt,
        "input_image": None,
        "input_image_path": None,
        "image_mode": settings_data.get("image_mode") or "text",
        "media_overrides": dict(settings_data.get("media_overrides") or {}),
    }
    if model.kind == GenerationKind.VIDEO:
        selection = settings_data.get("video_selection")
        if isinstance(selection, dict) and selection:
            data["video_selection"] = selection
            data["duration"] = selection.get("duration")
            data["token_cost"] = video_cost_tokens(model_key, selection)
            data["media_overrides"] = build_video_overrides(model_key, selection)
        await state.set_state(VideoGenerationStates.confirming)
    else:
        data["token_cost"] = db_manager.get_model_price_cached(model_key, model.token_cost)
        await state.set_state(ImageGenerationStates.confirming)
    await state.update_data(**data)
    await callback.answer("Проверьте и подтвердите")
    await callback.message.answer(
        f"<b>Повтор генерации · {html.escape(model.title)}</b>\n\n"
        f"Запрос: {html.escape(prompt[:1000])}\n\n"
        "Будет создан новый вариант, стоимость спишется после подтверждения.",
        reply_markup=get_generation_confirm_keyboard(video=model.kind == GenerationKind.VIDEO),
    )
