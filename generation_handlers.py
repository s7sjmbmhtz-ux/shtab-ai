"""Новый единый интерфейс текста, изображений, видео и баланса."""
from __future__ import annotations

import asyncio
import contextlib
import html
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import db_manager, token_repository, user_repository
from generation_keyboards import (
    get_cartoonify_strength_keyboard,
    get_generation_confirm_keyboard,
    get_image_mode_keyboard,
    get_image_model_card_keyboard,
    get_image_models_keyboard,
    get_input_image_keyboard,
    get_text_model_card_keyboard,
    get_text_models_keyboard,
    get_token_packages_keyboard,
    get_video_model_card_keyboard,
    get_video_models_keyboard,
    model_caption,
)
from generation_states import (
    ImageGenerationStates,
    TextGenerationStates,
    VideoGenerationStates,
)
from model_catalog import (
    GenerationKind,
    get_model,
    image_model_supports_mode,
)
from model_descriptions import (
    image_model_card,
    text_model_card,
    video_model_card,
)
from services.billing_service import InsufficientBalanceError, billing_service
from services.genapi_client import GenAPIError, GenAPIHTTPError, genapi_client
from services.generation_service import generation_service
from services.generation_guard import generation_guard
from services.media_storage import LocalMedia, media_storage
from services.public_media_service import PublicMediaError, public_media_service
from settings import settings
from video_options import (
    build_video_overrides,
    default_video_selection,
    get_video_options,
    selection_labels,
    validate_option,
    video_cost_tokens,
)
from utils import logger

router = Router(name="generation_router")

_BOT_USERNAME = settings.BOT_USERNAME.lstrip("@")

BRAND_FOOTER = (
    "\n\n────────────\n"
    "✨ Сгенерировано в <b>ШТАБ AI</b>\n"
    f"👉 https://t.me/{_BOT_USERNAME}"
)

IMAGE_BRAND_CAPTION = f"✨ Сгенерировано в ШТАБ AI\n👉 @{_BOT_USERNAME}"
VIDEO_BRAND_CAPTION = f"🎬 Видео создано в ШТАБ AI\n👉 @{_BOT_USERNAME}"

MAX_CHAT_HISTORY_MESSAGES = 10
MAX_CHAT_HISTORY_CHARS = 18_000
MAX_CHAT_MESSAGE_CHARS = 6_000


async def _ensure_user(message_or_callback: Message | CallbackQuery) -> None:
    user = message_or_callback.from_user
    if user is None:
        return
    await user_repository.add_user(
        user.id,
        user.username,
        user.first_name,
    )
    await user_repository.update_activity(user.id)


def _current_model_price(model_key: str) -> int:
    model = get_model(model_key)
    return db_manager.get_model_price_cached(model.key, model.token_cost)


def _trim_chat_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    """Ограничивает повторную отправку длинной истории и себестоимость чата."""
    selected: list[dict[str, str]] = []
    used_chars = 0
    for item in reversed(history[-MAX_CHAT_HISTORY_MESSAGES:]):
        role = str(item.get("role") or "")
        content = str(item.get("content") or "")[:MAX_CHAT_MESSAGE_CHARS]
        if not role or not content:
            continue
        if selected and used_chars + len(content) > MAX_CHAT_HISTORY_CHARS:
            break
        selected.append({"role": role, "content": content})
        used_chars += len(content)
    return list(reversed(selected))


def _free_model_key(kind: GenerationKind) -> str:
    return {
        GenerationKind.TEXT: settings.FREE_TEXT_MODEL,
        GenerationKind.IMAGE: settings.FREE_IMAGE_MODEL,
        GenerationKind.VIDEO: settings.FREE_VIDEO_MODEL,
    }[kind]


def _free_credit_field(kind: GenerationKind) -> str:
    return {
        GenerationKind.TEXT: "text_left",
        GenerationKind.IMAGE: "image_left",
        GenerationKind.VIDEO: "video_left",
    }[kind]


async def _free_trial_remaining(user_id: int, model_key: str) -> int | None:
    """Возвращает остаток только для назначенной бесплатной модели."""
    model = get_model(model_key)
    if model.key != _free_model_key(model.kind):
        return None
    credits = await db_manager.get_free_credits(user_id)
    return max(0, int(credits[_free_credit_field(model.kind)]))


async def _free_trial_notice(user_id: int, model_key: str) -> str:
    remaining = await _free_trial_remaining(user_id, model_key)
    if remaining is None:
        return ""
    if remaining > 0:
        return f"\n\n🎁 Бесплатных попыток для этой модели: <b>{remaining}</b>."
    return (
        "\n\n⚠️ <b>Ваши бесплатные попытки закончились.</b>\n"
        "Дальнейшая генерация оплачивается в 💎. "
        "Удаление переписки и повторный /start попытки не восстанавливают."
    )


async def _insufficient_balance_message(
    user_id: int,
    model_key: str,
    exc: InsufficientBalanceError,
) -> str:
    remaining = await _free_trial_remaining(user_id, model_key)
    prefix = ""
    if remaining == 0:
        prefix = (
            "🎁 <b>Ваши бесплатные попытки закончились.</b>\n"
            "Они закреплены за Telegram-аккаунтом и повторно не выдаются.\n\n"
        )
    return (
        f"{prefix}Недостаточно токенов. "
        f"Нужно {exc.required} 💎, "
        f"на балансе {exc.balance} 💎."
    )


def _free_count_label(value: int) -> str:
    value = max(0, int(value))
    return f"<b>{value}</b>" if value > 0 else "<b>0 — закончились</b>"


async def _download_photo(
    message: Message,
    bot: Bot,
    *,
    max_dimension_sum: int | None = None,
) -> tuple[LocalMedia, int, int]:
    if not message.photo:
        raise ValueError("Фотография не найдена")

    photos = list(message.photo)
    if max_dimension_sum is not None:
        suitable = [
            photo for photo in photos
            if int(photo.width) + int(photo.height) <= max_dimension_sum
        ]
        # Telegram обычно присылает несколько размеров одного фото. Берём
        # максимально качественный вариант, который проходит лимит модели.
        selected = max(
            suitable or photos,
            key=lambda photo: int(photo.width) * int(photo.height),
        )
        if not suitable:
            selected = min(
                photos,
                key=lambda photo: int(photo.width) + int(photo.height),
            )
    else:
        selected = max(
            photos,
            key=lambda photo: int(photo.width) * int(photo.height),
        )

    media = await media_storage.download_photo(bot, selected.file_id)
    return media, int(selected.width), int(selected.height)


