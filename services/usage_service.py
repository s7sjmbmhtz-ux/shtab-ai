"""
Сервис для учёта использования AI.
"""

from datetime import datetime
from typing import Optional
from database import db_manager
from models import ResponseType


async def track_usage(
    user_id: int,
    tool_id: str,
    model: str,
    response_type: ResponseType,
    tokens: Optional[int] = None,
    cost: Optional[float] = None
) -> bool:
    """Записывает использование AI."""
    
    # Проверяем, существует ли пользователь
    async with db_manager.connection() as conn:
        cursor = await conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?",
            (user_id,)
        )
        user = await cursor.fetchone()
        if not user:
            # Если пользователь не найден — создаём
            await conn.execute(
                "INSERT OR IGNORE INTO users (telegram_id) VALUES (?)",
                (user_id,)
            )
            await conn.commit()
    
    async with db_manager.connection() as conn:
        await conn.execute(
            """
            INSERT INTO usage (user_id, tool_id, model, response_type, tokens, cost, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, tool_id, model, response_type.value, tokens, cost, datetime.now())
        )
        await conn.commit()
        return True


async def get_user_usage_today(user_id: int, response_type: ResponseType) -> int:
    """Возвращает количество использований за сегодня по типу."""
    today = datetime.now().date()

    async with db_manager.connection() as conn:
        cursor = await conn.execute(
            """
            SELECT COUNT(*) as count FROM usage
            WHERE user_id = ? AND DATE(created_at) = ? AND response_type = ?
            """,
            (user_id, today.isoformat(), response_type.value)
        )
        row = await cursor.fetchone()
        return row["count"] if row else 0


async def check_and_consume_limit(
    user_id: int,
    response_type: ResponseType,
    limit: int
) -> tuple[bool, int, int]:
    """
    Проверяет и атомарно списывает лимит.
    Возвращает: (разрешено, использовано, осталось)
    """
    today = datetime.now().date().isoformat()

    async with db_manager.connection() as conn:
        await conn.execute("BEGIN IMMEDIATE")

        try:
            cursor = await conn.execute(
                """
                SELECT COUNT(*) as count FROM usage
                WHERE user_id = ? AND DATE(created_at) = ? AND response_type = ?
                """,
                (user_id, today, response_type.value)
            )
            row = await cursor.fetchone()
            used = row["count"] if row else 0

            if used >= limit:
                await conn.commit()
                return False, used, 0

            await conn.commit()
            return True, used, limit - used

        except Exception as e:
            await conn.rollback()
            raise
