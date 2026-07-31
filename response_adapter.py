import json
import logging
import base64
import tempfile
import os
from aiogram.types import Message, FSInputFile
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
        elif result.response_type == ResponseType.VIDEO:
            return await self._send_video(message, result, success_text, keyboard, parse_mode)
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

            if image_url.startswith("data:image"):
                try:
                    if "," in image_url:
                        _, encoded = image_url.split(",", 1)
                    else:
                        encoded = image_url
                    
                    missing_padding = len(encoded) % 4
                    if missing_padding:
                        encoded += "=" * (4 - missing_padding)
                    
                    image_data = base64.b64decode(encoded)
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        tmp.write(image_data)
                        tmp_path = tmp.name
                    
                    photo = FSInputFile(tmp_path)
                    await message.answer_photo(
                        photo=photo,
                        caption=f"{success_text}\n\n<i>⏱ {result.elapsed:.2f} сек</i>",
                        reply_markup=keyboard,
                        parse_mode=parse_mode
                    )
                    
                    os.unlink(tmp_path)
                    return True
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки base64: {e}")
                    await message.answer("❌ Ошибка обработки изображения", parse_mode=parse_mode)
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

    async def _send_video(
        self,
        message: Message,
        result: PipelineResult,
        success_text: str,
        keyboard: InlineKeyboardMarkup = None,
        parse_mode: str = "HTML"
    ) -> bool:
        try:
            data = json.loads(result.content)
            video_url = data.get("url")
            
            if not video_url:
                await message.answer("❌ URL видео не получен", parse_mode=parse_mode)
                return False

            if video_url.startswith("data:video"):
                try:
                    if "," in video_url:
                        _, encoded = video_url.split(",", 1)
                    else:
                        encoded = video_url
                    
                    missing_padding = len(encoded) % 4
                    if missing_padding:
                        encoded += "=" * (4 - missing_padding)
                    
                    video_data = base64.b64decode(encoded)
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                        tmp.write(video_data)
                        tmp_path = tmp.name
                    
                    video = FSInputFile(tmp_path)
                    await message.answer_video(
                        video=video,
                        caption=f"{success_text}\n\n<i>⏱ {result.elapsed:.2f} сек</i>",
                        reply_markup=keyboard,
                        parse_mode=parse_mode
                    )
                    
                    os.unlink(tmp_path)
                    return True
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки base64 видео: {e}")
                    await message.answer("❌ Ошибка обработки видео", parse_mode=parse_mode)
                    return False
            
            await message.answer_video(
                video=video_url,
                caption=f"{success_text}\n\n<i>⏱ {result.elapsed:.2f} сек</i>",
                reply_markup=keyboard,
                parse_mode=parse_mode
            )
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON для Video: {e}")
            await message.answer("❌ Ошибка формата ответа", parse_mode=parse_mode)
            return False
        except Exception as e:
            logger.error(f"Ошибка отправки видео: {e}")
            await message.answer("❌ Ошибка отправки видео", parse_mode=parse_mode)
            return False
