"""
Сервис для отслеживания использования лимитов.
"""

from datetime import datetime
from typing import Union
from database import db_manager
from models import ResponseType
from services.subscription_service import get_user_limit
from utils import logger


async def get_user_usage_today(user_id: int, response_type: Union[str, ResponseType]) -> int:
    """Получить использование за сегодня."""
    if hasattr(response_type, 'value'):
        response_type = response_type.value
    
    return await db_manager.get_user_usage_today(user_id, response_type)


async def track_usage(user_id: int, response_type: Union[str, ResponseType]):
    """Отследить использование."""
    if hasattr(response_type, 'value'):
        response_type = response_type.value
    
    await db_manager.track_usage(user_id, response_type)
    logger.info(f"📊 Отслежено использование {response_type} для {user_id}")


async def check_and_consume_limit(user_id: int, limit_type: str) -> bool:
    """
    Проверить и использовать лимит.
    Возвращает True если лимит доступен, False если лимит превышен.
    """
    try:
        # Получаем лимит для пользователя
        limit_type_enum = None
        if limit_type == "text":
            limit_type_enum = ResponseType.TEXT
        elif limit_type == "image":
            limit_type_enum = ResponseType.IMAGE
        elif limit_type == "video":
            limit_type_enum = ResponseType.VIDEO
        else:
            return True

        limit = await get_user_limit(user_id, limit_type_enum)

        # Если лимит 0 - безлимит
        if limit == 0:
            return True

        # Получаем текущее использование
        used = await get_user_usage_today(user_id, limit_type)

        # Проверяем не превышен ли лимит
        if used >= limit:
            logger.warning(f"⚠️ Лимит {limit_type} превышен для {user_id}: {used}/{limit}")
            return False

        # Используем лимит
        await track_usage(user_id, limit_type)
        logger.info(f"✅ Использован {limit_type} для {user_id}: {used+1}/{limit}")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка проверки лимита: {e}")
        return False


async def get_usage_stats(user_id: int) -> dict:
    """Получить статистику использования пользователя."""
    return {
        "text": await get_user_usage_today(user_id, "text"),
        "image": await get_user_usage_today(user_id, "image"),
        "video": await get_user_usage_today(user_id, "video"),
    }
