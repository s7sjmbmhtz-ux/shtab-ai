"""
Административные функции.
"""

from settings import settings


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id == settings.ADMIN_TELEGRAM_ID


async def get_admin_stats():
    """Собирает статистику для админ-панели."""
    from database import db_manager
    from tariffs import TARIFFS

    async with db_manager.connection() as conn:
        # Всего пользователей
        cursor = await conn.execute("SELECT COUNT(*) as total FROM users")
        total_row = await cursor.fetchone()
        total = total_row["total"] if total_row else 0

        # По тарифам
        stats = {"total": total}
        for tariff_id in TARIFFS.keys():
            cursor = await conn.execute(
                "SELECT COUNT(*) as count FROM users WHERE tariff = ?",
                (tariff_id,)
            )
            row = await cursor.fetchone()
            stats[tariff_id] = row["count"] if row else 0

        # Расходы AI
        cursor = await conn.execute("SELECT COALESCE(SUM(cost), 0) as total_cost FROM usage")
        row = await cursor.fetchone()
        stats["ai_cost"] = row["total_cost"] if row else 0

        # Доход (успешные платежи)
        cursor = await conn.execute("SELECT COALESCE(SUM(amount), 0) as revenue FROM payments WHERE status = 'success'")
        row = await cursor.fetchone()
        stats["revenue"] = row["revenue"] if row else 0

        # Общее количество токенов в системе
        cursor = await conn.execute("SELECT COALESCE(SUM(tokens), 0) as total_tokens FROM users")
        row = await cursor.fetchone()
        stats["total_tokens"] = row["total_tokens"] if row else 0

        return stats