def _video_aspect_overrides(
    model_key: str,
    width: int | None,
    height: int | None,
) -> dict[str, str]:
    """Подбирает формат видео по ориентации загруженного кадра."""
    if not width or not height or width == height:
        return {}

    vertical = height > width
    if model_key == "runway-gen4":
        # Для Runway Gen-4 в переданной схеме подтверждён только 1280:720.
        return {"ratio": "1280:720"}

    aspect_models = {
        "ltx-2-3",
        "kling-o3",
        "kling-v3",
        "veo-3-1-lite",
        "veo-3-1",
        "luma-ray2",
    }
    if model_key in aspect_models:
        return {"aspect_ratio": "9:16" if vertical else "16:9"}

    return {}


def _video_settings_text(model_key: str, selection: dict[str, Any]) -> str:
    model = get_model(model_key)
    labels = selection_labels(model_key, selection)
    cost = video_cost_tokens(model_key, selection)
    return (
        f"<b>🎬 {model.title}</b>\n\n"
        "Выберите параметры генерации:\n\n"
        f"Качество: <b>{labels['quality']}</b>\n"
        f"Разрешение: <b>{labels['resolution']}</b>\n"
        f"Длительность: <b>{labels['duration']}</b>\n"
        f"Звук: <b>{labels['audio']}</b>\n"
        f"Формат: <b>{labels['aspect']}</b>\n\n"
        f"Стоимость: <b>{cost} 💎</b>"
    )


def _video_settings_keyboard(model_key: str, selection: dict[str, Any]) -> InlineKeyboardMarkup:
    options = get_video_options(model_key)
    rows: list[list[InlineKeyboardButton]] = []

    def add_choice_row(field: str, choices: tuple[Any, ...]) -> None:
        if len(choices) <= 1:
            return
        rows.append([
            InlineKeyboardButton(
                text=("✅ " if selection.get(field) == choice.value else "") + choice.label,
                callback_data=f"video_option:{model_key}:{field}:{choice.value}",
            )
            for choice in choices
        ])

    add_choice_row("quality", options.qualities)
    add_choice_row("resolution", options.resolutions)

    if len(options.durations) > 1:
        rows.append([
            InlineKeyboardButton(
                text=("✅ " if selection.get("duration") == seconds else "") + f"{seconds} сек",
                callback_data=f"video_option:{model_key}:duration:{seconds}",
            )
            for seconds in options.durations
        ])

    add_choice_row("audio", options.audio_choices)
    add_choice_row("aspect", options.aspects)
    rows.append([InlineKeyboardButton(
        text="➡️ Продолжить",
        callback_data=f"video_options_continue:{model_key}",
    )])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="generation_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_video_settings(callback: CallbackQuery, state: FSMContext, *, edit: bool) -> None:
    data = await state.get_data()
    model_key = data["model_key"]
    selection = dict(data.get("video_selection") or default_video_selection(model_key))
    await state.update_data(video_selection=selection, duration=selection.get("duration"))
    text = _video_settings_text(model_key, selection)
    keyboard = _video_settings_keyboard(model_key, selection)
    if edit:
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
            return
        except TelegramBadRequest:
            pass
    await callback.message.answer(text, reply_markup=keyboard)


