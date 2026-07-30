import json
import logging
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardMarkup

from models import PipelineResult, ResponseType

logger = logging.getLogger(__name__)


class TelegramResponseAdapter:
    """Адаптер для отправки разных типов ответов в Telegram."""

    async def send(
        self,
        message: Message,
        result: PipelineResult,
        success_text: str,
        keyboard: InlineKeyboardMarkup = None,
        parse_mode: str = "HTML"
    ) -> bool:
        if result.response_type == ResponseType.IMAGE:
            return await self._send_image(message, result, success_text, keyboard, parse_mode)
        else:
            return await self._send_text(message, result, success_text, keyboard, parse_mode)

    async def _send_text(
        self,
        message: Message,
        result: PipelineResult,
        success_text: str,
        keyboard: InlineKeyboardMarkup = None,
        parse_mode: str = "HTML"
    ) -> bool:
        await message.answer(
            f"{success_text}\n\n{result.content}\n\n<i>⏱ {result.elapsed:.2f} сек</i>",
            reply_markup=keyboard,
            parse_mode=parse_mode
        )
        return True

    async def _send_image(
        self,
        message: Message,
        result: PipelineResult,
        success_text: str,
        keyboard: InlineKeyboardMarkup = None,
        parse_mode: str = "HTML"
    ) -> bool:
        try:
            data = json.loads(result.content)
            image_url = data.get("url")
            if not image_url:
                await message.answer("❌ URL изображения не получен", parse_mode=parse_mode)
                return False

            await message.answer_photo(
                photo=image_url,
                caption=f"{success_text}\n\n<i>⏱ {result.elapsed:.2f} сек</i>",
                reply_markup=keyboard,
                parse_mode=parse_mode
            )
            return True
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON для Image: {e}")
            await message.answer("❌ Ошибка формата ответа", parse_mode=parse_mode)
            return False
        except Exception as e:
            logger.error(f"Ошибка отправки изображения: {e}")
            await message.answer("❌ Ошибка отправки изображения", parse_mode=parse_mode)
            return False