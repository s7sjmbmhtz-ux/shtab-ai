import json
import logging
import base64
import re
from aiogram.types import Message, BufferedInputFile
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

    def _clean_text(self, text: str) -> str:
        """Очищает текст от Markdown и HTML, оставляя красивый читаемый текст."""
        if not text:
            return text
        
        # Убираем **жирный текст** → просто текст
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        
        # Убираем *курсив* → просто текст
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        
        # Убираем ## заголовки → просто текст
        text = re.sub(r'^#+\s*(.+?)$', r'\1', text, flags=re.MULTILINE)
        
        # Убираем ссылки [текст](url) → просто текст
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
        
        # Убираем ```код``` → просто текст
        text = re.sub(r'```.+?```', '', text, flags=re.DOTALL)
        text = re.sub(r'`(.+?)`', r'\1', text)
        
        # Убираем ___ и --- (разделители)
        text = re.sub(r'_{3,}', '', text)
        text = re.sub(r'-{3,}', '', text)
        
        # Убираем лишние пробелы и пустые строки
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:  # не пустая строка
                cleaned_lines.append(line)
        
        return '\n\n'.join(cleaned_lines)

    async def _send_text(
        self,
        message: Message,
        result: PipelineResult,
        success_text: str,
        keyboard: InlineKeyboardMarkup = None,
        parse_mode: str = "HTML"
    ) -> bool:
        # Очищаем текст от Markdown и HTML
        content = self._clean_text(result.content)
        
        # Формируем красивый ответ
        response_text = f"{success_text}\n\n{content}\n\n⏱ {result.elapsed:.2f} сек"
        
        await message.answer(
            response_text,
            reply_markup=keyboard,
            parse_mode=None  # ← Отключаем HTML, чтобы не было тегов
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

            # Если это data URL с base64
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
                    
                    photo = BufferedInputFile(
                        file=image_data,
                        filename="image.png"
                    )
                    
                    await message.answer_photo(
                        photo=photo,
                        caption=f"{success_text}\n\n⏱ {result.elapsed:.2f} сек",
                        reply_markup=keyboard
                    )
                    return True
                    
                except Exception as e:
                    logger.error(f"Ошибка обработки base64: {e}")
                    await message.answer("❌ Ошибка обработки изображения")
                    return False
            
            # Обычный URL
            await message.answer_photo(
                photo=image_url,
                caption=f"{success_text}\n\n⏱ {result.elapsed:.2f} сек",
                reply_markup=keyboard
            )
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON для Image: {e}")
            await message.answer("❌ Ошибка формата ответа")
            return False
        except Exception as e:
            logger.error(f"Ошибка отправки изображения: {e}")
            await message.answer("❌ Ошибка отправки изображения")
            return False