async def _continue_video_flow(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    model_key = data["model_key"]
    model = get_model(model_key)
    selection = dict(data.get("video_selection") or default_video_selection(model_key))
    labels = selection_labels(model_key, selection)
    await state.update_data(
        video_selection=selection,
        duration=selection.get("duration"),
        media_overrides=build_video_overrides(model_key, selection),
    )

    if model.supports_input_image:
        await state.set_state(VideoGenerationStates.choosing_input)
        hint = (
            "Для этой модели изображение обязательно."
            if model.requires_input_image
            else "Можно отправить исходное фото или продолжить без него."
        )
        await callback.message.answer(
            f"<b>{model.title}</b>\n\n"
            f"Качество: {labels['quality']}\n"
            f"Разрешение: {labels['resolution']}\n"
            f"Длительность: {labels['duration']}\n"
            f"Звук: {labels['audio']}\n"
            f"Формат: {labels['aspect']}\n\n"
            f"{hint}",
            reply_markup=get_input_image_keyboard(model_key, required=model.requires_input_image),
        )
        return

    await state.set_state(VideoGenerationStates.waiting_prompt)
    await callback.message.answer(f"<b>{model.title}</b>\n\nВведите промпт для видео.")


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

    raise GenAPIError(
        f"Не удалось извлечь текст из ответа: {data}"
    )


RESULT_URL_KEYS = {
    "url",
    "video",
    "image",
    "file",
    "files",
    "output",
    "result",
    "response",
    "images",
    "videos",
    "data",
    "full_response",
}


def _collect_urls(value: Any) -> list[str]:
    """Собирает ссылки только из полей результата.

    GenAPI возвращает входное фото внутри ``parameters``. Старый обход
    заходил туда и отправлял пользователю исходник вместе с результатом.
    """
    result: list[str] = []

    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            result.append(value)
    elif isinstance(value, list):
        for item in value:
            result.extend(_collect_urls(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in RESULT_URL_KEYS:
                result.extend(_collect_urls(item))

    return list(dict.fromkeys(result))


def _format_elapsed(seconds: int) -> str:
    minutes, rest = divmod(max(0, seconds), 60)
    if minutes:
        return f"{minutes} мин {rest:02d} сек"
    return f"{rest} сек"


async def _animate_generation_status(
    status: Message,
    model_title: str,
) -> None:
    frames = (
        "▰▱▱▱▱",
        "▰▰▱▱▱",
        "▰▰▰▱▱",
        "▰▰▰▰▱",
        "▰▰▰▰▰",
        "▱▰▰▰▰",
        "▱▱▰▰▰",
        "▱▱▱▰▰",
    )
    started = asyncio.get_running_loop().time()
    step = 0

    while True:
        await asyncio.sleep(8)
        elapsed = int(asyncio.get_running_loop().time() - started)

        if elapsed < 24:
            stage = "🧠 Модель обрабатывает запрос"
        elif elapsed < 60:
            stage = "🎨 Создаю изображение"
        else:
            stage = (
                "⌛ Генерация идёт дольше обычного, "
                "но запрос ещё выполняется"
            )

        text = (
            f"<b>{model_title}</b>\n\n"
            f"{frames[step % len(frames)]}\n"
            f"{stage}\n"
            f"Прошло: <b>{_format_elapsed(elapsed)}</b>"
        )
        step += 1

        try:
            await status.edit_text(text)
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                continue
            return
        except Exception:
            return


async def _stop_progress(task: asyncio.Task[None] | None) -> None:
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task


async def _record_generation_error(
    user_id: int,
    model_key: str,
    prompt: str,
    exc: Exception,
) -> None:
    """Сохраняет безопасную запись об ошибке для админ-панели."""
    try:
        model = get_model(model_key)
        async with db_manager.connection() as conn:
            await conn.execute(
                """INSERT INTO requests
                   (user_id, section, tool, input_data, prompt, provider, model, status, error_message)
                   VALUES (?, ?, ?, '{}', ?, 'genapi', ?, 'error', ?)""",
                (
                    user_id,
                    model.kind.value,
                    model_key,
                    (prompt or "")[:4000],
                    model_key,
                    f"{type(exc).__name__}: {exc}"[:4000],
                ),
            )
            await conn.commit()
    except Exception:
        logger.exception("Не удалось записать ошибку генерации в БД")


def _friendly_media_error(exc: Exception) -> str:
    lowered = str(exc).lower()

    if isinstance(exc, PublicMediaError):
        return (
            "🌐 <b>Фото недоступно для внешней модели</b>\n\n"
            "Бот не смог открыть временную ссылку на загруженное фото через "
            "публичный домен. Проверьте в BotHost:\n"
            "• включено «Использовать домен»;\n"
            "• порт веб-приложения совпадает с PORT;\n"
            "• MEDIA_PUBLIC_BASE_URL содержит ваш HTTPS-домен без / в конце.\n\n"
            "💎 Токены не списаны."
        )

    if (
        "http 503" in lowered
        or "http 502" in lowered
        or "http 504" in lowered
        or "сервис сейчас недоступен" in lowered
        or "не удалось подключиться к genapi" in lowered
    ):
        return (
            "🛠 <b>Сервис генерации временно недоступен</b>\n\n"
            "Бот уже повторил запрос несколько раз, но GenAPI пока не отвечает. "
            "Попробуйте запустить генерацию чуть позже.\n\n"
            "💎 Токены не списаны."
        )

    if (
        "is_moderation_error" in lowered
        or "не прошли модерацию" in lowered
        or "nsfw" in lowered
        or "moderation" in lowered
    ):
        return (
            "⚠️ <b>Запрос не прошёл модерацию модели</b>\n\n"
            "Попробуйте изменить формулировку или убрать "
            "чувствительные детали.\n\n"
            "💎 Токены не списаны."
        )

    if "превышено время ожидания" in lowered or "timeout" in lowered:
        return (
            "⌛ <b>Модель не успела завершить генерацию</b>\n\n"
            "Попробуйте повторить запрос немного позже.\n\n"
            "💎 Токены не списаны."
        )

    if "http 422" in lowered or "errors_validation" in lowered:
        return (
            "⚠️ <b>Модель отклонила входные данные</b>\n\n"
            "Попробуйте выбрать другую модель или повторить запрос.\n\n"
            "💎 Токены не списаны."
        )

    if "недостаточно средств" in lowered or "http 402" in lowered:
        return (
            "⚠️ <b>Генерация временно недоступна</b>\n\n"
            "На стороне сервиса генерации недостаточно средств. "
            "Попробуйте позже.\n\n"
            "💎 Токены не списаны."
        )

    return (
        "❌ <b>Генерация не выполнена</b>\n\n"
        "Модель временно не смогла обработать запрос. "
        "Попробуйте ещё раз или выберите другую модель.\n\n"
        "💎 Токены не списаны."
    )


async def _complete_media_task(
    task: dict[str, Any],
) -> dict[str, Any]:
    status = str(task.get("status", "")).lower()

    if status in {"success", "completed", "done"}:
        return task

    request_id = task.get("request_id") or task.get("id")
    if not request_id:
        raise GenAPIError(
            f"GenAPI не вернул request_id: {task}"
        )

    return await genapi_client.wait_for_result(
        request_id,
        timeout=settings.GENAPI_POLL_TIMEOUT,
        interval=settings.GENAPI_POLL_INTERVAL,
    )


async def _send_long_text(
    message: Message,
    text: str,
) -> None:
    safe_text = html.escape(text)
    chunk_size = 3600
    chunks = [safe_text[start:start + chunk_size] for start in range(0, len(safe_text), chunk_size)]
    for index, chunk in enumerate(chunks):
        if index == len(chunks) - 1:
            chunk += BRAND_FOOTER
        await message.answer(chunk)


async def _show_video_models(message: Message) -> None:
    await message.answer(
        "<b>🎬 Создание видео</b>\n\n"
        "📝 — работает по текстовому описанию\n"
        "🖼 — умеет оживлять фотографию\n\n"
        "Нажмите на модель, чтобы сначала прочитать её описание, "
        "возможности и ограничения. После подтверждения бот покажет "
        "доступные настройки и точную стоимость.",
        reply_markup=get_video_models_keyboard(),
    )


@router.message(Command("ai"))
@router.message(F.text == "🤖 AI Ассистент")
async def open_text_models(
    message: Message,
    state: FSMContext,
) -> None:
    await _ensure_user(message)
    await state.clear()
    await message.answer(
        "<b>🤖 Текстовые модели</b>\n\n"
        "Нажмите на модель, чтобы сначала прочитать её описание, "
        "назначение и стоимость.",
        reply_markup=get_text_models_keyboard(),
    )


@router.message(F.text == "🖼 Создать картинку")
async def open_image_models(
    message: Message,
    state: FSMContext,
) -> None:
    await _ensure_user(message)
    await state.clear()
    await state.set_state(ImageGenerationStates.choosing_mode)
    await message.answer(
        "<b>🖼 Создать изображение</b>\n\n"
        "Как будем создавать?",
        reply_markup=get_image_mode_keyboard(),
    )


@router.callback_query(
    ImageGenerationStates.choosing_mode,
    F.data.startswith("image_mode:"),
)
async def select_image_mode(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    mode = callback.data.split(":", 1)[1]
    if mode not in {"text", "photo"}:
        await callback.answer("Некорректный режим", show_alert=True)
        return

    await state.update_data(
        image_mode=mode,
        input_image=None,
        input_image_path=None,
    )
    await state.set_state(ImageGenerationStates.choosing_model)
    await callback.answer()

    title = (
        "📝 <b>По описанию</b>"
        if mode == "text"
        else "📸 <b>По фотографии</b>"
    )
    await callback.message.answer(
        f"{title}\n\n"
        "Нажмите на модель, чтобы прочитать описание, "
        "подходящие задачи и ограничения. "
        "Цены идут по возрастанию.",
        reply_markup=get_image_models_keyboard(mode),
    )


@router.message(F.text == "🎬 Создать видео")
async def open_video_models(
    message: Message,
    state: FSMContext,
) -> None:
    await _ensure_user(message)
    await state.clear()
    await _show_video_models(message)


@router.message(F.text == "💰 Мой баланс")
@router.message(Command("balance"))
async def show_balance(message: Message) -> None:
    await _ensure_user(message)
    balance = await token_repository.get_user_tokens(
        message.from_user.id
    )
    free = await db_manager.get_free_credits(
        message.from_user.id
    )

    await message.answer(
        "<b>Ваш баланс</b>\n\n"
        f"💎 Токены: <b>{balance}</b>\n"
        f"🎁 Бесплатный текст: {_free_count_label(free['text_left'])} "
        f"· {get_model(settings.FREE_TEXT_MODEL).title}\n"
        f"🎁 Бесплатное изображение: "
        f"{_free_count_label(free['image_left'])} "
        f"· {get_model(settings.FREE_IMAGE_MODEL).title}\n"
        f"🎁 Бесплатное видео: "
        f"{_free_count_label(free['video_left'])} "
        f"· {get_model(settings.FREE_VIDEO_MODEL).title}\n\n"
        "ℹ️ Бесплатные попытки выдаются один раз на Telegram-аккаунт. "
        "Удаление переписки и повторный /start их не восстанавливают."
    )


@router.message(F.text == "💳 Купить токены")
@router.message(F.text == "💳 Купить кредиты")
@router.message(Command("buy"))
async def show_packages(message: Message) -> None:
    await _ensure_user(message)
    await message.answer(
        "Выберите пакет токенов:",
        reply_markup=get_token_packages_keyboard(),
    )


@router.callback_query(F.data.startswith("newtext:"))
async def select_text_model(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    model_key = callback.data.split(":", 1)[1]
    model = get_model(model_key)
    if not db_manager.is_model_enabled_cached(model_key):
        await callback.answer("Модель временно отключена", show_alert=True)
        return

    if model.kind != GenerationKind.TEXT:
        await callback.answer("Некорректная модель", show_alert=True)
        return

    await state.update_data(pending_text_model=model_key)
    free_notice = await _free_trial_notice(callback.from_user.id, model_key)
    exhausted = (await _free_trial_remaining(callback.from_user.id, model_key)) == 0
    await callback.answer(
        "Бесплатные попытки закончились. Дальше — за 💎." if exhausted else None,
        show_alert=exhausted,
    )
    await callback.message.edit_text(
        text_model_card(model_key) + free_notice,
        reply_markup=get_text_model_card_keyboard(model_key),
    )


@router.callback_query(F.data.startswith("text_use:"))
async def use_text_model(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    model_key = callback.data.split(":", 1)[1]
    model = get_model(model_key)
    if not db_manager.is_model_enabled_cached(model_key):
        await callback.answer("Модель временно отключена", show_alert=True)
        return
    data = await state.get_data()

    if model.kind != GenerationKind.TEXT or data.get("pending_text_model") != model_key:
        await callback.answer("Выберите модель заново", show_alert=True)
        return

    await state.set_state(TextGenerationStates.chatting)
    await state.update_data(
        text_model=model_key,
        pending_text_model=None,
        history=[],
    )
    free_notice = await _free_trial_notice(callback.from_user.id, model_key)
    await callback.answer()
    await callback.message.edit_text(
        f"{model_caption(model_key)}\n\n"
        "Отправьте вопрос. Для выхода нажмите "
        "«🔙 Назад» или выберите другой раздел."
        f"{free_notice}"
    )


@router.callback_query(F.data == "text_models_back")
async def back_to_text_models(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "<b>🤖 Текстовые модели</b>\n\n"
        "Нажмите на модель, чтобы сначала прочитать её описание, "
        "назначение и стоимость.",
        reply_markup=get_text_models_keyboard(),
    )


@router.message(
    TextGenerationStates.chatting,
    F.text,
    ~F.text.startswith("/"),
)
async def text_chat(
    message: Message,
    state: FSMContext,
) -> None:
    if message.text == "🔙 Назад":
        await state.clear()
        await message.answer("Диалог завершён.")
        return

    data = await state.get_data()
    model_key = data.get("text_model")
    history = _trim_chat_history(list(data.get("history", [])))
    history.append(
        {
            "role": "user",
            "content": message.text,
        }
    )
    history = _trim_chat_history(history)

    status = await message.answer(
        "⏳ Формирую ответ…"
    )

    try:
        response = await generation_service.generate_text(
            message.from_user.id,
            model_key,
            history,
        )
        text = _extract_text(response)
        history.append(
            {
                "role": "assistant",
                "content": text,
            }
        )
        await state.update_data(history=_trim_chat_history(history))
        await status.delete()
        await _send_long_text(message, text)

    except InsufficientBalanceError as exc:
        await status.edit_text(
            await _insufficient_balance_message(
                message.from_user.id,
                model_key,
                exc,
            ),
            reply_markup=get_token_packages_keyboard(),
        )

    except Exception as exc:
        logger.exception(
            "Ошибка текстовой генерации"
        )
        await _record_generation_error(
            message.from_user.id,
            model_key,
            message.text or "",
            exc,
        )
        await status.edit_text(
            "Не удалось получить ответ от модели. Токены возвращены — "
            "попробуйте ещё раз или выберите другую модель."
        )


@router.callback_query(F.data.startswith("newimage:"))
async def select_image_model(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    model_key = callback.data.split(":", 1)[1]
    model = get_model(model_key)
    if not db_manager.is_model_enabled_cached(model_key):
        await callback.answer("Модель временно отключена", show_alert=True)
        return
    data = await state.get_data()
    mode = data.get("image_mode")

    if model.kind != GenerationKind.IMAGE:
        await callback.answer("Некорректная модель", show_alert=True)
        return

    if mode not in {"text", "photo"}:
        await state.clear()
        await state.set_state(ImageGenerationStates.choosing_mode)
        await callback.answer("Сначала выберите режим", show_alert=True)
        await callback.message.edit_text(
            "<b>🖼 Создать изображение</b>\n\nКак будем создавать?",
            reply_markup=get_image_mode_keyboard(),
        )
        return

    if not image_model_supports_mode(model_key, mode):
        await callback.answer(
            "Эта модель недоступна в выбранном режиме",
            show_alert=True,
        )
        return

    await state.update_data(
        model_key=model_key,
        input_image=None,
        input_image_path=None,
    )
    free_notice = await _free_trial_notice(callback.from_user.id, model_key)
    exhausted = (await _free_trial_remaining(callback.from_user.id, model_key)) == 0
    await callback.answer(
        "Бесплатные попытки закончились. Дальше — за 💎." if exhausted else None,
        show_alert=exhausted,
    )
    await callback.message.edit_text(
        image_model_card(model_key, mode) + free_notice,
        reply_markup=get_image_model_card_keyboard(model_key, mode),
    )


@router.callback_query(F.data.startswith("image_models_back:"))
async def back_to_image_models(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    mode = callback.data.split(":", 1)[1]
    if mode not in {"text", "photo"}:
        await callback.answer("Некорректный режим", show_alert=True)
        return

    await state.set_state(ImageGenerationStates.choosing_model)
    await state.update_data(
        image_mode=mode,
        model_key=None,
        input_image=None,
        input_image_path=None,
    )
    await callback.answer()
    title = (
        "📝 <b>По описанию</b>"
        if mode == "text"
        else "📸 <b>По фотографии</b>"
    )
    await callback.message.edit_text(
        f"{title}\n\n"
        "Нажмите на модель, чтобы прочитать описание, "
        "подходящие задачи и ограничения. "
        "Цены идут по возрастанию.",
        reply_markup=get_image_models_keyboard(mode),
    )


@router.callback_query(F.data.startswith("image_use:"))
async def use_image_model(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    try:
        _, mode, model_key = callback.data.split(":", 2)
    except ValueError:
        await callback.answer("Некорректный выбор", show_alert=True)
        return

    if not db_manager.is_model_enabled_cached(model_key):
        await callback.answer("Модель временно отключена", show_alert=True)
        return

    data = await state.get_data()

    if (
        mode not in {"text", "photo"}
        or data.get("image_mode") != mode
        or not image_model_supports_mode(model_key, mode)
    ):
        await callback.answer("Выберите модель заново", show_alert=True)
        return

    if (
        mode == "photo"
        and generation_service.requires_public_url(model_key)
        and not public_media_service.is_configured
    ):
        await callback.answer(
            "Для этой модели не настроен публичный домен BotHost.",
            show_alert=True,
        )
        return

    await state.update_data(
        model_key=model_key,
        input_image=None,
        input_image_path=None,
    )
    free_notice = await _free_trial_notice(callback.from_user.id, model_key)
    exhausted = (await _free_trial_remaining(callback.from_user.id, model_key)) == 0
    await callback.answer(
        "Бесплатные попытки закончились. Дальше — за 💎." if exhausted else None,
        show_alert=exhausted,
    )

    if mode == "photo":
        await state.set_state(ImageGenerationStates.waiting_image)
        await callback.message.edit_text(
            f"{model_caption(model_key, image_mode=mode)}"
            f"{free_notice}\n\n"
            "📸 Отправьте фотографию одним сообщением."
        )
        return

    await state.set_state(ImageGenerationStates.waiting_prompt)
    await callback.message.edit_text(
        f"{model_caption(model_key, image_mode=mode)}"
        f"{free_notice}\n\n"
        "📝 Опишите изображение, которое нужно создать."
    )


@router.callback_query(F.data.startswith("newvideo:"))
async def select_video_model(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    model_key = callback.data.split(":", 1)[1]
    model = get_model(model_key)
    if not db_manager.is_model_enabled_cached(model_key):
        await callback.answer("Модель временно отключена", show_alert=True)
        return

    if model.kind != GenerationKind.VIDEO:
        await callback.answer("Некорректная модель", show_alert=True)
        return

    await state.update_data(pending_video_model=model_key)
    free_notice = await _free_trial_notice(callback.from_user.id, model_key)
    exhausted = (await _free_trial_remaining(callback.from_user.id, model_key)) == 0
    await callback.answer(
        "Бесплатные попытки закончились. Дальше — за 💎." if exhausted else None,
        show_alert=exhausted,
    )
    await callback.message.edit_text(
        video_model_card(model_key) + free_notice,
        reply_markup=get_video_model_card_keyboard(model_key),
    )


@router.callback_query(F.data.startswith("video_use:"))
async def use_video_model(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    model_key = callback.data.split(":", 1)[1]
    model = get_model(model_key)
    if not db_manager.is_model_enabled_cached(model_key):
        await callback.answer("Модель временно отключена", show_alert=True)
        return
    data = await state.get_data()

    if model.kind != GenerationKind.VIDEO or data.get("pending_video_model") != model_key:
        await callback.answer("Выберите модель заново", show_alert=True)
        return

    selection = default_video_selection(model_key)
    await state.set_state(VideoGenerationStates.choosing_duration)
    await state.update_data(
        model_key=model_key,
        pending_video_model=None,
        input_image=None,
        input_image_path=None,
        video_selection=selection,
        duration=selection.get("duration"),
        media_overrides=build_video_overrides(model_key, selection),
    )
    free_notice = await _free_trial_notice(callback.from_user.id, model_key)
    await callback.answer()
    await callback.message.edit_text(
        _video_settings_text(model_key, selection) + free_notice,
        reply_markup=_video_settings_keyboard(model_key, selection),
    )


@router.callback_query(F.data == "video_models_back")
async def back_to_video_models(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(
        "<b>🎬 Создание видео</b>\n\n"
        "📝 — работает по текстовому описанию\n"
        "🖼 — умеет оживлять фотографию\n\n"
        "Нажмите на модель, чтобы сначала прочитать её описание, "
        "возможности и ограничения.",
        reply_markup=get_video_models_keyboard(),
    )


@router.callback_query(F.data.startswith("video_option:"))
async def select_video_option(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    parts = callback.data.split(":")

    # Новый формат хранит модель прямо в callback_data и переживает перезапуск бота:
    # video_option:<model_key>:<field>:<value>
    if len(parts) == 4:
        _, model_key, field, raw_value = parts
    # Совместимость со старыми сообщениями, созданными до обновления.
    elif len(parts) == 3:
        _, field, raw_value = parts
        model_key = data.get("model_key")
    else:
        await callback.answer("Некорректная кнопка. Выберите модель заново.", show_alert=True)
        return

    if not model_key:
        await callback.answer(
            "Сессия устарела после перезапуска. Выберите модель видео заново.",
            show_alert=True,
        )
        return

    try:
        model = get_model(model_key)
        if model.kind != GenerationKind.VIDEO:
            raise ValueError("Некорректная модель видео")
        value = validate_option(model_key, field, raw_value)
    except (KeyError, ValueError) as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    stored_model_key = data.get("model_key")
    selection = dict(
        data.get("video_selection")
        if stored_model_key == model_key and data.get("video_selection")
        else default_video_selection(model_key)
    )
    selection[field] = value
    await state.set_state(VideoGenerationStates.choosing_duration)
    await state.update_data(
        model_key=model_key,
        pending_video_model=None,
        video_selection=selection,
        duration=selection.get("duration"),
        media_overrides=build_video_overrides(model_key, selection),
    )
    await callback.answer()
    await _show_video_settings(callback, state, edit=True)


@router.callback_query(F.data == "video_options_continue")
@router.callback_query(F.data.startswith("video_options_continue:"))
async def continue_video_options(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    model_key = data.get("model_key")

    # В новых кнопках модель записана в callback_data, поэтому продолжение
    # восстанавливается даже после потери MemoryStorage при перезапуске.
    if callback.data.startswith("video_options_continue:"):
        model_key = callback.data.split(":", 1)[1]

    if not model_key:
        await callback.answer(
            "Сессия устарела после перезапуска. Выберите модель видео заново.",
            show_alert=True,
        )
        return

    try:
        model = get_model(model_key)
    except KeyError:
        await callback.answer("Модель не найдена. Выберите её заново.", show_alert=True)
        return
    if model.kind != GenerationKind.VIDEO:
        await callback.answer("Некорректная модель видео", show_alert=True)
        return
    if not db_manager.is_model_enabled_cached(model_key):
        await callback.answer("Модель временно отключена", show_alert=True)
        return

    stored_model_key = data.get("model_key")
    selection = dict(
        data.get("video_selection")
        if stored_model_key == model_key and data.get("video_selection")
        else default_video_selection(model_key)
    )
    await state.set_state(VideoGenerationStates.choosing_duration)
    await state.update_data(
        model_key=model_key,
        pending_video_model=None,
        video_selection=selection,
        duration=selection.get("duration"),
        media_overrides=build_video_overrides(model_key, selection),
    )
    await callback.answer()
    await _continue_video_flow(callback, state)


@router.callback_query(
    F.data.startswith("video_duration:")
)
async def select_video_duration(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    _, model_key, raw_duration = callback.data.split(":", 2)
    try:
        duration = validate_option(model_key, "duration", raw_duration)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return

    data = await state.get_data()
    selection = dict(data.get("video_selection") or default_video_selection(model_key))
    selection["duration"] = duration
    await state.update_data(
        model_key=model_key,
        video_selection=selection,
        duration=duration,
        media_overrides=build_video_overrides(model_key, selection),
    )
    await callback.answer()
    await _show_video_settings(callback, state, edit=False)


@router.callback_query(F.data.startswith("media_image:"))
async def request_input_image(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    model_key = callback.data.split(":", 1)[1]
    model = get_model(model_key)

    state_cls = (
        ImageGenerationStates
        if model.kind == GenerationKind.IMAGE
        else VideoGenerationStates
    )

    await state.set_state(
        state_cls.waiting_image
    )
    await state.update_data(
        model_key=model_key
    )
    await callback.answer()
    await callback.message.answer(
        "Отправьте фотографию одним сообщением."
    )


@router.callback_query(F.data.startswith("media_skip:"))
async def skip_input_image(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    model_key = callback.data.split(":", 1)[1]
    model = get_model(model_key)

    if model.requires_input_image:
        await callback.answer(
            "Для этой модели фото обязательно",
            show_alert=True,
        )
        return

    next_state = (
        ImageGenerationStates.waiting_prompt
        if model.kind == GenerationKind.IMAGE
        else VideoGenerationStates.waiting_prompt
    )

    await state.set_state(next_state)
    await state.update_data(
        model_key=model_key,
        input_image=None,
    )
    await callback.answer()
    await callback.message.answer(
        "Введите промпт."
    )


@router.message(
    ImageGenerationStates.waiting_image,
    F.photo,
)
@router.message(
    VideoGenerationStates.waiting_image,
    F.photo,
)
async def receive_input_image(
    message: Message,
    state: FSMContext,
    bot: Bot,
) -> None:
    data = await state.get_data()
    model = get_model(data["model_key"])
    media, image_width, image_height = await _download_photo(
        message,
        bot,
        # Несколько video-endpoint отклоняют изображения, у которых
        # width + height > 1920. Telegram уже хранит уменьшенные копии,
        # поэтому скачиваем подходящую без потери исходного фото пользователя.
        max_dimension_sum=1920 if model.kind == GenerationKind.VIDEO else None,
    )

    next_state = (
        ImageGenerationStates.waiting_prompt
        if model.kind == GenerationKind.IMAGE
        else VideoGenerationStates.waiting_prompt
    )

    await state.update_data(
        input_image_path=media.path,
        input_image_name=media.filename,
        input_image_type=media.content_type,
        input_image_width=image_width,
        input_image_height=image_height,
    )

    if model.key == "cartoonify":
        await state.set_state(
            ImageGenerationStates.choosing_cartoon_strength
        )
        await message.answer(
            "Фото принято. Выберите силу мультяшного эффекта:",
            reply_markup=get_cartoonify_strength_keyboard(),
        )
        return

    await state.set_state(next_state)
    await message.answer(
        "Фото принято. Напишите, что должно получиться."
    )


@router.message(
    ImageGenerationStates.waiting_image
)
@router.message(
    VideoGenerationStates.waiting_image
)
async def require_photo(message: Message) -> None:
    await message.answer(
        "Нужно отправить фотографию, "
        "не файл и не текст."
    )


@router.callback_query(
    ImageGenerationStates.choosing_cartoon_strength,
    F.data.startswith("cartoonify_strength:"),
)
async def choose_cartoonify_strength(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    level = callback.data.split(":", 1)[1]
    options = {
        "light": (1.0, "🙂 Лёгкий"),
        "medium": (1.25, "🎨 Средний"),
        "strong": (1.5, "🧸 Сильный"),
    }
    selected = options.get(level)
    if selected is None:
        await callback.answer("Некорректный вариант", show_alert=True)
        return

    scale, title = selected
    data = await state.get_data()
    model = get_model(data["model_key"])
    await state.update_data(
        prompt="",
        token_cost=_current_model_price(model.key),
        media_overrides={"scale": scale},
    )
    await state.set_state(ImageGenerationStates.confirming)
    await callback.answer()
    await callback.message.answer(
        "<b>Подтверждение генерации</b>\n\n"
        f"{model_caption(model.key, image_mode=data.get('image_mode'))}\n"
        f"Эффект: <b>{title}</b>"
        "\n\nТокены будут списаны только после подтверждения.",
        reply_markup=get_generation_confirm_keyboard(),
    )


@router.message(
    ImageGenerationStates.waiting_prompt,
    F.text,
    ~F.text.startswith("/"),
)
@router.message(
    VideoGenerationStates.waiting_prompt,
    F.text,
    ~F.text.startswith("/"),
)
async def generate_media(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    model = get_model(data["model_key"])

    if model.kind == GenerationKind.VIDEO:
        selection = dict(
            data.get("video_selection")
            or default_video_selection(model.key)
        )
        duration = selection.get("duration")
        cost = video_cost_tokens(model.key, selection)
        labels = selection_labels(model.key, selection)
        overrides = build_video_overrides(model.key, selection)

        await state.update_data(
            prompt=message.text,
            token_cost=cost,
            duration=duration,
            video_selection=selection,
            media_overrides=overrides,
        )
        await state.set_state(VideoGenerationStates.confirming)
        await message.answer(
            "<b>Подтверждение генерации</b>\n\n"
            f"<b>🎬 {model.title}</b>\n"
            f"Режим: {'🖼 фото → видео' if data.get('input_image_path') else '📝 текст → видео'}\n"
            f"Качество: <b>{labels['quality']}</b>\n"
            f"Разрешение: <b>{labels['resolution']}</b>\n"
            f"Длительность: <b>{labels['duration']}</b>\n"
            f"Звук: <b>{labels['audio']}</b>\n"
            f"Формат: <b>{labels['aspect']}</b>\n"
            f"Стоимость: <b>{cost} 💎</b>\n\n"
            "Токены будут списаны только после подтверждения.",
            reply_markup=get_generation_confirm_keyboard(video=True),
        )
        return

    await state.update_data(
        prompt=message.text,
        token_cost=_current_model_price(model.key),
    )
    await state.set_state(
        ImageGenerationStates.confirming
    )
    await message.answer(
        "<b>Подтверждение генерации</b>\n\n"
        f"{model_caption(model.key, image_mode=data.get('image_mode'))}\n"
        f"Режим: "
        f"{'📸 по фотографии' if data.get('input_image_path') else '📝 по описанию'}"
        "\n\nТокены будут списаны только "
        "после подтверждения.",
        reply_markup=get_generation_confirm_keyboard(),
    )


@router.callback_query(
    F.data == "video_change_duration"
)
async def change_video_duration(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await state.set_state(VideoGenerationStates.choosing_duration)
    await callback.answer()
    await _show_video_settings(callback, state, edit=False)


@router.callback_query(
    ImageGenerationStates.confirming,
    F.data == "generation_confirm",
)
@router.callback_query(
    VideoGenerationStates.confirming,
    F.data == "generation_confirm",
)
async def confirm_generation(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    user_id = callback.from_user.id
    if not generation_guard.try_acquire(user_id):
        await callback.answer(
            "Предыдущая генерация ещё выполняется. Дождитесь результата.",
            show_alert=True,
        )
        return

    await callback.answer("Генерация запущена")
    data = await state.get_data()
    try:
        await _execute_media(
            callback.message,
            state,
            prompt=data["prompt"],
            user_id=user_id,
        )
    finally:
        generation_guard.release(user_id)


async def _execute_media(
    message: Message,
    state: FSMContext,
    *,
    prompt: str,
    user_id: int,
) -> None:
    data = await state.get_data()
    model_key = data["model_key"]
    model = get_model(model_key)

    processing_state = (
        ImageGenerationStates.processing
        if model.kind == GenerationKind.IMAGE
        else VideoGenerationStates.processing
    )
    await state.set_state(processing_state)

    status = await message.answer(
        f"<b>{model.title}</b>\n\n"
        "▰▱▱▱▱\n"
        "⏳ Запрос отправлен в модель…"
    )
    progress_task: asyncio.Task[None] | None = asyncio.create_task(
        _animate_generation_status(status, model.title)
    )
    charge = None

    try:
        overrides: dict[str, Any] = dict(
            data.get("media_overrides") or {}
        )
        duration = data.get("duration")

        if model.kind == GenerationKind.VIDEO:
            selection = data.get("video_selection")
            if selection:
                overrides.update(build_video_overrides(model_key, selection))
            elif data.get("input_image_path"):
                # Совместимость со старыми незавершёнными сценариями.
                for key, value in _video_aspect_overrides(
                    model_key,
                    data.get("input_image_width"),
                    data.get("input_image_height"),
                ).items():
                    overrides.setdefault(key, value)

        if model.kind == GenerationKind.VIDEO and duration:
            if model_key in {
                "veo-3-1",
                "veo-3-1-lite",
                "luma-ray2",
            }:
                overrides["duration"] = f"{duration}s"
            else:
                overrides["duration"] = duration

        input_image = None
        if data.get("input_image_path"):
            input_image = LocalMedia(
                data["input_image_path"],
                data["input_image_name"],
                data["input_image_type"],
            )

        charge, task = await generation_service.create_media_task(
            user_id,
            model_key,
            prompt,
            input_image=input_image,
            overrides=overrides,
            token_cost=data.get("token_cost"),
        )
        result = await _complete_media_task(task)
        urls = _collect_urls(result)

        if not urls:
            raise GenAPIError(
                "В результате нет ссылки на файл: "
                f"{result}"
            )

        await _stop_progress(progress_task)
        progress_task = None

        if model.kind == GenerationKind.IMAGE:
            requested_count = overrides.get(
                "num_images",
                model.defaults.get("num_images", 1),
            )
            try:
                result_limit = max(1, min(4, int(requested_count)))
            except (TypeError, ValueError):
                result_limit = 1

            for url in urls[:result_limit]:
                await message.answer_photo(
                    url,
                    caption=(
                        f"✅ Готово · {model.title}\n\n"
                        f"{IMAGE_BRAND_CAPTION}"
                    ),
                )
        else:
            duration_suffix = f" · {duration} сек." if duration else ""
            await message.answer_video(
                urls[0],
                caption=(
                    f"✅ Готово · {model.title}{duration_suffix}\n\n"
                    f"{VIDEO_BRAND_CAPTION}"
                ),
                supports_streaming=True,
            )

        with contextlib.suppress(TelegramBadRequest):
            await status.delete()

        await public_media_service.revoke_path(
            data.get("input_image_path")
        )
        await media_storage.remove(
            data.get("input_image_path")
        )
        await state.clear()

    except asyncio.CancelledError:
        if charge is not None:
            await billing_service.refund(
                charge,
                "Генерация прервана перезапуском бота",
            )
        await public_media_service.revoke_path(data.get("input_image_path"))
        await media_storage.remove(data.get("input_image_path"))
        raise

    except InsufficientBalanceError as exc:
        await _stop_progress(progress_task)
        progress_task = None
        await public_media_service.revoke_path(
            data.get("input_image_path")
        )
        await media_storage.remove(
            data.get("input_image_path")
        )
        await state.clear()
        await status.edit_text(
            await _insufficient_balance_message(
                user_id,
                model_key,
                exc,
            ),
            reply_markup=get_token_packages_keyboard(),
        )

    except Exception as exc:
        await _record_generation_error(
            user_id,
            model_key,
            str(data.get("prompt") or ""),
            exc,
        )
        if isinstance(exc, (GenAPIError, GenAPIHTTPError, PublicMediaError)):
            logger.warning("Ожидаемая ошибка медиагенерации: %s", exc)
        else:
            logger.exception("Ошибка медиагенерации")
        await _stop_progress(progress_task)
        progress_task = None

        if charge is not None:
            await billing_service.refund(
                charge,
                "Ошибка получения результата",
            )

        await public_media_service.revoke_path(
            data.get("input_image_path")
        )
        await media_storage.remove(
            data.get("input_image_path")
        )

        if model.kind == GenerationKind.IMAGE:
            await state.set_state(ImageGenerationStates.choosing_mode)
            reply_markup = get_image_mode_keyboard()
        else:
            await state.clear()
            reply_markup = get_video_models_keyboard()

        await status.edit_text(
            _friendly_media_error(exc),
            reply_markup=reply_markup,
        )

    finally:
        await _stop_progress(progress_task)


@router.callback_query(
    F.data == "generation_cancel"
)
async def cancel_generation(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    if generation_guard.is_active(callback.from_user.id):
        await callback.answer(
            "Генерация уже запущена и выполняется. Дождитесь результата.",
            show_alert=True,
        )
        return

    data = await state.get_data()
    model_key = data.get("model_key")

    await public_media_service.revoke_path(
        data.get("input_image_path")
    )
    await media_storage.remove(
        data.get("input_image_path")
    )
    await state.clear()
    await callback.answer("Отменено")

    # Если отменили видео — сразу возвращаем в раздел видео.
    if model_key:
        try:
            model = get_model(model_key)
        except (KeyError, ValueError):
            model = None

        if (
            model is not None
            and model.kind == GenerationKind.VIDEO
        ):
            await _show_video_models(callback.message)
            return
        if (
            model is not None
            and model.kind == GenerationKind.IMAGE
        ):
            await state.set_state(ImageGenerationStates.choosing_mode)
            await callback.message.answer(
                "<b>🖼 Создать изображение</b>\n\n"
                "Как будем создавать?",
                reply_markup=get_image_mode_keyboard(),
            )
            return

    if data.get("image_mode"):
        await state.set_state(ImageGenerationStates.choosing_mode)
        await callback.message.answer(
            "<b>🖼 Создать изображение</b>\n\n"
            "Как будем создавать?",
            reply_markup=get_image_mode_keyboard(),
        )
        return

    await callback.message.answer("Генерация отменена.")
