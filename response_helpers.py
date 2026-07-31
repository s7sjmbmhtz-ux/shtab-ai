from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardMarkup
import re

from models import PipelineResult
from response_adapter import TelegramResponseAdapter


# Создаём один экземпляр адаптера
telegram_response_adapter = TelegramResponseAdapter()


def clean_text(text: str) -> str:
    """Полностью очищает текст от Markdown и HTML."""
    if not text:
        return text
    
    # Убираем **жирный текст**
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    
    # Убираем *курсив*
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    
    # Убираем ## заголовки
    text = re.sub(r'^#+\s*(.+?)$', r'\1', text, flags=re.MULTILINE)
    
    # Убираем ссылки [текст](url)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    
    # Убираем ```код```
    text = re.sub(r'```.+?```', '', text, flags=re.DOTALL)
    text = re.sub(r'`(.+?)`', r'\1', text)
    
    # Убираем разделители --- и ___
    text = re.sub(r'_{3,}', '', text)
    text = re.sub(r'-{3,}', '', text)
    
    # Убираем лишние пустые строки
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = line.strip()
        if line:
            cleaned.append(line)
    
    return '\n\n'.join(cleaned)


async def send_pipeline_result(
    message: Message,
    state: FSMContext,
    result: PipelineResult,
    success_text: str,
    keyboard: InlineKeyboardMarkup = None,
    parse_mode: str = None  # ← УБИРАЕМ HTML
) -> bool:
    if not result.success:
        await message.answer(f"❌ {result.error or 'Произошла ошибка'}")
        return False

    # Очищаем текст от Markdown
    cleaned_content = clean_text(result.content)
    
    # Сохраняем ОРИГИНАЛ в состояние (для истории)
    await state.update_data(
        last_prompt=result.prompt or "",
        last_response=result.content or ""  # ← оригинал сохраняем
    )

    # Создаём новый результат с очищенным текстом
    from models import PipelineResult, GenerationStatus
    
    cleaned_result = PipelineResult(
        success=result.success,
        content=cleaned_content,
        raw=result.raw,
        prompt=result.prompt,
        status=result.status,
        elapsed=result.elapsed,
        provider=result.provider,
        model=result.model,
        history_id=result.history_id,
        response_type=result.response_type
    )

    # Отправляем через адаптер (parse_mode=None)
    return await telegram_response_adapter.send(
        message,
        cleaned_result,
        success_text,
        keyboard
    )
