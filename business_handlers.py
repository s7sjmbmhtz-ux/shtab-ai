"""Продажи, маркетинг и профессиональный мастер карточек маркетплейсов."""
from __future__ import annotations

import html
from typing import Any

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from business_catalog import TOOLS, get_tool
from business_keyboards import (
    cancel_keyboard, marketplace_menu, marketplace_product_type,
    marketplace_style, marketing_menu, sales_menu,
)
from business_states import BusinessToolStates, MarketplaceStates
from generation_keyboards import get_token_packages_keyboard
from handlers import _register_user
from keyboards import get_main_menu
from services.billing_service import InsufficientBalanceError
from services.genapi_client import GenAPIError, genapi_client
from services.generation_service import generation_service
from services.media_storage import LocalMedia, media_storage
from model_catalog import get_model
from settings import settings
from utils import logger

router = Router(name="business_router")

BUTTON_TO_TOOL = {
    "📞 Скрипт продаж": "sales_script",
    "💬 Ответ клиенту": "client_reply",
    "📑 Коммерческое предложение": "commercial_offer",
    "🛡 Работа с возражениями": "objections",
    "📊 Анализ переписки": "chat_analysis",
    "📝 Маркетинговый пост": "marketing_post",
    "🗓 Контент-план": "content_plan",
    "🎯 Анализ аудитории": "audience_analysis",
    "✉️ Email-рассылка": "email_campaign",
    "📝 Описание товара": "marketplace_listing",
}


