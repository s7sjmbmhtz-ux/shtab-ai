"""
Сервис для работы с подписками и тарифами.
"""

from datetime import datetime, timedelta
from typing import Optional
from database import db_manager
from models import Tariff, ResponseType
from tariffs import get_tariff
from settings import settings


async def get_user_tariff(user_id: int) -> Tariff:
    """Получает текущий тариф пользователя."""
    async with db_manager.connection() as conn:
        cursor = await conn.execute(
            "SELECT tariff FROM users WHERE telegram_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        if row:
            return Tariff(row["tariff"])
    return Tariff.FREE


async def set_user_tariff(user_id: int, tariff: Tariff) -> bool:
    """Устанавливает тариф пользователю."""
    async with db_manager.connection() as conn:
        cursor = await conn.execute(
            "UPDATE users SET tariff = ? WHERE telegram_id = ?",
            (tariff.value, user_id)
        )
        await conn.commit()
        return cursor.rowcount > 0


async def get_user_limit(user_id: int, limit_type: ResponseType) -> int:
    """Возвращает дневной лимит пользователя по типу."""
    tariff = await get_user_tariff(user_id)
    tariff_config = get_tariff(tariff.value)

    if limit_type == ResponseType.TEXT:
        return tariff_config.get("text_limit", 3)
    elif limit_type == ResponseType.IMAGE:
        return tariff_config.get("image_limit", 1)
    return 0


async def activate_subscription(user_id: int, tariff: Tariff, period_days: int = 30) -> bool:
    """Активирует подписку, деактивируя предыдущие."""
    async with db_manager.connection() as conn:
        # Деактивируем все активные подписки
        await conn.execute(
            "UPDATE subscriptions SET status = 'expired' WHERE user_id = ? AND status = 'active'",
            (user_id,)
        )

        # Создаём новую
        start_date = datetime.now()
        end_date = start_date + timedelta(days=period_days)

        await conn.execute(
            """
            INSERT INTO subscriptions (user_id, tariff, start_date, end_date, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, tariff.value, start_date.isoformat(), end_date.isoformat(), 'active')
        )
        await conn.commit()

        # Обновляем тариф в users
        await set_user_tariff(user_id, tariff)

        return True


async def get_subscription_end_date(user_id: int) -> Optional[datetime]:
    """Возвращает дату окончания активной подписки."""
    async with db_manager.connection() as conn:
        cursor = await conn.execute(
            """
            SELECT end_date FROM subscriptions
            WHERE user_id = ? AND status = 'active'
            ORDER BY end_date DESC LIMIT 1
            """,
            (user_id,)
        )
        row = await cursor.fetchone()
        if row and row["end_date"]:
            return datetime.fromisoformat(row["end_date"])
        return None