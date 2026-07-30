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
                autocommit=False,
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


db_manager = DatabaseConnectionManager(settings.db_path)


# ==================== MIGRATIONS ====================

class MigrationManager:
    def __init__(self):
        self.migrations = [
            {"version": 1, "columns": ["provider", "status", "error_message", "saved", "elapsed"]},
            {"version": 2, "columns": ["schema_version", "response_type"]}
        ]

    async def get_current_version(self) -> int:
        try:
            async with db_manager.connection() as conn:
                cursor = await conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
                row = await cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"Ошибка получения версии: {e}")
            return 0

    async def _column_exists(self, table: str, column: str) -> bool:
        async with db_manager.connection() as conn:
            cursor = await conn.execute(f"PRAGMA table_info({table})")
            rows = await cursor.fetchall()
            return any(row[1] == column for row in rows)

    async def _apply_column_migration(self, table: str, column: str, col_type: str = "TEXT", default: Optional[str] = None) -> bool:
        if await self._column_exists(table, column):
            return True
        try:
            sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
            if default is not None:
                sql += f" DEFAULT {default}"
            async with db_manager.connection() as conn:
                await conn.execute(sql)
                await conn.commit()
            logger.info(f"Добавлена колонка {column}")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления колонки {column}: {e}")
            return False

    async def apply_migration(self, version: int) -> bool:
        for mig in self.migrations:
            if mig["version"] == version:
                for column in mig["columns"]:
                    if not await self._apply_column_migration("requests", column):
                        return False
                try:
                    async with db_manager.connection() as conn:
                        await conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
                        await conn.commit()
                    return True
                except Exception as e:
                    logger.error(f"Ошибка сохранения версии: {e}")
                    return False
        return False

    async def migrate(self) -> bool:
        current = await self.get_current_version()
        for mig in self.migrations:
            if mig["version"] > current:
                if not await self.apply_migration(mig["version"]):
                    return False
        return True


migration_manager = MigrationManager()


async def run_migrations() -> bool:
    return await migration_manager.migrate()


# ==================== USER REPOSITORY ====================

class UserRepository:
    async def add_user(self, telegram_id: int, username: Optional[str], first_name: Optional[str]) -> bool:
        async with db_manager.connection() as conn:
            cursor = await conn.execute(
                "INSERT OR IGNORE INTO users (telegram_id, username, first_name, last_activity) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (telegram_id, username, first_name)
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def get_user(self, telegram_id: int) -> Optional[User]:
        async with db_manager.connection() as conn:
            cursor = await conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = await cursor.fetchone()
            if row:
                return User(
                    id=row["id"],
                    telegram_id=row["telegram_id"],
                    username=row["username"],
                    first_name=row["first_name"],
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
                )
            return None

    async def update_activity(self, telegram_id: int) -> bool:
        async with db_manager.connection() as conn:
            cursor = await conn.execute(
                "UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                (telegram_id,)
            )
            await conn.commit()
            return cursor.rowcount > 0


user_repository = UserRepository()


# ==================== REQUEST REPOSITORY ====================

class RequestRepository:
    async def save_request(
        self,
        user_id: int,
        section: str,
        tool: str,
        input_data: Dict[str, Any],
        prompt: str,
        response: Optional[str] = None,
        response_type: ResponseType = ResponseType.TEXT,
        schema_version: int = 1,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        elapsed: Optional[float] = None,
        status: GenerationStatus = GenerationStatus.SUCCESS,
        error_message: Optional[str] = None,
        saved: bool = False
    ) -> Optional[int]:
        try:
            input_data_json = json.dumps(input_data, ensure_ascii=False)
            async with db_manager.connection() as conn:
                cursor = await conn.execute(
                    """
                    INSERT INTO requests 
                    (user_id, section, tool, input_data, prompt, response, response_type, schema_version,
                     provider, model, elapsed, status, error_message, saved)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id, section, tool, input_data_json, prompt,
                        response, response_type.value, schema_version,
                        provider, model, elapsed,
                        status.value, error_message, saved
                    )
                )
                await conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка сохранения запроса: {e}")
            return None


request_repository = RequestRepository()


# ==================== LIMIT REPOSITORY ====================

class LimitRepository:
    async def get_generations_count(self, user_id: int, tool: str, target_date: Optional[date] = None) -> int:
        target_date = target_date or date.today()
        date_str = target_date.isoformat()
        async with db_manager.connection() as conn:
            cursor = await conn.execute(
                "SELECT generations FROM user_limits WHERE user_id = ? AND date = ? AND tool = ?",
                (user_id, date_str, tool)
            )
            row = await cursor.fetchone()
            return row["generations"] if row else 0

    async def increment_if_under_limit(self, user_id: int, tool: str, limit: int, target_date: Optional[date] = None) -> Tuple[bool, int]:
        target_date = target_date or date.today()
        date_str = target_date.isoformat()

        async with db_manager.connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = await conn.execute(
                    "UPDATE user_limits SET generations = generations + 1 WHERE user_id = ? AND date = ? AND tool = ? AND generations < ?",
                    (user_id, date_str, tool, limit)
                )
                if cursor.rowcount > 0:
                    new_cursor = await conn.execute(
                        "SELECT generations FROM user_limits WHERE user_id = ? AND date = ? AND tool = ?",
                        (user_id, date_str, tool)
                    )
                    row = await new_cursor.fetchone()
                    await conn.commit()
                    return True, row["generations"] if row else 1

                check_cursor = await conn.execute(
                    "SELECT generations FROM user_limits WHERE user_id = ? AND date = ? AND tool = ?",
                    (user_id, date_str, tool)
                )
                row = await check_cursor.fetchone()
                if row:
                    await conn.commit()
                    return False, row["generations"]

                await conn.execute(
                    "INSERT INTO user_limits (user_id, date, tool, generations) VALUES (?, ?, ?, 1)",
                    (user_id, date_str, tool)
                )
                await conn.commit()
                return True, 1
            except Exception as e:
                await conn.rollback()
                logger.error(f"Ошибка инкремента лимита: {e}")
                raise


limit_repository = LimitRepository()