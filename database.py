import json
import aiosqlite
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from contextlib import asynccontextmanager

from settings import settings
from models import User, RequestRecord, GenerationStatus, ResponseType
from utils import logger


# ==================== CONNECTION MANAGER ====================

class DatabaseConnectionManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._pool: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        if self._pool is None:
            self._pool = await aiosqlite.connect(
                self.db_path,
                timeout=30.0
            )
            self._pool.row_factory = aiosqlite.Row

            await self._pool.execute("PRAGMA busy_timeout = 30000;")
            await self._pool.execute("PRAGMA journal_mode = WAL;")
            await self._pool.execute("PRAGMA synchronous = NORMAL;")
            await self._pool.execute("PRAGMA foreign_keys = ON;")

            await self._create_tables()
            logger.info(f"База данных инициализирована: {self.db_path}")

    async def _create_tables(self) -> None:
        # ============================================================
        # USERS
        # ============================================================
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                tariff TEXT DEFAULT 'free',
                is_admin BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_activity DATETIME
            )
        """)

        # ============================================================
        # REQUESTS (история)
        # ============================================================
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                section TEXT NOT NULL,
                tool TEXT NOT NULL,
                input_data TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response TEXT,
                response_type TEXT DEFAULT 'text',
                schema_version INTEGER DEFAULT 1,
                provider TEXT,
                model TEXT,
                elapsed REAL,
                status TEXT DEFAULT 'success',
                error_message TEXT,
                saved BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ============================================================
        # USER LIMITS
        # ============================================================
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS user_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                tool TEXT NOT NULL,
                generations INTEGER DEFAULT 0,
                UNIQUE(user_id, date, tool)
            )
        """)

        # ============================================================
        # SUBSCRIPTIONS
        # ============================================================
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tariff TEXT NOT NULL,
                start_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                end_date DATETIME,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
        """)

        # ============================================================
        # USAGE
        # ============================================================
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tool_id TEXT NOT NULL,
                model TEXT,
                response_type TEXT NOT NULL,
                tokens INTEGER,
                cost REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
        """)

        # ============================================================
        # PAYMENTS
        # ============================================================
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                provider_payment_id TEXT,
                tariff TEXT NOT NULL,
                period TEXT,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'RUB',
                status TEXT DEFAULT 'pending',
                metadata TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                paid_at DATETIME,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
        """)

        # ============================================================
        # SCHEMA VERSION
        # ============================================================
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await self._pool.commit()

    @asynccontextmanager
    async def connection(self):
        if self._pool is None:
            await self.initialize()
        try:
            yield self._pool
        except Exception as e:
            await self._pool.rollback()
            logger.error(f"Ошибка транзакции: {e}")
            raise

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Соединение с БД закрыто")
# ============================================================
# РЕПОЗИТОРИИ (ЭКЗЕМПЛЯРЫ)
# ============================================================

user_repository = UserRepository()
request_repository = RequestRepository()
limit_repository = LimitRepository()
