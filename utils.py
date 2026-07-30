import io
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Optional, List

from aiogram.types import Message

from settings import settings
from models import AudioFile, AIResponse


# ==================== ЛОГГЕР ====================

logger = logging.getLogger(__name__)


# ==================== SUPPORTED FORMATS ====================

SUPPORTED_AUDIO_EXTENSIONS = {".ogg", ".mp3", ".m4a", ".wav", ".flac", ".aac", ".opus", ".webm"}


# ==================== EXTRACT AUDIO ====================

async def extract_audio_from_message(message: Message) -> Optional[AudioFile]:
    """Извлекает аудио из сообщения Telegram"""
    try:
        file = None
        duration = 0
        filename = None
        file_size = 0

        if message.voice:
            file = message.voice
            duration = file.duration or 0
            file_size = file.file_size or 0
            filename = f"voice_{file.file_id}.ogg"
        elif message.audio:
            file = message.audio
            duration = file.duration or 0
            file_size = file.file_size or 0
            filename = file.file_name or f"audio_{file.file_id}.mp3"
        elif message.document:
            if not message.document.file_name:
                return None
            ext = Path(message.document.file_name).suffix.lower()
            if ext not in SUPPORTED_AUDIO_EXTENSIONS:
                return None
            file = message.document
            duration = 0
            file_size = file.file_size or 0
            filename = file.file_name
        else:
            return None

        if not file:
            return None

        if duration > settings.max_audio_duration_sec:
            logger.warning(f"Слишком длинное аудио: {duration} сек")
            return None

        size_mb = file_size / (1024 * 1024)
        if size_mb > settings.max_audio_size_mb:
            logger.warning(f"Слишком большой файл: {size_mb:.1f} МБ")
            return None

        file_info = await message.bot.get_file(file.file_id)
        buf = io.BytesIO()
        await message.bot.download_file(file_info.file_path, destination=buf)
        content = buf.getvalue()

        return AudioFile(
            filename=filename,
            extension=Path(filename).suffix.lower(),
            duration=duration,
            size=file_size,
            content=content
        )

    except Exception as e:
        logger.error(f"Ошибка извлечения аудио: {e}")
        return None


# ==================== EXTRACT TEXT FROM DOCUMENTS ====================

def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """
    Извлекает текст из документа.

    Поддерживает: TXT, MD, PDF, DOCX, DOC
    """
    ext = Path(filename).suffix.lower()

    # TXT и MD
    if ext in [".txt", ".md"]:
        try:
            return file_content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return file_content.decode("cp1251")
            except UnicodeDecodeError:
                return file_content.decode("latin-1")

    # PDF
    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except ImportError:
            raise NotImplementedError("Для работы с PDF установите библиотеку pypdf")
        except Exception as e:
            raise ValueError(f"Ошибка извлечения текста из PDF: {e}")

    # DOCX
    if ext == ".docx":
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_content))
            return "\n".join([p.text for p in doc.paragraphs])
        except ImportError:
            raise NotImplementedError("Для работы с DOCX установите библиотеку python-docx")
        except Exception as e:
            raise ValueError(f"Ошибка извлечения текста из DOCX: {e}")

    # DOC
    if ext == ".doc":
        raise NotImplementedError("Извлечение текста из DOC пока не реализовано")

    raise ValueError(f"Неподдерживаемый формат: {ext}")


# ==================== RESPONSE PARSER ====================

class ParseState(Enum):
    TITLE = "title"
    CONTENT = "content"
    TIPS = "tips"
    FOLLOW_UP = "follow_up"
    UNKNOWN = "unknown"


