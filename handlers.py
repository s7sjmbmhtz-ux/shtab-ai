"""
Все обработчики Telegram — FSM, команды, callback'и.
"""

import json
import re
import asyncio
from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from settings import settings
from models import (
    SalesScriptData, MarketingPostData, ImageGenerationData,
    GenerationStatus, ResponseType, TextOperation, TextEditorData, EditorSession,
    Tariff
)
from tools import prompt_registry, PromptContext, PromptMode
from tool_ids import ToolNames
from ai_service import ai_service
from database import user_repository, request_repository, limit_repository, token_repository
from keyboards import (
    get_main_menu,
    get_sales_menu_keyboard,
    get_marketing_menu_keyboard,
    get_images_menu_keyboard,
    get_communication_format_keyboard,
    get_platform_keyboard,
    get_style_keyboard,
    get_purpose_keyboard,
    get_image_style_keyboard,
    get_image_size_keyboard,
    get_script_result_keyboard,
    get_post_result_keyboard,
    get_image_result_keyboard,
    get_editor_operations_keyboard,
    get_editor_result_keyboard,
    get_editor_language_keyboard,
    get_back_to_menu_keyboard,
    get_tariffs_keyboard,
    get_marketplace_platform_keyboard,
    get_marketplace_task_keyboard,
    get_video_menu_keyboard,
    get_video_models_keyboard,
    get_video_duration_keyboard,
    get_skip_photo_keyboard,
    get_tokens_keyboard,
    get_tariff_and_tokens_keyboard,
    get_tokens_packages_keyboard,
    get_back_to_tariffs_keyboard,
    get_back_to_subscriptions_keyboard,
    get_referral_keyboard,
    PLATFORM_MAP, STYLE_MAP, PURPOSE_MAP, IMAGE_STYLE_MAP, SIZE_MAP,
    OPERATION_MAP, LANGUAGE_MAP
)
from utils import logger
from tool_runner import execute_tool
from response_helpers import send_pipeline_result
from tool_ids import ToolNames as ToolIds
from admin import is_admin
from services.subscription_service import (
    get_user_tariff, set_user_tariff, get_user_limit, get_subscription_end_date,
    get_user_tokens_balance, deduct_tokens_with_check
)
from services.usage_service import get_user_usage_today, track_usage, check_and_consume_limit
from tariffs import get_tariff, get_all_tariffs

router = Router()


# ==================== ВИДЕО МОДЕЛИ ====================

VIDEO_MODELS = {
    "ltx": {
        "name": "⚡ LTX Video",
        "description": "Быстрая генерация, базовое качество",
        "price_per_second": 5,
        "api_model": "ltx-video",
        "max_duration": 15,
        "resolution": "720p"
    },
    "cogvideo": {
        "name": "🎬 CogVideoX",
        "description": "Хорошее качество, стабильный",
        "price_per_second": 12,
        "api_model": "cogvideox",
        "max_duration": 10,
        "resolution": "1080p"
    },
    "kling_standard": {
        "name": "🎥 Kling Standard",
        "description": "Высокое качество",
        "price_per_second": 15,
        "api_model": "kling-v1",
        "max_duration": 10,
        "resolution": "1080p"
    },
    "luma_ray2": {
        "name": "🌈 Luma Ray2",
        "description": "Современное качество, плавные движения",
        "price_per_second": 20,
        "api_model": "luma-ray2",
        "max_duration": 9,
        "resolution": "1080p"
    },
    "kling_pro": {
        "name": "🌟 Kling Pro",
        "description": "Очень высокое качество, детализация",
        "price_per_second": 18,
        "api_model": "kling-v1-pro",
        "max_duration": 10,
        "resolution": "1080p"
    },
    "veo_lite": {
        "name": "🌟 Veo 3.1 Lite",
        "description": "Очень высокое качество, оптимальный выбор",
        "price_per_second": 12,
        "api_model": "veo-3.1-lite",
        "max_duration": 15,
        "resolution": "1080p"
    },
    "veo": {
        "name": "💎 Veo 3.1",
        "description": "Максимальное качество, до 4K",
        "price_per_second": 50,
        "api_model": "veo-3.1",
        "max_duration": 15,
        "resolution": "4K"
    },
    "runway_gen4": {
        "name": "🎞️ Runway Gen-4",
        "description": "Профессиональное качество, кинематографичный стиль",
        "price_per_second": 25,
        "api_model": "runway-gen4",
        "max_duration": 10,
        "resolution": "1080p"
    },
}


# ==================== FSM STATES ====================

class SalesStates(StatesGroup):
    menu = State()
    script_product = State()
    script_client = State()
    script_average_check = State()
    script_format = State()
    script_objections = State()
    script_result = State()
    script_refinement = State()
    cp_company = State()
    cp_client = State()
    cp_product = State()
    cp_problem = State()
    cp_price = State()
    cp_result = State()
    reply_question = State()
    reply_context = State()
    reply_result = State()
    analysis_text = State()
    analysis_result = State()
    objection_product = State()
    objection_list = State()
    objection_result = State()


class MarketingStates(StatesGroup):
    menu = State()
    post_product = State()
    post_audience = State()
    post_platform = State()
    post_style = State()
    post_result = State()
    post_refinement = State()
    content_plan_niche = State()
    content_plan_audience = State()
    content_plan_platform = State()
    content_plan_result = State()
    offer_product = State()
    offer_benefit = State()
    offer_audience = State()
    offer_result = State()
    email_topic = State()
    email_audience = State()
    email_goal = State()
    email_result = State()
    utp_product = State()
    utp_competitors = State()
    utp_benefit = State()
    utp_result = State()
    audience_product = State()
    audience_details = State()
    audience_result = State()


class ImageStates(StatesGroup):
    menu = State()
    description = State()
    purpose = State()
    style = State()
    size = State()
    result = State()
    refinement = State()


class VideoStates(StatesGroup):
    menu = State()
    model_choice = State()
    waiting_prompt = State()
    waiting_photo = State()
    waiting_duration = State()
    processing = State()
    result = State()


class EditorStates(StatesGroup):
    menu = State()
    waiting_text = State()
    waiting_operation = State()
    waiting_language = State()
    processing = State()
    result = State()
    refinement = State()


class MarketplaceStates(StatesGroup):
    menu = State()
    platform = State()
    task = State()
    category = State()
    product_info = State()
    result = State()
    refinement = State()


class AssistantStates(StatesGroup):
    menu = State()
    waiting_question = State()
    result = State()
    refinement = State()


# ==================== НОВЫЕ КНОПКИ ГЛАВНОГО МЕНЮ ====================

@router.message(F.text == "🎬 Создать видео")
async def menu_create_video(message: types.Message, state: FSMContext):
    """Создать видео - переход в раздел видео."""
    await enter_video(message, state)


@router.message(F.text == "🖼 Создать картинку")
async def menu_create_image(message: types.Message, state: FSMContext):
    """Создать картинку - переход в раздел изображений."""
    await enter_image(message, state)


@router.message(F.text == "🏢 Продажи")
async def menu_sales(message: types.Message, state: FSMContext):
    """Продажи."""
    await enter_sales(message, state)


@router.message(F.text == "📈 Маркетинг")
async def menu_marketing(message: types.Message, state: FSMContext):
    """Маркетинг."""
    await enter_marketing(message, state)


@router.message(F.text == "🤖 AI Ассистент")
async def menu_assistant(message: types.Message, state: FSMContext):
    """AI Ассистент."""
    await enter_assistant(message, state)


@router.message(F.text == "🛒 Маркетплейсы")
async def menu_marketplace(message: types.Message, state: FSMContext):
    """Маркетплейсы."""
    await enter_marketplace(message, state)


@router.message(F.text == "💰 Мой баланс")
async def menu_balance(message: types.Message, state: FSMContext):
    """Мой баланс."""
    await user_cabinet(message, state)


@router.message(F.text == "💳 Купить кредиты")
async def menu_buy_tokens(message: types.Message, state: FSMContext):
    """Купить кредиты."""
    await show_tokens_packages(message, state)


@router.message(F.text == "💎 Тарифы")
async def menu_tariffs(message: types.Message, state: FSMContext):
    """Тарифы."""
    await show_tariffs(message, state)


@router.message(F.text == "📞 Поддержка")
async def menu_support(message: types.Message, state: FSMContext):
    """Поддержка."""
    await message.answer(
        "📞 **Поддержка**\n\n"
        "Свяжитесь с нами:\n"
        "💬 Telegram: @ShtabProBot\n"
        "⏰ Время работы: 24/7\n\n"
        "Мы ответим в течение 15 минут! 🚀",
        parse_mode="HTML"
    )


