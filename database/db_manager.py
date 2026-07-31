"""
Менеджер базы данных с асинхронным подключением.
"""

import aiosqlite
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from settings import settings
from utils import logger


class DatabaseManager:
    """Менеджер подключений к SQLite."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.DB_PATH
        self._pool = None

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Контекстный менеджер для подключения к БД."""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    async def init_db(self):
        """Инициализация базы данных."""
        async with self.connection() as conn:
            # Таблица пользователей
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    tariff TEXT DEFAULT 'free',
                    tokens INTEGER DEFAULT 100,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица подписок
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    tariff TEXT,
                    start_date TIMESTAMP,
                    end_date TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                )
            """)

            # Таблица использования
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    date TEXT,
                    text_count INTEGER DEFAULT 0,
                    image_count INTEGER DEFAULT 0,
                    video_count INTEGER DEFAULT 0,
                    tokens_used INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id),
                    UNIQUE(user_id, date)
                )
            """)

            # Таблица транзакций токенов
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS token_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    type TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                )
            """)

            # Таблица запросов для статистики
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    tool_id TEXT,
                    model TEXT,
                    tokens_used INTEGER DEFAULT 0,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                )
            """)

            await conn.commit()
            logger.info("✅ База данных инициализирована")

    async def get_user_tokens(self, user_id: int) -> int:
        """Получить баланс токенов пользователя."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT tokens FROM users WHERE telegram_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            return row["tokens"] if row else 0

    async def add_tokens(self, user_id: int, amount: int, description: str = None) -> bool:
        """Добавить токены пользователю."""
        if amount <= 0:
            return False

        async with self.connection() as conn:
            try:
                await conn.execute(
                    "UPDATE users SET tokens = tokens + ? WHERE telegram_id = ?",
                    (amount, user_id)
                )
                await conn.execute(
                    """
                    INSERT INTO token_transactions (user_id, amount, type, description)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, amount, "add", description or f"Пополнение на {amount} токенов")
                )
                await conn.commit()
                logger.info(f"💰 Добавлено {amount} токенов пользователю {user_id}")
                return True
            except Exception as e:
                logger.error(f"❌ Ошибка добавления токенов: {e}")
                return False

    async def deduct_tokens(self, user_id: int, amount: int, description: str = None) -> bool:
        """Списать токены с пользователя."""
        if amount <= 0:
            return True

        async with self.connection() as conn:
            # Проверяем баланс
            current = await self.get_user_tokens(user_id)
            if current < amount:
                logger.warning(f"⚠️ Недостаточно токенов у {user_id}: {current} < {amount}")
                return False

            try:
                await conn.execute(
                    "UPDATE users SET tokens = tokens - ? WHERE telegram_id = ? AND tokens >= ?",
                    (amount, user_id, amount)
                )
                await conn.execute(
                    """
                    INSERT INTO token_transactions (user_id, amount, type, description)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, -amount, "deduct", description or f"Списание {amount} токенов")
                )
                await conn.commit()
                logger.info(f"💸 Списано {amount} токенов у пользователя {user_id}")
                return True
            except Exception as e:
                logger.error(f"❌ Ошибка списания токенов: {e}")
                return False


# Глобальный экземпляр менеджера БД
db_manager = DatabaseManager()