class AIResponseParser:
    @classmethod
    def _clean_header(cls, line: str) -> str:
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"
            u"\U0001F300-\U0001F5FF"
            u"\U0001F680-\U0001F6FF"
            u"\U0001F700-\U0001F77F"
            u"\U0001F780-\U0001F7FF"
            u"\U0001F800-\U0001F8FF"
            u"\U0001F900-\U0001F9FF"
            u"\U0001FA00-\U0001FA6F"
            u"\U0001FA70-\U0001FAFF"
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        cleaned = emoji_pattern.sub(r'', line)
        cleaned = re.sub(r'^#{1,6}\s*', '', cleaned)
        cleaned = re.sub(r'\*\*|__', '', cleaned)
        cleaned = re.sub(r'\*|_', '', cleaned)
        cleaned = re.sub(r'^[-•*]\s*', '', cleaned)
        cleaned = re.sub(r':\s*$', '', cleaned)
        return cleaned.strip().lower()

    @classmethod
    def _detect_section(cls, line: str):
        cleaned = cls._clean_header(line)
        title_keywords = ["title", "заголовок", "название"]
        content_keywords = ["content", "текст", "содержание", "скрипт", "результат"]
        tips_keywords = ["tips", "советы", "рекомендации", "подсказки"]
        follow_keywords = ["follow_up", "follow up", "продолжить", "варианты", "дальше"]

        for kw in title_keywords:
            if cleaned == kw or cleaned.startswith(kw):
                return ParseState.TITLE
        for kw in content_keywords:
            if cleaned == kw or cleaned.startswith(kw):
                return ParseState.CONTENT
        for kw in tips_keywords:
            if cleaned == kw or cleaned.startswith(kw):
                return ParseState.TIPS
        for kw in follow_keywords:
            if cleaned == kw or cleaned.startswith(kw):
                return ParseState.FOLLOW_UP
        return ParseState.UNKNOWN

    @classmethod
    def _clean_list_item(cls, line: str) -> str:
        cleaned = line.strip()
        for marker in ["- ", "• ", "* ", "  - ", "  • ", "  * "]:
            if cleaned.startswith(marker):
                cleaned = cleaned[len(marker):]
                break
        match = re.match(r"^\d+\.?\s+", cleaned)
        if match:
            cleaned = cleaned[len(match.group()):]
        return cleaned.strip()

    @classmethod
    def _looks_like_title(cls, line: str) -> bool:
        if len(line) < 60 and not line.endswith((".", "?", "!")):
            return True
        title_keywords = ["скрипт", "продажи", "стратегия", "план", "метод"]
        return any(kw in line.lower() for kw in title_keywords)

    @classmethod
    def _looks_like_list_item(cls, line: str) -> bool:
        markers = ["-", "•", "*", "1.", "2.", "3.", "—"]
        return any(line.strip().startswith(m) for m in markers)

    @classmethod
    def parse(cls, text: str) -> AIResponse:
        lines = text.strip().split("\n")
        title = None
        content_lines = []
        tips_lines = []
        follow_up_lines = []
        current_state = ParseState.UNKNOWN

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            new_state = cls._detect_section(stripped)
            if new_state != ParseState.UNKNOWN:
                current_state = new_state
                continue
            if current_state == ParseState.TITLE:
                title = stripped if title is None else title + " " + stripped
            elif current_state == ParseState.CONTENT:
                content_lines.append(stripped)
            elif current_state == ParseState.TIPS:
                clean = cls._clean_list_item(stripped)
                if clean:
                    tips_lines.append(clean)
            elif current_state == ParseState.FOLLOW_UP:
                clean = cls._clean_list_item(stripped)
                if clean:
                    follow_up_lines.append(clean)
            elif current_state == ParseState.UNKNOWN:
                if cls._looks_like_title(stripped):
                    title = stripped
                elif cls._looks_like_list_item(stripped):
                    clean = cls._clean_list_item(stripped)
                    if tips_lines and not follow_up_lines:
                        tips_lines.append(clean)
                    elif follow_up_lines:
                        follow_up_lines.append(clean)
                elif not content_lines and not tips_lines and not follow_up_lines:
                    content_lines.append(stripped)

        if not title and content_lines and content_lines[0]:
            if len(content_lines[0]) < 100 and not content_lines[0].endswith((".", "?", "!")):
                title = content_lines.pop(0)

        content = "\n".join(content_lines) if content_lines else text
        return AIResponse(
            title=title,
            content=content,
            tips=tips_lines,
            follow_up=follow_up_lines
        )