def _extract_text(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        content = choices[0].get("message", {}).get("content")
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
    raise GenAPIError("Не удалось извлечь текст из ответа")


def _collect_urls(value: Any) -> list[str]:
    urls: list[str] = []
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        urls.append(value)
    elif isinstance(value, list):
        for item in value:
            urls.extend(_collect_urls(item))
    elif isinstance(value, dict):
        for item in value.values():
            if isinstance(item, (str, list, dict)):
                urls.extend(_collect_urls(item))
    return list(dict.fromkeys(urls))


async def _wait_media(task: dict[str, Any]) -> dict[str, Any]:
    if str(task.get("status", "")).lower() in {"success", "completed", "done"}:
        return task
    request_id = task.get("request_id") or task.get("id")
    if not request_id:
        raise GenAPIError("GenAPI не вернул request_id")
    return await genapi_client.wait_for_result(
        request_id,
        timeout=settings.GENAPI_POLL_TIMEOUT,
        interval=settings.GENAPI_POLL_INTERVAL,
    )


@router.message(F.text == "🏢 Продажи")
async def open_sales(message: Message, state: FSMContext) -> None:
    await _register_user(message)
    await state.clear()
    await message.answer("Выберите инструмент продаж:", reply_markup=sales_menu())


@router.message(F.text == "📈 Маркетинг")
async def open_marketing(message: Message, state: FSMContext) -> None:
    await _register_user(message)
    await state.clear()
    await message.answer("Выберите маркетинговый инструмент:", reply_markup=marketing_menu())


@router.message(F.text == "🛒 Маркетплейсы")
async def open_marketplace(message: Message, state: FSMContext) -> None:
    await _register_user(message)
    await state.clear()
    await message.answer(
        "<b>Маркетплейсы</b>\n\n"
        "Создайте визуал товара из фотографии или концепт без фотографии. "
        "Для точного совпадения реального товара лучше использовать фото.",
        reply_markup=marketplace_menu(),
    )


@router.message(F.text.in_(set(BUTTON_TO_TOOL)))
async def start_business_tool(message: Message, state: FSMContext) -> None:
    await _register_user(message)
    tool = get_tool(BUTTON_TO_TOOL[message.text])
    await state.set_state(BusinessToolStates.collecting)
    await state.update_data(tool_key=tool.key, step=0, answers={})
    price = get_model(tool.model_key).token_cost
    admin_note = " (для администратора 0 💎)" if message.from_user.id == settings.ADMIN_TELEGRAM_ID else ""
    await message.answer(
        f"<b>{tool.title}</b>\n{tool.description}\n\nСтоимость: <b>{price} 💎</b>{admin_note}\n\n{tool.questions[0][1]}",
        reply_markup=cancel_keyboard(),
    )


@router.message(BusinessToolStates.collecting, F.text)
async def collect_business_answer(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=get_main_menu())
        return
    data = await state.get_data()
    tool = get_tool(data["tool_key"])
    step = int(data.get("step", 0))
    answers = dict(data.get("answers", {}))
    field, _ = tool.questions[step]
    answers[field] = message.text.strip()
    step += 1
    if step < len(tool.questions):
        await state.update_data(step=step, answers=answers)
        await message.answer(tool.questions[step][1])
        return

    prompt_lines = [tool.instruction, "", "ДАННЫЕ ПОЛЬЗОВАТЕЛЯ:"]
    for key, value in answers.items():
        prompt_lines.append(f"{key}: {value}")
    prompt_lines.append("\nОтвечай на русском языке. Не выдумывай факты, которых нет во входных данных.")
    status = await message.answer("⏳ Готовлю результат…")
    try:
        response = await generation_service.generate_text(
            message.from_user.id,
            tool.model_key,
            [{"role": "user", "content": "\n".join(prompt_lines)}],
        )
        text = _extract_text(response)
        await status.delete()
        for start in range(0, len(text), 3900):
            await message.answer(html.escape(text[start:start + 3900]))
    except InsufficientBalanceError as exc:
        await status.edit_text(
            f"Недостаточно токенов: нужно {exc.required} 💎, доступно {exc.balance} 💎.",
            reply_markup=get_token_packages_keyboard(),
        )
    except Exception as exc:
        logger.exception("Ошибка бизнес-инструмента")
        await status.edit_text(f"Не удалось выполнить задачу: {html.escape(str(exc))}")
    finally:
        await state.clear()


@router.message(F.text == "📸 Карточка из фото")
async def marketplace_from_photo(message: Message, state: FSMContext) -> None:
    await state.set_state(MarketplaceStates.waiting_photo)
    await state.update_data(source="photo", input_image=None)
    await message.answer(
        "Загрузите чёткое фото товара без лишних предметов. Лучше использовать нейтральный фон.",
        reply_markup=cancel_keyboard(),
    )


@router.message(F.text == "✨ Карточка без фото")
async def marketplace_without_photo(message: Message, state: FSMContext) -> None:
    await state.set_state(MarketplaceStates.choosing_product_type)
    await state.update_data(source="prompt", input_image=None)
    await message.answer(
        "Что нужно создать? Без фотографии результат будет концептом и может отличаться от реального товара.",
        reply_markup=marketplace_product_type(),
    )


@router.message(MarketplaceStates.waiting_photo, F.photo)
async def marketplace_receive_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    media = await media_storage.download_photo(bot, message.photo[-1].file_id)
    await state.update_data(input_image={"path": str(media.path), "filename": media.filename, "content_type": media.content_type})
    await state.set_state(MarketplaceStates.choosing_product_type)
    await message.answer("Фото принято. Что нужно создать?", reply_markup=marketplace_product_type())


@router.message(MarketplaceStates.waiting_photo)
async def marketplace_photo_required(message: Message) -> None:
    await message.answer("Пришлите фотографию товара или нажмите «❌ Отмена».")


@router.callback_query(MarketplaceStates.choosing_product_type, F.data.startswith("mp:type:"))
async def marketplace_choose_type(callback: CallbackQuery, state: FSMContext) -> None:
    product_type = callback.data.rsplit(":", 1)[1]
    await state.update_data(product_type=product_type)
    await state.set_state(MarketplaceStates.waiting_product_name)
    await callback.answer()
    await callback.message.answer("Напишите название товара и его категорию.")


@router.message(MarketplaceStates.waiting_product_name, F.text)
async def marketplace_product_name(message: Message, state: FSMContext) -> None:
    await state.update_data(product_name=message.text.strip())
    await state.set_state(MarketplaceStates.waiting_features)
    await message.answer("Перечислите реальные характеристики и преимущества товара. Не добавляйте того, чего у товара нет.")


@router.message(MarketplaceStates.waiting_features, F.text)
async def marketplace_features(message: Message, state: FSMContext) -> None:
    await state.update_data(features=message.text.strip())
    await state.set_state(MarketplaceStates.choosing_style)
    await message.answer("Выберите визуальный стиль:", reply_markup=marketplace_style())


@router.callback_query(MarketplaceStates.choosing_style, F.data.startswith("mp:style:"))
async def marketplace_generate(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    style = callback.data.rsplit(":", 1)[1]
    input_data = data.get("input_image")
    input_image = None
    if input_data:
        from pathlib import Path
        input_image = LocalMedia(Path(input_data["path"]), input_data["filename"], input_data["content_type"])

    prompts = _marketplace_prompts(
        data["product_type"], data["product_name"], data["features"], style,
        has_photo=input_image is not None,
    )
    status = await callback.message.answer(
        f"⏳ Создаю {len(prompts)} изображение(я). Это может занять несколько минут…"
    )
    try:
        model_by_type = {
            "main": "marketplace-main",
            "lifestyle": "marketplace-lifestyle",
            "infographic": "marketplace-infographic",
            "bundle": "marketplace-bundle-item",
        }
        for index, prompt in enumerate(prompts, start=1):
            charge, task = await generation_service.create_media_task(
                callback.from_user.id,
                model_by_type[data["product_type"]],
                prompt,
                input_image=input_image,
                overrides={"width": 1024, "height": 1280, "strength": 0.72},
            )
            result = await _wait_media(task)
            urls = _collect_urls(result.get("output", result))
            if not urls:
                await generation_service.client  # keeps type checkers quiet
                raise GenAPIError("Сервис не вернул изображение")
            await callback.message.answer_photo(
                urls[0],
                caption=f"Карточка {index}/{len(prompts)} — {html.escape(data['product_name'])}",
            )
        await status.edit_text(
            "✅ Готово. Для точной инфографики с надписями следующий этап добавит программное наложение текста — "
            "сейчас модель создаёт визуальную основу и композицию."
        )
    except InsufficientBalanceError as exc:
        await status.edit_text(
            f"Недостаточно токенов: нужно {exc.required} 💎, доступно {exc.balance} 💎.",
            reply_markup=get_token_packages_keyboard(),
        )
    except Exception as exc:
        logger.exception("Ошибка карточки маркетплейса")
        await status.edit_text(f"Не удалось создать карточку: {html.escape(str(exc))}")
    finally:
        if input_image:
            await media_storage.remove(input_image)
        await state.clear()


def _marketplace_prompts(kind: str, product: str, features: str, style: str, *, has_photo: bool) -> list[str]:
    styles = {
        "minimal": "light minimal studio, clean soft shadows, white and pale beige palette",
        "premium": "premium commercial studio, dark elegant background, controlled highlights",
        "cozy": "cozy realistic home interior, warm natural light",
        "bright": "bright modern advertising composition, energetic clean colors",
    }
    identity = (
        "Preserve the exact product shape, proportions, materials, colors, handles, labels and all visible details from the reference image. "
        if has_photo else
        "Create a realistic product concept matching the description exactly. "
    )
    base = (
        f"Professional marketplace product photography. Product: {product}. Verified features: {features}. "
        f"{identity}Style: {styles.get(style, styles['minimal'])}. Vertical 4:5 composition, high detail, realistic materials, no watermark, no distorted text. "
    )
    if kind == "main":
        return [base + "Hero main product image, product centered, clear silhouette, generous clean space, commercial catalog quality."]
    if kind == "lifestyle":
        return [base + "Lifestyle scene showing the product naturally in use, product remains the clear main subject, realistic scale."]
    if kind == "infographic":
        return [base + "Marketplace infographic base: product on one side and three clean empty callout zones on the other side. Do not generate readable words; leave blank panels for later text overlay."]
    return [
        base + "Hero main product image, centered, catalog quality.",
        base + "Lifestyle scene showing the product naturally in use.",
        base + "Detailed close-up emphasizing materials and useful product features, clean commercial composition.",
    ]
