"""Новый единый интерфейс текста, изображений, видео и баланса."""
from __future__ import annotations

import html
from typing import Any

from aiogram import Bot, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import db_manager, token_repository, user_repository
from generation_keyboards import (
    get_image_models_keyboard,
    get_input_image_keyboard,
    get_text_models_keyboard,
    get_token_packages_keyboard,
    get_video_models_keyboard,
    get_video_duration_keyboard,
    get_generation_confirm_keyboard,
    model_caption,
)
from generation_states import ImageGenerationStates, TextGenerationStates, VideoGenerationStates
from model_catalog import GenerationKind, TOKEN_PACKAGES, get_model
from services.billing_service import InsufficientBalanceError
from services.genapi_client import GenAPIError, genapi_client
from services.generation_service import generation_service
from settings import settings
from services.media_storage import LocalMedia, media_storage
from utils import logger

router = Router(name="generation_router")


async def _ensure_user(message_or_callback: Message | CallbackQuery) -> None:
    user = message_or_callback.from_user
    if user is None:
        return
    await user_repository.add_user(user.id, user.username, user.first_name)


async def _download_photo(message: Message, bot: Bot) -> LocalMedia:
    if not message.photo:
        raise ValueError("Фотография не найдена")
    return await media_storage.download_photo(bot, message.photo[-1].file_id)


def _extract_text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    output = data.get("output")
    if isinstance(output, str) and output.strip():
        return output.strip()
    if isinstance(output, dict):
        for key in ("text", "content", "response"):
            value = output.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    raise GenAPIError(f"Не удалось извлечь текст из ответа: {data}")


