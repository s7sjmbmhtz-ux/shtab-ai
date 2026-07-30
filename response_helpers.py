from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardMarkup

from models import PipelineResult
from response_adapter import TelegramResponseAdapter


# Создаём один экземпляр адаптера
telegram_response_adapter = TelegramResponseAdapter()


async def send_pipeline_result(
    message: Message,
    state: FSMContext,
    result: PipelineResult,
    success_text: str,
    keyboard: InlineKeyboardMarkup = None,
    parse_mode: str = "HTML"
) -> bool:
    if not result.success:
        await message.answer(f"❌ {result.error or 'Произошла ошибка'}", parse_mode=parse_mode)
        return False

    await state.update_data(
        last_prompt=result.prompt or "",
        last_response=result.content or ""
    )

    return await telegram_response_adapter.send(
        message,
        result,
        success_text,
        keyboard,
        parse_mode
    )