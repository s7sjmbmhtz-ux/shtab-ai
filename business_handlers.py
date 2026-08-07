"""Продажи, маркетинг и профессиональный мастер карточек маркетплейсов."""
from __future__ import annotations

import asyncio
import html
from typing import Any

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from business_catalog import get_tool
from database import db_manager, token_repository
from business_keyboards import (
    cancel_keyboard,
    marketplace_category,
    marketplace_confirm,
    marketplace_features_action,
    marketplace_goal,
    marketplace_menu,
    marketplace_platform,
    marketplace_product_type,
    marketplace_style,
    marketing_menu,
    sales_menu,
)
from business_states import BusinessToolStates, MarketplaceStates
from generation_keyboards import get_token_packages_keyboard
from handlers import _register_user
from keyboards import get_main_menu
from services.billing_service import InsufficientBalanceError, billing_service
from services.genapi_client import GenAPIError, genapi_client
from services.generation_service import generation_service
from services.generation_guard import generation_guard
from services.media_storage import LocalMedia, media_storage
from model_catalog import get_model
from marketplace_prompts import build_prompts, detect_category
from settings import settings
from utils import logger

router = Router(name="business_router")

_BOT_USERNAME = settings.BOT_USERNAME.lstrip("@")
MARKETPLACE_BRAND_CAPTION = f"📦 Карточка создана в ШТАБ AI\n👉 @{_BOT_USERNAME}"

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
    model = get_model(tool.model_key)
    price = db_manager.get_model_price_cached(model.key, model.token_cost)
    admin_note = " (для администратора 0 💎)" if settings.is_admin(message.from_user.id) else ""
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
    answers[field] = message.text.strip()[:3000]
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
    await state.clear()
    await state.set_state(MarketplaceStates.waiting_photo)
    await state.update_data(source="photo", input_image=None)
    await message.answer("Загрузите чёткое фото товара. Лучше: один товар, нейтральный фон, без рук и лишних предметов.", reply_markup=cancel_keyboard())