def _collect_urls(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        result.append(value)
    elif isinstance(value, list):
        for item in value:
            result.extend(_collect_urls(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in {"url", "video", "image", "file", "files", "output", "result", "images", "videos"}:
                result.extend(_collect_urls(item))
            elif isinstance(item, (dict, list)):
                result.extend(_collect_urls(item))
    return list(dict.fromkeys(result))


async def _complete_media_task(task: dict[str, Any]) -> dict[str, Any]:
    status = str(task.get("status", "")).lower()
    if status in {"success", "completed", "done"}:
        return task
    request_id = task.get("request_id") or task.get("id")
    if not request_id:
        raise GenAPIError(f"GenAPI не вернул request_id: {task}")
    return await genapi_client.wait_for_result(
        request_id,
        timeout=settings.GENAPI_POLL_TIMEOUT,
        interval=settings.GENAPI_POLL_INTERVAL,
    )


async def _send_long_text(message: Message, text: str) -> None:
    for start in range(0, len(text), 3900):
        await message.answer(html.escape(text[start:start + 3900]))


@router.message(Command("ai"))
@router.message(F.text == "🤖 AI Ассистент")
async def open_text_models(message: Message, state: FSMContext) -> None:
    await _ensure_user(message)
    await state.clear()
    await message.answer("Выберите текстовую модель:", reply_markup=get_text_models_keyboard())


@router.message(F.text == "🖼 Создать картинку")
async def open_image_models(message: Message, state: FSMContext) -> None:
    await _ensure_user(message)
    await state.clear()
    await message.answer("Выберите модель изображения:", reply_markup=get_image_models_keyboard())


@router.message(F.text == "🎬 Создать видео")
async def open_video_models(message: Message, state: FSMContext) -> None:
    await _ensure_user(message)
    await state.clear()
    await message.answer(
        "<b>🎬 Создание видео</b>\n\n"
        "📝 — работает по текстовому описанию\n"
        "🖼 — умеет оживлять фотографию\n\n"
        "После выбора модели бот предложит доступную длительность и заранее покажет точную стоимость.",
        reply_markup=get_video_models_keyboard(),
    )


@router.message(F.text == "💰 Мой баланс")
@router.message(Command("balance"))
async def show_balance(message: Message) -> None:
    await _ensure_user(message)
    balance = await token_repository.get_user_tokens(message.from_user.id)
    free = await db_manager.get_free_credits(message.from_user.id)
    await message.answer(
        "<b>Ваш баланс</b>\n\n"
        f"💎 Токены: <b>{balance}</b>\n"
        f"🎁 Бесплатный текст: <b>{free['text_left']}</b>\n"
        f"🎁 Бесплатное изображение: <b>{free['image_left']}</b>\n"
        f"🎁 Бесплатное видео: <b>{free['video_left']}</b>"
    )


@router.message(F.text == "💳 Купить кредиты")
@router.message(Command("buy"))
async def show_packages(message: Message) -> None:
    await _ensure_user(message)
    await message.answer("Выберите пакет токенов:", reply_markup=get_token_packages_keyboard())


@router.callback_query(F.data.startswith("newtext:"))
async def select_text_model(callback: CallbackQuery, state: FSMContext) -> None:
    model_key = callback.data.split(":", 1)[1]
    model = get_model(model_key)
    if model.kind != GenerationKind.TEXT:
        await callback.answer("Некорректная модель", show_alert=True)
        return
    await state.set_state(TextGenerationStates.chatting)
    await state.update_data(text_model=model_key, history=[])
    await callback.answer()
    await callback.message.answer(
        f"{model_caption(model_key)}\n\nОтправьте вопрос. Для выхода нажмите «🔙 Назад» или выберите другой раздел."
    )


@router.message(TextGenerationStates.chatting, F.text)
async def text_chat(message: Message, state: FSMContext) -> None:
    if message.text == "🔙 Назад":
        await state.clear()
        await message.answer("Диалог завершён.")
        return
    data = await state.get_data()
    model_key = data.get("text_model")
    history = list(data.get("history", []))[-12:]
    history.append({"role": "user", "content": message.text})
    status = await message.answer("⏳ Формирую ответ…")
    try:
        response = await generation_service.generate_text(message.from_user.id, model_key, history)
        text = _extract_text(response)
        history.append({"role": "assistant", "content": text})
        await state.update_data(history=history[-12:])
        await status.delete()
        await _send_long_text(message, text)
    except InsufficientBalanceError as exc:
        await status.edit_text(
            f"Недостаточно токенов. Нужно {exc.required} 💎, на балансе {exc.balance} 💎.",
            reply_markup=get_token_packages_keyboard(),
        )
    except Exception as exc:
        logger.exception("Ошибка текстовой генерации")
        await status.edit_text(f"Не удалось получить ответ: {html.escape(str(exc))}")


@router.callback_query(F.data.startswith("newimage:"))
async def select_image_model(callback: CallbackQuery, state: FSMContext) -> None:
    model_key = callback.data.split(":", 1)[1]
    model = get_model(model_key)
    if model.kind != GenerationKind.IMAGE:
        await callback.answer("Некорректная модель", show_alert=True)
        return
    await state.set_state(ImageGenerationStates.choosing_input)
    await state.update_data(model_key=model_key, input_image=None)
    await callback.answer()
    await callback.message.answer(
        f"{model_caption(model_key)}\n\nМожно отправить исходное фото или продолжить без него.",
        reply_markup=get_input_image_keyboard(model_key),
    )


@router.callback_query(F.data.startswith("newvideo:"))
async def select_video_model(callback: CallbackQuery, state: FSMContext) -> None:
    model_key = callback.data.split(":", 1)[1]
    model = get_model(model_key)
    if model.kind != GenerationKind.VIDEO:
        await callback.answer("Некорректная модель", show_alert=True)
        return
    await state.set_state(VideoGenerationStates.choosing_duration)
    await state.update_data(model_key=model_key, input_image=None)
    await callback.answer()
    await callback.message.answer(
        f"{model_caption(model_key)}\n\nВыберите длительность:",
        reply_markup=get_video_duration_keyboard(model_key),
    )


@router.callback_query(F.data.startswith("video_duration:"))
async def select_video_duration(callback: CallbackQuery, state: FSMContext) -> None:
    _, model_key, raw_duration = callback.data.split(":", 2)
    model = get_model(model_key)
    duration = int(raw_duration)
    if duration not in model.video_durations:
        await callback.answer("Недоступная длительность", show_alert=True)
        return
    await state.update_data(model_key=model_key, duration=duration, input_image=None)
    await callback.answer()
    if model.supports_input_image:
        await state.set_state(VideoGenerationStates.choosing_input)
        await callback.message.answer(
            f"{model_caption(model_key, duration)}\n\n"
            + ("Для этой модели изображение обязательно." if model.requires_input_image else "Можно отправить исходное фото или продолжить без него."),
            reply_markup=get_input_image_keyboard(model_key, required=model.requires_input_image),
        )
    else:
        await state.set_state(VideoGenerationStates.waiting_prompt)
        await callback.message.answer(f"{model_caption(model_key, duration)}\n\nВведите промпт для видео.")


@router.callback_query(F.data.startswith("media_image:"))
async def request_input_image(callback: CallbackQuery, state: FSMContext) -> None:
    model_key = callback.data.split(":", 1)[1]
    model = get_model(model_key)
    state_cls = ImageGenerationStates if model.kind == GenerationKind.IMAGE else VideoGenerationStates
    await state.set_state(state_cls.waiting_image)
    await state.update_data(model_key=model_key)
    await callback.answer()
    await callback.message.answer("Отправьте фотографию одним сообщением.")


@router.callback_query(F.data.startswith("media_skip:"))
async def skip_input_image(callback: CallbackQuery, state: FSMContext) -> None:
    model_key = callback.data.split(":", 1)[1]
    model = get_model(model_key)
    if model.requires_input_image:
        await callback.answer("Для этой модели фото обязательно", show_alert=True)
        return
    next_state = ImageGenerationStates.waiting_prompt if model.kind == GenerationKind.IMAGE else VideoGenerationStates.waiting_prompt
    await state.set_state(next_state)
    await state.update_data(model_key=model_key, input_image=None)
    await callback.answer()
    await callback.message.answer("Введите промпт.")


@router.message(ImageGenerationStates.waiting_image, F.photo)
@router.message(VideoGenerationStates.waiting_image, F.photo)
async def receive_input_image(message: Message, state: FSMContext, bot: Bot) -> None:
    media = await _download_photo(message, bot)
    data = await state.get_data()
    model = get_model(data["model_key"])
    next_state = ImageGenerationStates.waiting_prompt if model.kind == GenerationKind.IMAGE else VideoGenerationStates.waiting_prompt
    await state.update_data(input_image_path=media.path, input_image_name=media.filename, input_image_type=media.content_type)
    await state.set_state(next_state)
    await message.answer("Фото принято. Теперь введите промпт.")


@router.message(ImageGenerationStates.waiting_image)
@router.message(VideoGenerationStates.waiting_image)
async def require_photo(message: Message) -> None:
    await message.answer("Нужно отправить фотографию, не файл и не текст.")


@router.message(ImageGenerationStates.waiting_prompt, F.text)
@router.message(VideoGenerationStates.waiting_prompt, F.text)
async def generate_media(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    model = get_model(data["model_key"])
    if model.kind == GenerationKind.VIDEO:
        duration = int(data.get("duration") or model.default_duration or 5)
        cost = model.cost_for_duration(duration)
        await state.update_data(prompt=message.text, token_cost=cost)
        await state.set_state(VideoGenerationStates.confirming)
        await message.answer(
            f"<b>Подтверждение генерации</b>\n\n"
            f"{model_caption(model.key, duration)}\n"
            f"Режим: {'🖼 фото → видео' if data.get('input_image_path') else '📝 текст → видео'}\n\n"
            "Токены будут списаны только после подтверждения.",
            reply_markup=get_generation_confirm_keyboard(),
        )
        return
    await _execute_media(message, state, prompt=message.text)


@router.callback_query(F.data == "video_change_duration")
async def change_video_duration(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    model_key = data["model_key"]
    await state.set_state(VideoGenerationStates.choosing_duration)
    await callback.answer()
    await callback.message.answer("Выберите другую длительность:", reply_markup=get_video_duration_keyboard(model_key))


@router.callback_query(VideoGenerationStates.confirming, F.data == "video_confirm")
async def confirm_video(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _execute_media(callback.message, state, prompt=(await state.get_data())["prompt"])


async def _execute_media(message: Message, state: FSMContext, *, prompt: str) -> None:
    data = await state.get_data()
    model_key = data["model_key"]
    model = get_model(model_key)
    await state.set_state(ImageGenerationStates.processing if model.kind == GenerationKind.IMAGE else VideoGenerationStates.processing)
    status = await message.answer("⏳ Задача отправлена. Ожидаю результат…")
    charge = None
    try:
        overrides: dict[str, Any] = {}
        duration = data.get("duration")
        if model.kind == GenerationKind.VIDEO and duration:
            # GenAPI использует разные типы значения длительности у разных моделей.
            overrides["duration"] = f"{duration}s" if model_key in {"veo-3-1", "veo-3-1-lite", "luma-ray2"} else duration
        charge, task = await generation_service.create_media_task(
            message.chat.id,
            model_key,
            prompt,
            input_image=(LocalMedia(data["input_image_path"], data["input_image_name"], data["input_image_type"]) if data.get("input_image_path") else None),
            overrides=overrides,
            token_cost=data.get("token_cost"),
        )
        result = await _complete_media_task(task)
        urls = _collect_urls(result)
        if not urls:
            raise GenAPIError(f"В результате нет ссылки на файл: {result}")
        await status.delete()
        if model.kind == GenerationKind.IMAGE:
            for url in urls[:4]:
                await message.answer_photo(url, caption=f"✅ Готово · {model.title}")
        else:
            await message.answer_video(urls[0], caption=f"✅ Готово · {model.title} · {duration} сек.", supports_streaming=True)
        await media_storage.remove(data.get("input_image_path"))
        await state.clear()
    except InsufficientBalanceError as exc:
        await media_storage.remove(data.get("input_image_path"))
        await state.clear()
        await status.edit_text(
            f"Недостаточно токенов. Нужно {exc.required} 💎, на балансе {exc.balance} 💎.",
            reply_markup=get_token_packages_keyboard(),
        )
    except Exception as exc:
        logger.exception("Ошибка медиагенерации")
        if charge is not None:
            from services.billing_service import billing_service
            await billing_service.refund(charge, "Ошибка получения результата")
        await media_storage.remove(data.get("input_image_path"))
        await state.clear()
        await status.edit_text(f"Генерация не выполнена: {html.escape(str(exc))}")


@router.callback_query(F.data == "generation_cancel")
async def cancel_generation(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await media_storage.remove(data.get("input_image_path"))
    await state.clear()
    await callback.answer("Отменено")
    await callback.message.answer("Генерация отменена.")