@router.message(F.text == "🔙 Назад")
async def back_to_main_from_anywhere(message: types.Message, state: FSMContext):
    """Возврат в главное меню."""
    await state.clear()
    await message.answer(
        "👋 **Главное меню**",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )


# ==================== START ====================

@router.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    user = await user_repository.get_user(message.from_user.id)

    if user is None:
        await user_repository.add_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name
        )
        await set_user_tariff(message.from_user.id, Tariff.FREE)
        logger.info(f"Новый пользователь: {message.from_user.id}")
    else:
        await user_repository.update_activity(message.from_user.id)

    text = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Добро пожаловать в ШТАБ AI — твой AI-сотрудник для бизнеса.\n\n"
        "Выбери нужный раздел в меню ниже 👇"
    )

    await message.answer(text, reply_markup=get_main_menu())
    await state.clear()
    logger.info(f"Пользователь {message.from_user.id} выполнил /start")


@router.message(F.text == "Главное меню")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Вы вернулись в главное меню", reply_markup=get_main_menu())


# ==================== ПРОДАЖИ ====================

@router.message(F.text == "🏢 Продажи")
async def enter_sales(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(SalesStates.menu)
    await message.answer(
        "📊 Раздел «Продажи»\n\nВыберите инструмент:",
        reply_markup=get_sales_menu_keyboard()
    )


@router.message(F.text == "📞 Скрипт продаж")
async def start_script(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(SalesStates.script_product)
    await message.answer(
        "📝 Создание скрипта продаж\n\n"
        "Шаг 1 из 5\nЧто вы продаёте?",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(SalesStates.script_product))
async def script_product(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_script(message, state)
        return
    await state.update_data(product=message.text)
    await state.set_state(SalesStates.script_client)
    await message.answer("Шаг 2 из 5\nКто ваш клиент?")


@router.message(StateFilter(SalesStates.script_client))
async def script_client(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_script(message, state)
        return
    await state.update_data(client=message.text)
    await state.set_state(SalesStates.script_average_check)
    await message.answer("Шаг 3 из 5\nКакой у вас средний чек?")


@router.message(StateFilter(SalesStates.script_average_check))
async def script_check(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_script(message, state)
        return
    await state.update_data(average_check=message.text)
    await state.set_state(SalesStates.script_format)
    await message.answer(
        "Шаг 4 из 5\nВыберите формат общения:",
        reply_markup=get_communication_format_keyboard()
    )


@router.message(StateFilter(SalesStates.script_format))
async def script_format(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_script(message, state)
        return
    valid = ["📞 Холодный звонок", "☎️ Тёплый звонок", "💬 Переписка", "🤝 Личная встреча"]
    if message.text not in valid:
        await message.answer("❌ Выберите вариант из кнопок.", reply_markup=get_communication_format_keyboard())
        return
    await state.update_data(communication_format=message.text)
    await state.set_state(SalesStates.script_objections)
    await message.answer(
        "Шаг 5 из 5\nКакие основные возражения вы слышите?",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(SalesStates.script_objections))
async def script_objections(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_script(message, state)
        return
    await state.update_data(objections=message.text)
    await generate_script(message, state)


async def generate_script(message: types.Message, state: FSMContext):
    data = await state.get_data()
    required = ["product", "client", "average_check", "communication_format", "objections"]
    if any(f not in data for f in required):
        await message.answer("⚠️ Заполните все шаги.")
        return

    loading = await message.answer("⏳ Генерирую...")

    try:
        result = await execute_tool(
            tool_id=ToolIds.SALES_SCRIPT,
            user_id=message.from_user.id,
            input_data=data,
            session=None,
            mode="initial"
        )

        try:
            await loading.delete()
        except Exception:
            pass

        if await send_pipeline_result(
            message,
            state,
            result,
            "💰 Ваш скрипт готов!",
            get_script_result_keyboard()
        ):
            await state.set_state(SalesStates.script_result)

    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        logger.error(f"Ошибка: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже.")


async def cancel_script(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(SalesStates.menu)
    await message.answer("❌ Отменено.", reply_markup=get_sales_menu_keyboard())


@router.message(F.text == "📑 Коммерческое предложение")
async def start_cp(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(SalesStates.cp_company)
    await message.answer(
        "📑 Создание коммерческого предложения\n\n"
        "Шаг 1 из 5\nНазвание вашей компании:",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(SalesStates.cp_company))
async def cp_company(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_cp(message, state)
        return
    await state.update_data(company=message.text)
    await state.set_state(SalesStates.cp_client)
    await message.answer("Шаг 2 из 5\nКто ваш клиент (компания/должность)?")


@router.message(StateFilter(SalesStates.cp_client))
async def cp_client(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_cp(message, state)
        return
    await state.update_data(client=message.text)
    await state.set_state(SalesStates.cp_product)
    await message.answer("Шаг 3 из 5\nЧто вы предлагаете? (продукт/услуга)")


@router.message(StateFilter(SalesStates.cp_product))
async def cp_product(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_cp(message, state)
        return
    await state.update_data(product=message.text)
    await state.set_state(SalesStates.cp_problem)
    await message.answer("Шаг 4 из 5\nКакую проблему решает ваш продукт?")


@router.message(StateFilter(SalesStates.cp_problem))
async def cp_problem(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_cp(message, state)
        return
    await state.update_data(problem=message.text)
    await state.set_state(SalesStates.cp_price)
    await message.answer("Шаг 5 из 5\nСтоимость (или ценовой диапазон):")


@router.message(StateFilter(SalesStates.cp_price))
async def cp_price(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_cp(message, state)
        return
    await state.update_data(price=message.text)
    await generate_cp(message, state)


async def generate_cp(message: types.Message, state: FSMContext):
    data = await state.get_data()
    required = ["company", "client", "product", "problem", "price"]
    if any(f not in data for f in required):
        await message.answer("⚠️ Заполните все шаги.")
        return

    loading = await message.answer("📑 Генерирую коммерческое предложение...")

    try:
        result = await execute_tool(
            tool_id=ToolIds.SALES_SCRIPT,
            user_id=message.from_user.id,
            input_data={
                "product": data.get("product", ""),
                "client": data.get("client", ""),
                "audience": data.get("client", ""),
                "average_check": data.get("price", ""),
                "communication_format": "Коммерческое предложение",
                "objections": f"Компания: {data.get('company', '')}\nПроблема: {data.get('problem', '')}"
            },
            session=None,
            mode="initial"
        )

        try:
            await loading.delete()
        except Exception:
            pass

        await send_pipeline_result(
            message,
            state,
            result,
            "📑 Ваше коммерческое предложение готово!",
            None
        )

    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        logger.error(f"Ошибка генерации КП: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже.")


async def cancel_cp(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(SalesStates.menu)
    await message.answer("❌ Отменено.", reply_markup=get_sales_menu_keyboard())


@router.message(F.text == "💬 Ответ клиенту")
async def start_reply(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(SalesStates.reply_question)
    await message.answer(
        "💬 Ответ клиенту\n\n"
        "Шаг 1 из 2\nЧто спрашивает клиент? (опишите вопрос или ситуацию)",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(SalesStates.reply_question))
async def reply_question(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_reply(message, state)
        return
    await state.update_data(question=message.text)
    await state.set_state(SalesStates.reply_context)
    await message.answer(
        "Шаг 2 из 2\nДополнительный контекст (необязательно):\n"
        "Например: какой товар, какая цена, какие были предыдущие сообщения"
    )


@router.message(StateFilter(SalesStates.reply_context))
async def reply_context(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_reply(message, state)
        return
    await state.update_data(context=message.text)
    await generate_reply(message, state)


async def generate_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()

    loading = await message.answer("💬 Генерирую ответ...")

    try:
        result = await execute_tool(
            tool_id=ToolIds.SALES_SCRIPT,
            user_id=message.from_user.id,
            input_data={
                "product": "Ответ клиенту",
                "client": "Клиент",
                "audience": "Клиент",
                "average_check": "0",
                "communication_format": "Переписка",
                "objections": f"Вопрос клиента: {data.get('question', '')}\nКонтекст: {data.get('context', '')}"
            },
            session=None,
            mode="initial"
        )

        try:
            await loading.delete()
        except Exception:
            pass

        await send_pipeline_result(
            message,
            state,
            result,
            "💬 Готовый ответ клиенту:",
            None
        )

    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        logger.error(f"Ошибка генерации ответа: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже.")


async def cancel_reply(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(SalesStates.menu)
    await message.answer("❌ Отменено.", reply_markup=get_sales_menu_keyboard())


@router.message(F.text == "📊 Анализ переписки")
async def start_analysis(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(SalesStates.analysis_text)
    await message.answer(
        "📊 Анализ переписки\n\n"
        "Вставьте текст переписки (диалог с клиентом) для анализа.\n\n"
        "Я выявлю:\n"
        "• Качество обработки возражений\n"
        "• Эффективность вопросов\n"
        "• Точки роста\n"
        "• Рекомендации по улучшению",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(SalesStates.analysis_text))
async def analysis_text(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_analysis(message, state)
        return
    
    if len(message.text) < 10:
        await message.answer("❌ Текст слишком короткий. Отправьте диалог (минимум 10 символов).")
        return
    
    await state.update_data(text=message.text)
    await generate_analysis(message, state)


async def generate_analysis(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = data.get("text", "")

    if len(text) < 10:
        await message.answer("❌ Текст слишком короткий. Отправьте диалог (минимум 10 символов).")
        return

    loading = await message.answer("📊 Анализирую переписку... Это может занять до 30 секунд. Пожалуйста, подождите.")

    try:
        max_text_length = 1500
        if len(text) > max_text_length:
            text = text[:max_text_length] + "\n...(текст обрезан для анализа)"

        analysis_prompt = f"""
Проанализируй эту переписку как эксперт по продажам. Дай краткий, конкретный ответ без лишней воды.

Переписка:
{text}

1. Кто участники диалога?
2. Какие ошибки допустил продавец? (конкретно, по пунктам)
3. Что нужно было сказать вместо этого? (конкретные фразы)
4. Оценка работы продавца (от 1 до 10):
5. Один главный совет:
"""

        from ai_service import ai_service
        from models import ResponseType, GenerationStatus
        
        ai_result = await ai_service.generate(
            provider_type="text",
            response_type=ResponseType.TEXT,
            prompt=analysis_prompt,
            model="deepseek-chat",
            temperature=0.7
        )

        try:
            await loading.delete()
        except Exception:
            pass

        if ai_result.status != GenerationStatus.SUCCESS:
            await message.answer("❌ Ошибка генерации анализа. Попробуйте позже.")
            return

        content = ai_result.content
        
        content = re.sub(r'\*\*(.+?)\*\*', r'\1', content)
        content = re.sub(r'\*(.+?)\*', r'\1', content)
        content = re.sub(r'^#+\s*(.+?)$', r'\1', content, flags=re.MULTILINE)
        content = re.sub(r'_{3,}', '', content)
        content = re.sub(r'-{3,}', '', content)

        await state.update_data(last_response=ai_result.content)

        await message.answer(
            f"📊 Анализ переписки\n\n{content}\n\n⏱ {ai_result.elapsed:.2f} сек",
            reply_markup=None
        )

    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        logger.error(f"Ошибка анализа: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже.")


async def cancel_analysis(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(SalesStates.menu)
    await message.answer("❌ Отменено.", reply_markup=get_sales_menu_keyboard())


@router.message(F.text == "🛡️ Работа с возражениями")
async def start_objections(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(SalesStates.objection_product)
    await message.answer(
        "🛡️ Работа с возражениями\n\n"
        "Шаг 1 из 2\nЧто вы продаёте?",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(SalesStates.objection_product))
async def objection_product(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_objections(message, state)
        return
    await state.update_data(product=message.text)
    await state.set_state(SalesStates.objection_list)
    await message.answer(
        "Шаг 2 из 2\nКакие возражения вы слышите?\n"
        "Перечислите через запятую или каждое с новой строки"
    )


@router.message(StateFilter(SalesStates.objection_list))
async def objection_list(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_objections(message, state)
        return
    await state.update_data(objections=message.text)
    await generate_objections(message, state)


async def generate_objections(message: types.Message, state: FSMContext):
    data = await state.get_data()
    required = ["product", "objections"]
    if any(f not in data for f in required):
        await message.answer("⚠️ Заполните все шаги.")
        return

    loading = await message.answer("🛡️ Готовлю ответы на возражения...")

    try:
        result = await execute_tool(
            tool_id=ToolIds.SALES_SCRIPT,
            user_id=message.from_user.id,
            input_data={
                "product": data.get("product", ""),
                "client": "Клиент",
                "audience": "Клиент",
                "average_check": "0",
                "communication_format": "Переписка",
                "objections": data.get("objections", "")
            },
            session=None,
            mode="initial"
        )

        try:
            await loading.delete()
        except Exception:
            pass

        await send_pipeline_result(
            message,
            state,
            result,
            "🛡️ Готовые ответы на возражения:",
            None
        )

    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        logger.error(f"Ошибка генерации ответов на возражения: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже.")


async def cancel_objections(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(SalesStates.menu)
    await message.answer("❌ Отменено.", reply_markup=get_sales_menu_keyboard())


@router.callback_query(F.data == "sales_new_script")
async def sales_new(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await start_script(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "sales_main_menu")
async def sales_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.clear()
    await state.set_state(SalesStates.menu)
    await callback.message.answer(
        "📊 Раздел «Продажи»",
        reply_markup=get_sales_menu_keyboard()
    )
    await callback.answer()


@router.message(StateFilter(SalesStates.menu), F.text == "⬅️ Назад")
async def back_from_sales_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Главное меню", reply_markup=get_main_menu())


@router.message(StateFilter(MarketingStates.menu), F.text == "⬅️ Назад")
async def back_from_marketing_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Главное меню", reply_markup=get_main_menu())


@router.message(StateFilter(ImageStates.menu), F.text == "⬅️ Назад")
async def back_from_image_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Главное меню", reply_markup=get_main_menu())


@router.message(StateFilter(VideoStates.menu), F.text == "⬅️ Назад")
async def back_from_video_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Главное меню", reply_markup=get_main_menu())


@router.message(StateFilter(MarketplaceStates.menu), F.text == "⬅️ Назад")
async def back_from_marketplace_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Главное меню", reply_markup=get_main_menu())


@router.message(StateFilter(AssistantStates.menu), F.text == "⬅️ Назад")
async def back_from_assistant_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("👋 Главное меню", reply_markup=get_main_menu())


# ==================== МАРКЕТИНГ ====================

@router.message(F.text == "📈 Маркетинг")
async def enter_marketing(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(MarketingStates.menu)
    await message.answer(
        "📊 Раздел «Маркетинг»\n\nВыберите инструмент:",
        reply_markup=get_marketing_menu_keyboard()
    )


@router.message(F.text == "📝 Продающий пост")
async def start_post(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(MarketingStates.post_product)
    await message.answer(
        "📝 Создание поста\n\nШаг 1 из 4\nЧто продаёте?",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(MarketingStates.post_product))
async def post_product(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_post(message, state)
        return
    await state.update_data(product=message.text)
    await state.set_state(MarketingStates.post_audience)
    await message.answer("Шаг 2 из 4\nКто ваша ЦА?")


@router.message(StateFilter(MarketingStates.post_audience))
async def post_audience(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_post(message, state)
        return
    await state.update_data(audience=message.text)
    await state.set_state(MarketingStates.post_platform)
    await message.answer(
        "Шаг 3 из 4\nГде публикуете?",
        reply_markup=get_platform_keyboard()
    )


@router.message(StateFilter(MarketingStates.post_platform))
async def post_platform(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_post(message, state)
        return
    if message.text not in PLATFORM_MAP:
        await message.answer("❌ Выберите из кнопок.", reply_markup=get_platform_keyboard())
        return
    await state.update_data(platform=PLATFORM_MAP[message.text])
    await state.set_state(MarketingStates.post_style)
    await message.answer(
        "Шаг 4 из 4\nВыберите стиль:",
        reply_markup=get_style_keyboard()
    )


@router.message(StateFilter(MarketingStates.post_style))
async def post_style(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_post(message, state)
        return
    if message.text not in STYLE_MAP:
        await message.answer("❌ Выберите из кнопок.", reply_markup=get_style_keyboard())
        return
    await state.update_data(style=STYLE_MAP[message.text])
    await generate_post(message, state)


async def generate_post(message: types.Message, state: FSMContext):
    data = await state.get_data()
    required = ["product", "audience", "platform", "style"]
    if any(f not in data for f in required):
        await message.answer("⚠️ Заполните все шаги.")
        return

    loading = await message.answer("⏳ Генерирую...")

    try:
        result = await execute_tool(
            tool_id=ToolIds.MARKETING_POST,
            user_id=message.from_user.id,
            input_data=data,
            session=None,
            mode="initial"
        )

        try:
            await loading.delete()
        except Exception:
            pass

        if await send_pipeline_result(
            message,
            state,
            result,
            "📝 Ваш пост готов!",
            get_post_result_keyboard()
        ):
            await state.set_state(MarketingStates.post_result)

    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        logger.error(f"Ошибка: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже.")


async def cancel_post(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(MarketingStates.menu)
    await message.answer("❌ Отменено.", reply_markup=get_marketing_menu_keyboard())


@router.message(F.text == "📅 Контент-план")
async def start_content_plan(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(MarketingStates.content_plan_niche)
    await message.answer(
        "📅 Создание контент-плана\n\n"
        "Шаг 1 из 3\nКакая у вас ниша?",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(MarketingStates.content_plan_niche))
async def content_plan_niche(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(niche=message.text)
    await state.set_state(MarketingStates.content_plan_audience)
    await message.answer("Шаг 2 из 3\nКто ваша целевая аудитория?")


@router.message(StateFilter(MarketingStates.content_plan_audience))
async def content_plan_audience(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(audience=message.text)
    await state.set_state(MarketingStates.content_plan_platform)
    await message.answer("Шаг 3 из 3\nКакие платформы? (Telegram, Instagram, VK, и т.д.)")


@router.message(StateFilter(MarketingStates.content_plan_platform))
async def content_plan_platform(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(platform=message.text)
    await generate_content_plan(message, state)


async def generate_content_plan(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if any(f not in data for f in ["niche", "audience", "platform"]):
        await message.answer("⚠️ Заполните все шаги.")
        return

    loading = await message.answer("📅 Генерирую контент-план...")
    try:
        result = await execute_tool(
            tool_id=ToolIds.MARKETING_POST,
            user_id=message.from_user.id,
            input_data={
                "product": data.get("niche", ""),
                "audience": data.get("audience", ""),
                "platform": data.get("platform", "Telegram"),
                "style": "Информационный"
            },
            session=None,
            mode="initial"
        )
        try:
            await loading.delete()
        except Exception:
            pass
        await send_pipeline_result(message, state, result, "📅 Ваш контент-план готов!", None)
    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        logger.error(f"Ошибка: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже.")


@router.message(F.text == "🎯 Рекламный оффер")
async def start_offer(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(MarketingStates.offer_product)
    await message.answer(
        "🎯 Создание рекламного оффера\n\n"
        "Шаг 1 из 3\nЧто вы продаёте?",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(MarketingStates.offer_product))
async def offer_product(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(product=message.text)
    await state.set_state(MarketingStates.offer_benefit)
    await message.answer("Шаг 2 из 3\nКакая главная выгода для клиента?")


@router.message(StateFilter(MarketingStates.offer_benefit))
async def offer_benefit(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(benefit=message.text)
    await state.set_state(MarketingStates.offer_audience)
    await message.answer("Шаг 3 из 3\nКто ваша целевая аудитория?")


@router.message(StateFilter(MarketingStates.offer_audience))
async def offer_audience(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(audience=message.text)
    await generate_offer(message, state)


async def generate_offer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if any(f not in data for f in ["product", "benefit", "audience"]):
        await message.answer("⚠️ Заполните все шаги.")
        return

    loading = await message.answer("🎯 Генерирую рекламный оффер...")
    try:
        result = await execute_tool(
            tool_id=ToolIds.MARKETING_POST,
            user_id=message.from_user.id,
            input_data={
                "product": data.get("product", ""),
                "audience": data.get("audience", ""),
                "platform": "Реклама",
                "style": "Продающий"
            },
            session=None,
            mode="initial"
        )
        try:
            await loading.delete()
        except Exception:
            pass
        await send_pipeline_result(message, state, result, "🎯 Ваш рекламный оффер готов!", None)
    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        logger.error(f"Ошибка: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже.")


@router.message(F.text == "📧 Email-рассылка")
async def start_email(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(MarketingStates.email_topic)
    await message.answer(
        "📧 Создание Email-рассылки\n\n"
        "Шаг 1 из 3\nТема письма:",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(MarketingStates.email_topic))
async def email_topic(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(topic=message.text)
    await state.set_state(MarketingStates.email_audience)
    await message.answer("Шаг 2 из 3\nКто получатели?")


@router.message(StateFilter(MarketingStates.email_audience))
async def email_audience(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(audience=message.text)
    await state.set_state(MarketingStates.email_goal)
    await message.answer("Шаг 3 из 3\nКакая цель письма? (продажа, информирование, приглашение)")


@router.message(StateFilter(MarketingStates.email_goal))
async def email_goal(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(goal=message.text)
    await generate_email(message, state)


async def generate_email(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if any(f not in data for f in ["topic", "audience", "goal"]):
        await message.answer("⚠️ Заполните все шаги.")
        return

    loading = await message.answer("📧 Генерирую Email-рассылку...")
    try:
        result = await execute_tool(
            tool_id=ToolIds.MARKETING_POST,
            user_id=message.from_user.id,
            input_data={
                "product": data.get("topic", ""),
                "audience": data.get("audience", ""),
                "platform": "Email",
                "style": data.get("goal", "информирование")
            },
            session=None,
            mode="initial"
        )
        try:
            await loading.delete()
        except Exception:
            pass
        await send_pipeline_result(message, state, result, "📧 Ваша Email-рассылка готова!", None)
    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        logger.error(f"Ошибка: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже.")


@router.message(F.text == "💎 УТП")
async def start_utp(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(MarketingStates.utp_product)
    await message.answer(
        "💎 Создание УТП\n\n"
        "Шаг 1 из 3\nЧто вы продаёте?",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(MarketingStates.utp_product))
async def utp_product(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(product=message.text)
    await state.set_state(MarketingStates.utp_competitors)
    await message.answer("Шаг 2 из 3\nКто ваши основные конкуренты?")


@router.message(StateFilter(MarketingStates.utp_competitors))
async def utp_competitors(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(competitors=message.text)
    await state.set_state(MarketingStates.utp_benefit)
    await message.answer("Шаг 3 из 3\nВаше главное преимущество?")


@router.message(StateFilter(MarketingStates.utp_benefit))
async def utp_benefit(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(benefit=message.text)
    await generate_utp(message, state)


async def generate_utp(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if any(f not in data for f in ["product", "competitors", "benefit"]):
        await message.answer("⚠️ Заполните все шаги.")
        return

    loading = await message.answer("💎 Генерирую УТП...")
    try:
        result = await execute_tool(
            tool_id=ToolIds.MARKETING_POST,
            user_id=message.from_user.id,
            input_data={
                "product": data.get("product", ""),
                "audience": data.get("competitors", ""),
                "platform": "Позиционирование",
                "style": "Экспертный"
            },
            session=None,
            mode="initial"
        )
        try:
            await loading.delete()
        except Exception:
            pass
        await send_pipeline_result(message, state, result, "💎 Ваше УТП готово!", None)
    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        logger.error(f"Ошибка: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже.")


@router.message(F.text == "🔍 Анализ ЦА")
async def start_audience_analysis(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(MarketingStates.audience_product)
    await message.answer(
        "🔍 Анализ ЦА\n\n"
        "Шаг 1 из 2\nЧто вы продаёте?",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(MarketingStates.audience_product))
async def audience_product(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(product=message.text)
    await state.set_state(MarketingStates.audience_details)
    await message.answer("Шаг 2 из 2\nДополнительная информация (кто ваши клиенты, их проблемы, возраст и т.д.)")


@router.message(StateFilter(MarketingStates.audience_details))
async def audience_details(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketing_tool(message, state)
        return
    await state.update_data(details=message.text)
    await generate_audience_analysis(message, state)


async def generate_audience_analysis(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if any(f not in data for f in ["product", "details"]):
        await message.answer("⚠️ Заполните все шаги.")
        return

    loading = await message.answer("🔍 Анализирую целевую аудиторию...")
    try:
        result = await execute_tool(
            tool_id=ToolIds.MARKETING_POST,
            user_id=message.from_user.id,
            input_data={
                "product": data.get("product", ""),
                "audience": data.get("details", ""),
                "platform": "Аналитика",
                "style": "Информационный"
            },
            session=None,
            mode="initial"
        )
        try:
            await loading.delete()
        except Exception:
            pass
        await send_pipeline_result(message, state, result, "🔍 Анализ ЦА готов!", None)
    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        logger.error(f"Ошибка: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже.")


async def cancel_marketing_tool(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(MarketingStates.menu)
    await message.answer("❌ Отменено.", reply_markup=get_marketing_menu_keyboard())


@router.callback_query(F.data == "marketing_new_post")
async def marketing_new(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await start_post(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "marketing_main_menu")
async def marketing_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.clear()
    await state.set_state(MarketingStates.menu)
    await callback.message.answer(
        "📊 Раздел «Маркетинг»",
        reply_markup=get_marketing_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "marketing_share_post")
async def share_post(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    response = data.get("last_response", "")
    if not response:
        await callback.answer("⚠️ Данных нет", show_alert=True)
        return
    await callback.message.answer(f"📤 Ваш пост\n\n{response}")
    await callback.answer()


# ==================== ИЗОБРАЖЕНИЯ ====================

@router.message(F.text == "🖼 Создать картинку")
async def enter_image(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(ImageStates.menu)
    await message.answer(
        "🖼 Генерация изображения\n\n"
        "Шаг 1 из 4\nЧто нужно изобразить?",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(ImageStates.description))
async def image_description(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_image(message, state)
        return
    await state.update_data(description=message.text)
    await state.set_state(ImageStates.purpose)
    await message.answer(
        "Шаг 2 из 4\nДля чего изображение?",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(ImageStates.purpose))
async def image_purpose(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_image(message, state)
        return
    await state.update_data(purpose=message.text)
    await state.set_state(ImageStates.style)
    await message.answer(
        "Шаг 3 из 4\nВыберите стиль:",
        reply_markup=get_image_style_keyboard()
    )


@router.message(StateFilter(ImageStates.style))
async def image_style(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_image(message, state)
        return
    valid = ["🎨 Реалистичный", "✨ Минимализм", "🎭 3D", "🖌 Иллюстрация"]
    if message.text not in valid:
        await message.answer("❌ Выберите стиль из кнопок.", reply_markup=get_image_style_keyboard())
        return
    await state.update_data(style=message.text)
    await state.set_state(ImageStates.size)
    await message.answer(
        "Шаг 4 из 4\nВыберите размер:",
        reply_markup=get_image_size_keyboard()
    )


@router.message(StateFilter(ImageStates.size))
async def image_size(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_image(message, state)
        return
    valid = ["⬜ Квадрат", "⬆️ Вертикальный", "↔️ Горизонтальный"]
    if message.text not in valid:
        await message.answer("❌ Выберите размер из кнопок.", reply_markup=get_image_size_keyboard())
        return
    await state.update_data(size=message.text)
    await generate_image_result(message, state)


async def generate_image_result(message: types.Message, state: FSMContext):
    data = await state.get_data()
    result = await execute_tool(
        tool_id=ToolIds.IMAGE_CREATIVE,
        user_id=message.from_user.id,
        input_data=data,
        session=None,
        mode="initial"
    )
    await send_pipeline_result(
        message,
        state,
        result,
        "🖼 Ваше изображение готово!",
        get_image_result_keyboard()
    )


async def cancel_image(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(ImageStates.menu)
    await message.answer("❌ Отменено.", reply_markup=get_images_menu_keyboard())


@router.callback_query(F.data == "image_new")
async def image_new(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await enter_image(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "image_menu")
async def image_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.clear()
    await callback.message.answer("👋 Главное меню", reply_markup=get_main_menu())
    await callback.answer()


# ==================== ВИДЕО ====================

@router.message(F.text == "🎬 Создать видео")
async def enter_video(message: types.Message, state: FSMContext):
    """Вход в раздел «Видео»."""
    await state.clear()
    await state.set_state(VideoStates.menu)
    
    text = (
        "🎬 **Раздел «Видео»**\n\n"
        "Создавайте видео с помощью нейросетей.\n\n"
        "📌 **Как это работает:**\n"
        "1. Выберите модель\n"
        "2. Напишите промт\n"
        "3. (Опционально) Загрузите фото-референс\n"
        "4. Выберите длительность\n"
        "5. Получите готовое видео\n\n"
        "💡 Токены списываются за каждую секунду видео."
    )
    
    await message.answer(
        text,
        reply_markup=get_video_menu_keyboard(),
        parse_mode="HTML"
    )


@router.message(StateFilter(VideoStates.menu), F.text == "🎬 Создать видео")
async def start_video_creation(message: types.Message, state: FSMContext):
    """Начало создания видео — выбор модели."""
    await state.set_state(VideoStates.model_choice)
    
    text = "🎬 **Выберите модель для генерации видео:**\n\n"
    
    for key, model in VIDEO_MODELS.items():
        text += (
            f"• **{model['name']}**\n"
            f"  _{model['description']}_\n"
            f"  💰 {model['price_per_second']} токенов/сек\n"
            f"  📐 {model['resolution']} | ⏱️ до {model['max_duration']} сек\n\n"
        )
    
    await message.answer(
        text,
        reply_markup=get_video_models_keyboard(),
        parse_mode="HTML"
    )


@router.message(StateFilter(VideoStates.menu), F.text == "⬅️ Назад")
async def back_from_video_menu(message: types.Message, state: FSMContext):
    """Возврат в главное меню из раздела видео."""
    await state.clear()
    await message.answer("👋 Главное меню", reply_markup=get_main_menu())


@router.message(StateFilter(VideoStates.model_choice))
async def choose_video_model(message: types.Message, state: FSMContext):
    """Обработка выбора модели."""
    if message.text == "⬅️ Назад":
        await state.set_state(VideoStates.menu)
        await message.answer(
            "🎬 Раздел «Видео»",
            reply_markup=get_video_menu_keyboard()
        )
        return
    
    selected_model = None
    for key, model in VIDEO_MODELS.items():
        if model["name"] in message.text:
            selected_model = {**model, "key": key}
            break
    
    if not selected_model:
        await message.answer(
            "❌ Пожалуйста, выберите модель из кнопок выше.",
            reply_markup=get_video_models_keyboard()
        )
        return
    
    await state.update_data(model=selected_model)
    await state.set_state(VideoStates.waiting_prompt)
    
    await message.answer(
        f"✅ Выбрана модель: **{selected_model['name']}**\n\n"
        "📝 Напишите промт (описание того, что хотите создать).\n\n"
        "📸 *Опционально:* вы также можете загрузить фото как референс.\n"
        "Просто отправьте фото до или после промта.",
        reply_markup=get_skip_photo_keyboard(),
        parse_mode="HTML"
    )


@router.message(StateFilter(VideoStates.waiting_prompt), F.photo)
async def get_photo_on_video_prompt(message: types.Message, state: FSMContext):
    """Обработка фото на этапе промта."""
    photo = message.photo[-1]
    file_id = photo.file_id
    await state.update_data(photo_file_id=file_id)
    await message.answer(
        "📸 Фото получено! Теперь напишите промт.\n"
        "Если хотите сгенерировать только по тексту — просто отправьте текст.",
        reply_markup=get_skip_photo_keyboard()
    )


@router.message(StateFilter(VideoStates.waiting_prompt))
async def get_video_prompt(message: types.Message, state: FSMContext):
    """Получение промта для видео."""
    if message.text == "⬅️ Назад":
        await cancel_video_creation(message, state)
        return
    
    if message.text == "⏭ Пропустить фото":
        await state.update_data(photo_file_id=None)
        await message.answer("⏭ Фото пропущено. Продолжаем с текстовым промптом.")
        return
    
    if len(message.text) < 3:
        await message.answer("❌ Промт слишком короткий. Напишите хотя бы 3 символа.")
        return
    
    await state.update_data(prompt=message.text)
    await state.set_state(VideoStates.waiting_duration)
    
    data = await state.get_data()
    model = data.get("model", {})
    max_duration = model.get("max_duration", 15)
    
    await message.answer(
        f"⏱️ **Выберите длительность видео:**\n\n"
        f"💡 Доступно: 5, 10, 15 секунд\n"
        f"📌 Максимум для этой модели: {max_duration} сек",
        reply_markup=get_video_duration_keyboard(max_duration)
    )


@router.message(StateFilter(VideoStates.waiting_duration))
async def get_video_duration(message: types.Message, state: FSMContext):
    """Получение длительности видео."""
    if message.text == "⬅️ Назад":
        await cancel_video_creation(message, state)
        return
    
    duration_map = {
        "5 секунд": 5,
        "10 секунд": 10,
        "15 секунд": 15,
    }
    
    if message.text not in duration_map:
        await message.answer(
            "❌ Выберите длительность из кнопок: 5, 10 или 15 секунд.",
            reply_markup=get_video_duration_keyboard()
        )
        return
    
    duration = duration_map[message.text]
    
    data = await state.get_data()
    model = data.get("model", {})
    max_duration = model.get("max_duration", 15)
    
    if duration > max_duration:
        await message.answer(
            f"❌ Для модели **{model.get('name', '...')}** максимальная длительность — {max_duration} сек.\n"
            f"Пожалуйста, выберите меньшее значение.",
            reply_markup=get_video_duration_keyboard(max_duration)
        )
        return
    
    await state.update_data(duration=duration)
    await generate_video(message, state)


async def generate_video(message: types.Message, state: FSMContext):
    """Генерация видео."""
    data = await state.get_data()
    user_id = message.from_user.id
    
    model = data.get("model", {})
    prompt = data.get("prompt", "")
    duration = data.get("duration", 5)
    photo_file_id = data.get("photo_file_id")
    
    price_per_second = model.get("price_per_second", 5)
    required_tokens = duration * price_per_second
    
    # ==================== ПРОВЕРКА ДЛЯ АДМИНА ====================
    # Если админ — пропускаем проверку токенов
    if is_admin(user_id):
        tokens = 999999  # Бесконечность для админа
        logger.info(f"👑 Админ {user_id} генерирует видео без списания токенов")
    else:
        # Проверяем баланс токенов для обычных пользователей
        tokens = await get_user_tokens_balance(user_id)
        
        if tokens < required_tokens:
            await message.answer(
                f"❌ **Недостаточно токенов.**\n\n"
                f"🎯 Модель: {model.get('name', '...')}\n"
                f"⏱️ Длительность: {duration} сек\n"
                f"💰 Нужно: **{required_tokens}** токенов\n"
                f"💳 У вас: **{tokens}** токенов\n\n"
                f"Пополните баланс через «💳 Купить кредиты»",
                parse_mode="HTML"
            )
            return
    
    # ==================== СПИСАНИЕ ТОКЕНОВ ====================
    # Если НЕ админ — списываем токены
    if not is_admin(user_id):
        success = await deduct_tokens_with_check(
            user_id, 
            required_tokens, 
            f"Генерация видео {duration} сек на {model.get('name', '...')}"
        )
        
        if not success:
            await message.answer(
                "❌ Ошибка списания токенов. Попробуйте позже.",
                parse_mode="HTML"
            )
            return
    else:
        # Для админа просто логируем
        logger.info(f"👑 Админ {user_id} — токены не списаны")
    
    loading = await message.answer(
        f"🎬 Генерирую видео ({duration} сек) на {model.get('name', '...')}...\n"
        f"⏳ Это может занять 1-5 минут."
    )
    
    try:
        # TODO: Интеграция с GenAPI
        await asyncio.sleep(3)
        
        # Для админа показываем что токены не тратились
        if is_admin(user_id):
            caption = (
                f"🎬 **Видео готово!**\n\n"
                f"🎯 Модель: {model.get('name', '...')}\n"
                f"⏱️ Длительность: {duration} сек\n"
                f"👑 **Админ — токены не списаны**"
            )
        else:
            caption = (
                f"🎬 **Видео готово!**\n\n"
                f"🎯 Модель: {model.get('name', '...')}\n"
                f"⏱️ Длительность: {duration} сек\n"
                f"📊 Потрачено: **{required_tokens}** токенов\n"
                f"💳 Осталось: **{tokens - required_tokens}** токенов"
            )
        
        await message.answer_video(
            video="https://example.com/video.mp4",
            caption=caption,
            parse_mode="HTML"
        )
        
    except Exception as e:
        # Возвращаем токены только если НЕ админ
        if not is_admin(user_id):
            await token_repository.refund_tokens(user_id, required_tokens, f"Возврат за ошибку видео")
        logger.error(f"Ошибка генерации видео: {e}")
        await message.answer(
            "❌ Ошибка при генерации видео." + 
            ("" if is_admin(user_id) else " Токены возвращены."),
            parse_mode="HTML"
        )
    
    finally:
        await loading.delete()


async def cancel_video_creation(message: types.Message, state: FSMContext):
    """Отмена создания видео."""
    await state.clear()
    await state.set_state(VideoStates.menu)
    await message.answer(
        "❌ Отменено.",
        reply_markup=get_video_menu_keyboard()
    )


# ==================== AI АССИСТЕНТ ====================

@router.message(F.text == "🤖 AI Ассистент")
async def enter_assistant(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(AssistantStates.menu)
    await message.answer(
        "🤖 AI Ассистент\n\n"
        "Напишите ваш вопрос или задачу.\n"
        "Я помогу с любым вопросом!",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(AssistantStates.waiting_question))
async def assistant_question(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_assistant(message, state)
        return

    if len(message.text) < 3:
        await message.answer("❌ Вопрос слишком короткий. Напишите подробнее.")
        return

    await state.update_data(question=message.text)
    await generate_assistant(message, state)


async def generate_assistant(message: types.Message, state: FSMContext):
    data = await state.get_data()
    question = data.get("question", "")

    loading = await message.answer("🤔 Думаю...")

    try:
        result = await execute_tool(
            tool_id=ToolIds.ASSISTANT,
            user_id=message.from_user.id,
            input_data={
                "message": question,
                "context": "",
                "history": []
            },
            session=None,
            mode="initial"
        )

        try:
            await loading.delete()
        except Exception:
            pass

        await send_pipeline_result(
            message,
            state,
            result,
            "🤖 AI Ассистент",
            None
        )

    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        logger.error(f"Ошибка AI Assistant: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


async def cancel_assistant(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(AssistantStates.menu)
    await message.answer("❌ Отменено.", reply_markup=get_main_menu())


# ==================== МАРКЕТПЛЕЙС ====================

@router.message(F.text == "🛒 Маркетплейсы")
async def enter_marketplace(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(MarketplaceStates.platform)
    await message.answer(
        "🛒 Маркетплейсы\n\n"
        "Шаг 1 из 4\nВыберите площадку:",
        reply_markup=get_marketplace_platform_keyboard()
    )


@router.message(StateFilter(MarketplaceStates.platform))
async def marketplace_platform(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await cancel_marketplace(message, state)
        return
    
    valid_platforms = ["🛍️ Wildberries", "🛒 Ozon", "📦 Яндекс.Маркет", "🛍️ AliExpress", "🌐 Другое"]
    if message.text not in valid_platforms:
        await message.answer("❌ Выберите площадку из кнопок.", reply_markup=get_marketplace_platform_keyboard())
        return
    
    await state.update_data(platform=message.text)
    await state.set_state(MarketplaceStates.task)
    await message.answer(
        "Шаг 2 из 4\nЧто нужно сделать?\n\n"
        "Примеры:\n"
        "• создать карточку товара\n"
        "• написать описание\n"
        "• улучшить название\n"
        "• сделать SEO-текст\n"
        "• ответить клиенту",
        reply_markup=get_marketplace_task_keyboard()
    )


@router.message(StateFilter(MarketplaceStates.task))
async def marketplace_task(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.set_state(MarketplaceStates.platform)
        await message.answer(
            "Шаг 1 из 4\nВыберите площадку:",
            reply_markup=get_marketplace_platform_keyboard()
        )
        return
    
    await state.update_data(task=message.text)
    await state.set_state(MarketplaceStates.category)
    await message.answer(
        "Шаг 3 из 4\nКатегория товара?",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(MarketplaceStates.category))
async def marketplace_category(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.set_state(MarketplaceStates.task)
        await message.answer(
            "Шаг 2 из 4\nЧто нужно сделать?",
            reply_markup=get_marketplace_task_keyboard()
        )
        return
    await state.update_data(category=message.text)
    await state.set_state(MarketplaceStates.product_info)
    await message.answer(
        "Шаг 4 из 4\nИнформация о товаре:",
        reply_markup=get_back_to_menu_keyboard()
    )


@router.message(StateFilter(MarketplaceStates.product_info))
async def marketplace_product_info(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.set_state(MarketplaceStates.category)
        await message.answer(
            "Шаг 3 из 4\nКатегория товара?",
            reply_markup=get_back_to_menu_keyboard()
        )
        return
    await state.update_data(product_info=message.text)
    await generate_marketplace(message, state)


async def generate_marketplace(message: types.Message, state: FSMContext):
    data = await state.get_data()
    required = ["platform", "task", "category", "product_info"]
    if any(f not in data for f in required):
        await message.answer("⚠️ Заполните все шаги.")
        return

    loading = await message.answer("⏳ Генерирую...")

    try:
        result = await execute_tool(
            tool_id=ToolIds.MARKETPLACE,
            user_id=message.from_user.id,
            input_data=data,
            session=None,
            mode="initial"
        )

        try:
            await loading.delete()
        except Exception:
            pass

        await send_pipeline_result(
            message,
            state,
            result,
            "🛒 Результат",
            None
        )

    except Exception as e:
        try:
            await loading.delete()
        except Exception:
            pass
        logger.error(f"Ошибка Marketplace: {e}")
        await message.answer("❌ Ошибка. Попробуйте позже.")


async def cancel_marketplace(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(MarketplaceStates.menu)
    await message.answer("❌ Отменено.", reply_markup=get_main_menu())


# ==================== КАБИНЕТ / МОЙ БАЛАНС ====================

@router.message(F.text == "💰 Мой баланс")
async def user_cabinet(message: types.Message, state: FSMContext):
    await state.clear()

    tariff_id = await get_user_tariff(message.from_user.id)
    tariff = get_tariff(tariff_id.value)

    text_used = await get_user_usage_today(message.from_user.id, ResponseType.TEXT)
    image_used = await get_user_usage_today(message.from_user.id, ResponseType.IMAGE)
    video_used = await get_user_usage_today(message.from_user.id, ResponseType.VIDEO)
    
    tokens = await get_user_tokens_balance(message.from_user.id)

    text_limit = tariff.get("text_limit", 0)
    image_limit = tariff.get("image_limit", 0)
    video_limit = tariff.get("video_limit", 0)

    text_remaining = max(0, text_limit - text_used)
    image_remaining = max(0, image_limit - image_used)
    video_remaining = max(0, video_limit - video_used)

    end_date = await get_subscription_end_date(message.from_user.id)

    text = f"💰 **Мой баланс**\n\n"
    text += f"🪙 Кредиты: **{tokens}**\n"
    text += f"📋 Тариф: **{tariff.get('name', 'FREE')}**\n"
    text += f"💳 Стоимость: {tariff.get('price', 0)} ₽ / {tariff.get('period', 'месяц')}\n"

    if end_date:
        text += f"📅 Активен до: {end_date.strftime('%d.%m.%Y')}\n"
    else:
        text += f"📅 Бессрочный (FREE)\n"

    text += f"\n📊 **Использование сегодня:**\n"
    text += f"• Тексты: {text_used} / {text_limit} (осталось {text_remaining})\n"
    text += f"• Картинки: {image_used} / {image_limit} (осталось {image_remaining})\n"
    text += f"• Видео: {video_used} / {video_limit} (осталось {video_remaining})\n\n"

    text += f"💡 Пополнить баланс: «💳 Купить кредиты»"

    await message.answer(text, parse_mode="HTML")


# ==================== ТАРИФЫ ====================

@router.message(F.text == "💎 Тарифы")
async def show_tariffs(message: types.Message, state: FSMContext):
    """Показать тарифы и пакеты токенов."""
    await state.clear()

    text = "🚀 ШТАБ AI — Тарифы и токены\n\n"
    text += "Выберите, что вам нужно:\n\n"
    text += "📋 **Подписки** — для регулярного использования\n"
    text += "🪙 **Пакеты токенов** — для разовых задач"

    await message.answer(
        text,
        reply_markup=get_tariff_and_tokens_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "show_subscriptions")
async def show_subscriptions(callback: types.CallbackQuery):
    """Показать список тарифов (подписок)."""
    text = "📋 **Подписки ШТАБ AI**\n\n"
    text += "Ежемесячная подписка для регулярного использования:\n\n"

    for tariff_id, tariff in get_all_tariffs().items():
        text += f"{tariff['color']} **{tariff['name']}**\n"
        text += f"   💰 {tariff['price']} ₽ / {tariff['period']}\n"
        text += f"   📝 {tariff['text_limit']} текстов / день\n"
        text += f"   🖼 {tariff['image_limit']} изображений / день\n"
        text += f"   🎬 {tariff['video_limit']} видео / день\n"
        text += f"   {tariff['description']}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_to_tariffs_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "show_tokens")
async def show_tokens_packages(callback: types.CallbackQuery):
    """Показать пакеты токенов."""
    user_id = callback.from_user.id
    tokens = await get_user_tokens_balance(user_id)
    
    text = f"🪙 **Пакеты токенов**\n\n"
    text += f"💰 Ваш баланс: **{tokens}** кредитов\n\n"
    text += "Разовое пополнение для любых задач:\n"
    text += "✅ Токены не сгорают\n"
    text += "✅ Подходят для всего: текст, изображения, видео\n"
    text += "✅ Можно использовать в любое время\n\n"
    text += "Выберите пакет:"

    await callback.message.edit_text(
        text,
        reply_markup=get_tokens_packages_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(F.text == "💳 Купить кредиты")
async def show_tokens_packages_message(message: types.Message, state: FSMContext):
    """Показать пакеты токенов (из меню)."""
    user_id = message.from_user.id
    tokens = await get_user_tokens_balance(user_id)
    
    text = f"🪙 **Пакеты токенов**\n\n"
    text += f"💰 Ваш баланс: **{tokens}** кредитов\n\n"
    text += "Разовое пополнение для любых задач:\n"
    text += "✅ Токены не сгорают\n"
    text += "✅ Подходят для всего: текст, изображения, видео\n"
    text += "✅ Можно использовать в любое время\n\n"
    text += "Выберите пакет:"

    await message.answer(
        text,
        reply_markup=get_tokens_packages_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(callback: types.CallbackQuery):
    """Вернуться к выбору тарифов/токенов."""
    text = "🚀 ШТАБ AI — Тарифы и токены\n\n"
    text += "Выберите, что вам нужно:\n\n"
    text += "📋 **Подписки** — для регулярного использования\n"
    text += "🪙 **Пакеты токенов** — для разовых задач"

    await callback.message.edit_text(
        text,
        reply_markup=get_tariff_and_tokens_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tariff_"))
async def tariff_selected(callback: types.CallbackQuery, state: FSMContext):
    """Выбор тарифа (подписки)."""
    tariff_id = callback.data.split("_")[1]
    tariff = get_tariff(tariff_id)

    if tariff["price"] == 0:
        current_tariff = await get_user_tariff(callback.from_user.id)
        if current_tariff.value == "free":
            await callback.message.edit_text(
                "⚪ **FREE**\n\n"
                "Бесплатный тариф уже активен!\n\n"
                "📝 5 текстов / день\n"
                "🖼 2 изображения / день\n"
                "🎬 0 видео / день",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "⚪ **FREE**\n\n"
                "Бесплатный тариф доступен всем новым пользователям.\n"
                "Вы можете перейти на FREE в любой момент.\n\n"
                "📝 5 текстов / день\n"
                "🖼 2 изображения / день\n"
                "🎬 0 видео / день",
                parse_mode="HTML"
            )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"💎 **{tariff['name']}** — {tariff['price']} ₽ / {tariff['period']}\n\n"
        f"📝 {tariff['text_limit']} текстов / день\n"
        f"🖼 {tariff['image_limit']} изображений / день\n"
        f"🎬 {tariff['video_limit']} видео / день\n\n"
        f"🚧 Оплата будет доступна в ближайшее время.\n"
        f"Способы оплаты: Telegram Stars, ЮKassa",
        reply_markup=get_back_to_subscriptions_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy_tokens_"))
async def buy_tokens_package(callback: types.CallbackQuery):
    """Покупка пакета токенов."""
    amount = int(callback.data.replace("buy_tokens_", ""))
    
    prices = {
        50: 69,
        150: 179,
        500: 499,
        1500: 1299,
        5000: 3999
    }
    
    price = prices.get(amount, 0)
    user_id = callback.from_user.id
    current_tokens = await get_user_tokens_balance(user_id)
    
    text = f"🪙 **Пакет {amount} токенов**\n\n"
    text += f"💰 Стоимость: **{price} ₽**\n"
    text += f"📊 Цена за токен: **{price/amount:.2f} ₽**\n"
    text += f"💳 Ваш баланс: **{current_tokens}** токенов\n\n"
    text += "📌 **Как оплатить:**\n"
    text += "1️⃣ Переведите сумму по реквизитам\n"
    text += "2️⃣ Отправьте скриншот чека\n"
    text += "3️⃣ Токены зачислятся автоматически\n\n"
    text += "💳 **Реквизиты для оплаты:**\n"
    text += "<code>+7 999 123-45-67</code> (СБП)\n\n"
    text += "После оплаты нажмите «✅ Я оплатил»"

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"confirm_tokens_{amount}")],
            [InlineKeyboardButton(text="🔙 Назад к пакетам", callback_data="show_tokens")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_tokens_"))
async def confirm_tokens_payment(callback: types.CallbackQuery):
    """Подтверждение оплаты токенов (отправка админу)."""
    amount = int(callback.data.replace("confirm_tokens_", ""))
    user_id = callback.from_user.id
    user = await user_repository.get_user(user_id)
    
    username = callback.from_user.username or "нет"
    first_name = callback.from_user.first_name or ""

    admin_id = settings.ADMIN_TELEGRAM_ID
    
    admin_text = (
        f"💰 **Заявка на пополнение токенов**\n\n"
        f"👤 Пользователь: {first_name} (@{username})\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📊 Пакет: **{amount}** токенов\n"
        f"💳 Текущий баланс: **{user.tokens if user else 0}** токенов\n\n"
        f"⏳ Ожидает подтверждения"
    )
    
    await callback.bot.send_message(
        admin_id,
        admin_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_approve_tokens_{user_id}_{amount}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_tokens_{user_id}_{amount}")
            ]
        ])
    )
    
    await callback.message.edit_text(
        f"✅ Заявка на **{amount}** токенов отправлена!\n\n"
        f"Ожидайте подтверждения администратора.\n"
        f"Обычно это занимает до 5 минут.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К пакетам", callback_data="show_tokens")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer("📨 Заявка отправлена администратору")


@router.callback_query(F.data.startswith("admin_approve_tokens_"))
async def admin_approve_tokens(callback: types.CallbackQuery):
    """Админ подтверждает оплату токенов."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только для администратора")
        return
    
    parts = callback.data.split("_")
    user_id = int(parts[3])
    amount = int(parts[4])
    
    success = await token_repository.add_tokens(
        user_id, 
        amount, 
        f"Пополнение на {amount} токенов (админ)"
    )
    
    if success:
        try:
            await callback.bot.send_message(
                user_id,
                f"✅ **Пополнение подтверждено!**\n\n"
                f"💰 На ваш баланс зачислено **{amount}** токенов.\n\n"
                f"Продолжайте пользоваться сервисом! 🚀",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя: {e}")
        
        await callback.message.edit_text(
            f"✅ Подтверждено! Пользователю {user_id} зачислено {amount} токенов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
            ])
        )
        await callback.answer("✅ Токены зачислены")
    else:
        await callback.answer("❌ Ошибка зачисления токенов")


@router.callback_query(F.data.startswith("admin_reject_tokens_"))
async def admin_reject_tokens(callback: types.CallbackQuery):
    """Админ отклоняет оплату токенов."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Только для администратора")
        return
    
    parts = callback.data.split("_")
    user_id = int(parts[3])
    amount = int(parts[4])
    
    try:
        await callback.bot.send_message(
            user_id,
            f"❌ **Пополнение отклонено**\n\n"
            f"К сожалению, ваша заявка на пополнение была отклонена.\n"
            f"Пожалуйста, проверьте правильность оплаты и попробуйте снова.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя: {e}")
    
    await callback.message.edit_text(
        f"❌ Отклонено! Пользователю {user_id} отказано в пополнении.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
        ])
    )
    await callback.answer("❌ Отклонено")


# ==================== АДМИН ====================

@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён")
        return

    from admin import get_admin_stats
    stats = await get_admin_stats()

    text = "📊 ШТАБ AI — Админ панель\n\n"
    text += f"👥 Пользователей: {stats['total']}\n"
    text += f"  ⚪ FREE: {stats.get('free', 0)}\n"
    text += f"  🟢 LITE: {stats.get('lite', 0)}\n"
    text += f"  🔵 PRO: {stats.get('pro', 0)}\n"
    text += f"  🟣 BUSINESS: {stats.get('business', 0)}\n\n"
    text += f"💰 Расход AI: {stats['ai_cost']:.2f} ₽\n"
    text += f"💳 Доход: {stats['revenue']:.2f} ₽\n"
    text += f"🪙 Всего токенов: {stats.get('total_tokens', 0)}"

    await message.answer(text)


# ==================== ОБЩИЙ НАЗАД ====================

@router.message(F.text == "⬅️ Назад")
async def back_to_main(message: types.Message, state: FSMContext):
    current = await state.get_state()

    sales_states = [
        SalesStates.script_product,
        SalesStates.script_client,
        SalesStates.script_average_check,
        SalesStates.script_format,
        SalesStates.script_objections,
        SalesStates.script_result,
        SalesStates.cp_company,
        SalesStates.cp_client,
        SalesStates.cp_product,
        SalesStates.cp_problem,
        SalesStates.cp_price,
        SalesStates.cp_result,
        SalesStates.reply_question,
        SalesStates.reply_context,
        SalesStates.reply_result,
        SalesStates.analysis_text,
        SalesStates.analysis_result,
        SalesStates.objection_product,
        SalesStates.objection_list,
        SalesStates.objection_result,
    ]
    marketing_states = [
        MarketingStates.post_product,
        MarketingStates.post_audience,
        MarketingStates.post_platform,
        MarketingStates.post_style,
        MarketingStates.post_result,
        MarketingStates.content_plan_niche,
        MarketingStates.content_plan_audience,
        MarketingStates.content_plan_platform,
        MarketingStates.content_plan_result,
        MarketingStates.offer_product,
        MarketingStates.offer_benefit,
        MarketingStates.offer_audience,
        MarketingStates.offer_result,
        MarketingStates.email_topic,
        MarketingStates.email_audience,
        MarketingStates.email_goal,
        MarketingStates.email_result,
        MarketingStates.utp_product,
        MarketingStates.utp_competitors,
        MarketingStates.utp_benefit,
        MarketingStates.utp_result,
        MarketingStates.audience_product,
        MarketingStates.audience_details,
        MarketingStates.audience_result,
    ]
    image_states = [
        ImageStates.description,
        ImageStates.purpose,
        ImageStates.style,
        ImageStates.size,
        ImageStates.result
    ]
    video_states = [
        VideoStates.model_choice,
        VideoStates.waiting_prompt,
        VideoStates.waiting_photo,
        VideoStates.waiting_duration,
        VideoStates.processing,
        VideoStates.result,
    ]
    marketplace_states = [
        MarketplaceStates.platform,
        MarketplaceStates.task,
        MarketplaceStates.category,
        MarketplaceStates.product_info,
        MarketplaceStates.result
    ]
    assistant_states = [
        AssistantStates.waiting_question,
        AssistantStates.result
    ]

    if current in sales_states:
        await state.clear()
        await state.set_state(SalesStates.menu)
        await message.answer("📊 Продажи", reply_markup=get_sales_menu_keyboard())
    elif current in marketing_states:
        await state.clear()
        await state.set_state(MarketingStates.menu)
        await message.answer("📊 Маркетинг", reply_markup=get_marketing_menu_keyboard())
    elif current in image_states:
        await state.clear()
        await state.set_state(ImageStates.menu)
        await message.answer("🖼 Изображения", reply_markup=get_images_menu_keyboard())
    elif current in video_states:
        await state.clear()
        await state.set_state(VideoStates.menu)
        await message.answer("🎬 Видео", reply_markup=get_video_menu_keyboard())
    elif current in marketplace_states:
        await state.clear()
        await state.set_state(MarketplaceStates.menu)
        await message.answer("🛒 Маркетплейсы", reply_markup=get_back_to_menu_keyboard())
    elif current in assistant_states:
        await state.clear()
        await state.set_state(AssistantStates.menu)
        await message.answer("🤖 AI Ассистент", reply_markup=get_back_to_menu_keyboard())
    else:
        await state.clear()
        await message.answer("👋 Главное меню", reply_markup=get_main_menu())