@router.message(F.text == "✨ Концепт без фото")
async def marketplace_without_photo(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(MarketplaceStates.choosing_product_type)
    await state.update_data(source="prompt", input_image=None)
    await message.answer("Выберите результат. Без фотографии модель создаст концепт, а не точную копию товара.", reply_markup=marketplace_product_type())


@router.message(MarketplaceStates.waiting_photo, F.photo)
async def marketplace_receive_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    media = await media_storage.download_photo(bot, message.photo[-1].file_id)
    await state.update_data(input_image={"path": str(media.path), "filename": media.filename, "content_type": media.content_type})
    await state.set_state(MarketplaceStates.choosing_product_type)
    await message.answer("Фото принято. Выберите результат:", reply_markup=marketplace_product_type())


@router.message(MarketplaceStates.waiting_photo)
async def marketplace_photo_required(message: Message, state: FSMContext) -> None:
    if message.text == "❌ Отмена":
        await state.clear(); await message.answer("Действие отменено.", reply_markup=marketplace_menu()); return
    await message.answer("Пришлите фотографию товара или нажмите «❌ Отмена».")


@router.callback_query(MarketplaceStates.choosing_product_type, F.data.startswith("mp:type:"))
async def marketplace_choose_type(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(product_type=callback.data.rsplit(":", 1)[1])
    await state.set_state(MarketplaceStates.waiting_product_name)
    await callback.answer(); await callback.message.answer("Напишите точное название товара и категорию.")


async def _ask_marketplace_features(message: Message, state: FSMContext, category: str) -> None:
    await state.update_data(category=category)
    await state.set_state(MarketplaceStates.choosing_features_action)
    await message.answer(
        "Дополнительные характеристики указывать необязательно.\n\n"
        "Бот не будет ничего придумывать от себя.",
        reply_markup=marketplace_features_action(),
    )


@router.message(MarketplaceStates.waiting_product_name, F.text, ~F.text.startswith("/"))
async def marketplace_product_name(message: Message, state: FSMContext) -> None:
    product_name = message.text.strip()[:500]
    category = detect_category(product_name)
    await state.update_data(product_name=product_name)
    if category:
        await _ask_marketplace_features(message, state, category)
        return
    await state.set_state(MarketplaceStates.choosing_category)
    await message.answer(
        "Не удалось надёжно определить категорию. Выберите её:",
        reply_markup=marketplace_category(),
    )


@router.callback_query(MarketplaceStates.choosing_category, F.data.startswith("mp:category:"))
async def marketplace_choose_category(callback: CallbackQuery, state: FSMContext) -> None:
    category = callback.data.rsplit(":", 1)[1]
    await callback.answer()
    await _ask_marketplace_features(callback.message, state, category)


@router.callback_query(
    MarketplaceStates.choosing_features_action,
    F.data == "mp:features:write",
)
async def marketplace_features_write(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(MarketplaceStates.waiting_features)
    await callback.answer()
    await callback.message.answer(
        "Укажите только реальные характеристики товара.\n"
        "Например: материал, цвет, размер, вес, комплектация."
    )


@router.callback_query(
    MarketplaceStates.choosing_features_action,
    F.data == "mp:features:skip",
)
async def marketplace_features_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(features="")
    await state.set_state(MarketplaceStates.choosing_goal)
    await callback.answer()
    await callback.message.answer(
        "Выберите цель оформления:",
        reply_markup=marketplace_goal(),
    )


@router.message(MarketplaceStates.waiting_features, F.text, ~F.text.startswith("/"))
async def marketplace_features(message: Message, state: FSMContext) -> None:
    await state.update_data(features=message.text.strip()[:2000])
    await state.set_state(MarketplaceStates.choosing_goal)
    await message.answer("Выберите цель оформления:", reply_markup=marketplace_goal())


@router.callback_query(MarketplaceStates.choosing_goal, F.data.startswith("mp:goal:"))
async def marketplace_choose_goal(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(goal=callback.data.rsplit(":", 1)[1])
    await state.set_state(MarketplaceStates.choosing_platform)
    await callback.answer(); await callback.message.answer("Для какой площадки готовим карточку?", reply_markup=marketplace_platform())


@router.callback_query(MarketplaceStates.choosing_platform, F.data.startswith("mp:platform:"))
async def marketplace_choose_platform(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(platform=callback.data.rsplit(":", 1)[1])
    await state.set_state(MarketplaceStates.choosing_style)
    await callback.answer(); await callback.message.answer("Выберите визуальный стиль:", reply_markup=marketplace_style())


@router.callback_query(MarketplaceStates.choosing_style, F.data.startswith("mp:style:"))
async def marketplace_preview(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(style=callback.data.rsplit(":", 1)[1])
    data = await state.get_data()
    model_by_type = {"main":"marketplace-main","lifestyle":"marketplace-lifestyle","infographic":"marketplace-infographic","bundle":"marketplace-bundle-item"}
    model = get_model(model_by_type[data["product_type"]])
    count = 3 if data["product_type"] == "bundle" else 1
    unit_cost = db_manager.get_model_price_cached(model.key, model.token_cost)
    total = unit_cost * count
    await state.update_data(token_cost=total, unit_token_cost=unit_cost)
    await state.set_state(MarketplaceStates.confirming)
    await callback.answer(); await callback.message.answer(
        f"<b>Подтверждение</b>\n\nТовар: <b>{html.escape(data['product_name'])}</b>\nИзображений: <b>{count}</b>\nСтоимость: <b>{total} 💎</b>\n\nТекст на изображениях нейросеть не рисует: создаётся чистая визуальная основа без случайных надписей.",
        reply_markup=marketplace_confirm())


@router.callback_query(F.data == "mp:cancel")
async def marketplace_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    data=await state.get_data(); item=data.get("input_image")
    if item: await media_storage.remove(item.get("path"))
    await state.clear(); await callback.answer("Отменено"); await callback.message.answer("Выберите задачу:", reply_markup=marketplace_menu())


@router.callback_query(MarketplaceStates.confirming, F.data == "mp:confirm")
async def marketplace_generate(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = callback.from_user.id
    if not generation_guard.try_acquire(user_id):
        await callback.answer(
            "Предыдущая генерация ещё выполняется. Дождитесь результата.",
            show_alert=True,
        )
        return

    try:
        await _marketplace_generate_locked(callback, state)
    finally:
        generation_guard.release(user_id)


async def _marketplace_generate_locked(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    from pathlib import Path

    data = await state.get_data()
    total_cost = int(data.get("token_cost") or 0)
    if not settings.is_admin(callback.from_user.id):
        balance = await token_repository.get_user_tokens(callback.from_user.id)
        if balance < total_cost:
            await callback.answer(
                f"Для всего комплекта нужно {total_cost} 💎, на балансе {balance} 💎.",
                show_alert=True,
            )
            return

    await callback.answer("Генерация запущена")
    await state.set_state(MarketplaceStates.generating)

    input_data = data.get("input_image")
    input_image = None
    if input_data:
        input_image = LocalMedia(
            str(Path(input_data["path"])),
            input_data["filename"],
            input_data["content_type"],
        )

    prompts = build_prompts(
        data["product_type"],
        data["product_name"],
        data["features"],
        data["style"],
        data["goal"],
        data["platform"],
        data["category"],
        has_photo=input_image is not None,
    )
    status = await callback.message.answer(
        f"⏳ Создаю {len(prompts)} изображения…"
    )
    model_by_type = {
        "main": "marketplace-main",
        "lifestyle": "marketplace-lifestyle",
        "infographic": "marketplace-infographic",
        "bundle": "marketplace-bundle-item",
    }
    model_key = model_by_type[data["product_type"]]
    unit_cost = int(data.get("unit_token_cost") or get_model(model_key).token_cost)
    bundle_overrides = [
        {"width": 1024, "height": 1280, "strength": 0.42 if input_image else 0.72, "guidance_scale": 8, "seed": 1101},
        {"width": 1024, "height": 1280, "strength": 0.62 if input_image else 0.82, "guidance_scale": 9, "seed": 2202},
        {"width": 1024, "height": 1280, "strength": 0.50 if input_image else 0.76, "guidance_scale": 8, "seed": 3303},
    ]

    try:
        for index, prompt in enumerate(prompts, 1):
            logger.info(
                "Marketplace generation %s/%s, model=%s",
                index,
                len(prompts),
                model_key,
            )
            overrides = (
                bundle_overrides[index - 1]
                if data["product_type"] == "bundle"
                else {
                    "width": 1024,
                    "height": 1280,
                    "strength": 0.48 if input_image else 0.74,
                    "guidance_scale": 8,
                    "seed": 4404 + index,
                }
            )
            await _generate_marketplace_image(
                callback,
                prompt=prompt,
                model_key=model_key,
                input_image=input_image,
                overrides=overrides,
                token_cost=unit_cost,
                index=index,
                total=len(prompts),
                product_name=data["product_name"],
            )

        await status.edit_text(
            "✅ Готово. Все изображения комплекта созданы и отправлены."
        )
    except InsufficientBalanceError as exc:
        await status.edit_text(
            f"Недостаточно токенов: нужно {exc.required} 💎, "
            f"доступно {exc.balance} 💎.",
            reply_markup=get_token_packages_keyboard(),
        )
    except Exception:
        logger.exception("Ошибка карточки маркетплейса")
        await status.edit_text(
            "Не удалось создать карточку. Списание за неудачную попытку "
            "возвращено — попробуйте ещё раз позже."
        )
    finally:
        if input_image:
            await media_storage.remove(input_image)
        await state.clear()


async def _generate_marketplace_image(
    callback: CallbackQuery,
    *,
    prompt: str,
    model_key: str,
    input_image: LocalMedia | None,
    overrides: dict[str, Any],
    token_cost: int,
    index: int,
    total: int,
    product_name: str,
) -> None:
    """Создаёт одну карточку и гарантирует возврат при любом сбое."""
    charge = None
    try:
        for attempt in range(2):
            current_overrides = dict(overrides)
            if attempt:
                current_overrides["seed"] = int(current_overrides.get("seed", 0)) + 999

            charge, task = await generation_service.create_media_task(
                callback.from_user.id,
                model_key,
                prompt,
                input_image=input_image,
                overrides=current_overrides,
                token_cost=token_cost,
            )
            result = await _wait_media(task)
            urls = _collect_urls(result.get("output", result))
            if urls:
                await callback.message.answer_photo(
                    urls[0],
                    caption=(
                        f"Карточка {index}/{total} — {html.escape(product_name)}\n\n"
                        f"{MARKETPLACE_BRAND_CAPTION}"
                    ),
                )
                charge = None
                return

            await billing_service.refund(
                charge,
                "Пустой результат карточки маркетплейса",
            )
            charge = None
            logger.warning(
                "Marketplace: пустой результат, попытка %s/2, карточка %s",
                attempt + 1,
                index,
            )

        raise GenAPIError("Сервис не вернул изображение после повторной попытки")
    except asyncio.CancelledError:
        if charge is not None:
            await billing_service.refund(
                charge,
                "Карточка прервана перезапуском бота",
            )
        raise
    except Exception:
        if charge is not None:
            await billing_service.refund(
                charge,
                "Ошибка карточки маркетплейса",
            )
        raise
