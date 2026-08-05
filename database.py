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
                tokens INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_activity DATETIME
            )
        """)

        # ============================================================
        # TOKEN TRANSACTIONS
        # ============================================================
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS token_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                package TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
        """)

        # ============================================================
        # REQUESTS
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
                tariff TEXT,
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

        # Одноразовые бесплатные генерации для каждого нового пользователя.
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS free_generation_credits (
                user_id INTEGER PRIMARY KEY,
                text_left INTEGER NOT NULL DEFAULT 1,
                image_left INTEGER NOT NULL DEFAULT 1,
                video_left INTEGER NOT NULL DEFAULT 1,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
        """)

        # Цены хранятся в БД, чтобы их можно было менять без правки кода.
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS model_prices (
                model_key TEXT PRIMARY KEY,
                token_cost INTEGER NOT NULL CHECK(token_cost >= 0),
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS user_onboarding (
                user_id INTEGER PRIMARY KEY,
                accepted BOOLEAN NOT NULL DEFAULT FALSE,
                accepted_at DATETIME,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
        """)

        await self._pool.commit()
        await self._seed_model_prices()

    async def _seed_model_prices(self) -> None:
        from model_catalog import MODELS
        for model in MODELS.values():
            await self._pool.execute(
                """
                INSERT INTO model_prices (model_key, token_cost, enabled)
                VALUES (?, ?, ?)
                ON CONFLICT(model_key) DO NOTHING
                """,
                (model.key, model.token_cost, int(model.enabled)),
            )
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
    # TOKEN OPERATIONS
    # ============================================================

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
                    VALUES (?, ?, 'purchase', ?)
                    """,
                    (user_id, amount, description or f"Пополнение на {amount} токенов")
                )
                await conn.commit()
                logger.info(f"💰 Добавлено {amount} токенов пользователю {user_id}")
                return True
            except Exception as e:
                logger.error(f"Ошибка добавления токенов: {e}")
                return False

    async def deduct_tokens(self, user_id: int, amount: int, description: str = None) -> bool:
        """Списать токены у пользователя."""
        if amount <= 0:
            return True

        async with self.connection() as conn:
            current = await self.get_user_tokens(user_id)
            if current < amount:
                logger.warning(f"Недостаточно токенов у {user_id}: {current} < {amount}")
                return False

            try:
                await conn.execute(
                    "UPDATE users SET tokens = tokens - ? WHERE telegram_id = ? AND tokens >= ?",
                    (amount, user_id, amount)
                )
                await conn.execute(
                    """
                    INSERT INTO token_transactions (user_id, amount, type, description)
                    VALUES (?, ?, 'spend', ?)
                    """,
                    (user_id, -amount, description or f"Списание {amount} токенов")
                )
                await conn.commit()
                logger.info(f"💸 Списано {amount} токенов у пользователя {user_id}")
                return True
            except Exception as e:
                logger.error(f"Ошибка списания токенов: {e}")
                return False

    async def refund_tokens(self, user_id: int, amount: int, description: str = None) -> bool:
        """Вернуть токены пользователю."""
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
                    VALUES (?, ?, 'refund', ?)
                    """,
                    (user_id, amount, description or f"Возврат {amount} токенов")
                )
                await conn.commit()
                logger.info(f"🔄 Возвращено {amount} токенов пользователю {user_id}")
                return True
            except Exception as e:
                logger.error(f"Ошибка возврата токенов: {e}")
                return False

    async def get_token_transactions(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Получить историю транзакций пользователя."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, amount, type, description, package, created_at
                FROM token_transactions
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def reserve_generation(
        self,
        user_id: int,
        generation_kind: str,
        model_key: str,
        token_cost: int,
    ) -> Dict[str, Any]:
        """Атомарно использует бесплатную попытку либо списывает токены."""
        if generation_kind not in {"text", "image", "video"}:
            raise ValueError("Некорректный тип генерации")
        column = f"{generation_kind}_left"
        async with self.connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                await conn.execute(
                    "INSERT OR IGNORE INTO free_generation_credits (user_id) VALUES (?)",
                    (user_id,),
                )
                cursor = await conn.execute(
                    f"SELECT {column} FROM free_generation_credits WHERE user_id = ?",
                    (user_id,),
                )
                row = await cursor.fetchone()
                if row and row[column] > 0:
                    await conn.execute(
                        f"UPDATE free_generation_credits SET {column} = {column} - 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                        (user_id,),
                    )
                    await conn.execute(
                        """INSERT INTO token_transactions
                           (user_id, amount, type, description)
                           VALUES (?, 0, 'free_trial', ?)""",
                        (user_id, f"Бесплатная генерация: {model_key}"),
                    )
                    await conn.commit()
                    return {"source": "free_trial", "amount": 0, "balance": await self.get_user_tokens(user_id)}

                price_cursor = await conn.execute(
                    "SELECT token_cost, enabled FROM model_prices WHERE model_key = ?",
                    (model_key,),
                )
                price_row = await price_cursor.fetchone()
                actual_cost = int(price_row["token_cost"]) if price_row else int(token_cost)
                if price_row and not bool(price_row["enabled"]):
                    raise ValueError("Модель временно отключена")

                update = await conn.execute(
                    "UPDATE users SET tokens = tokens - ? WHERE telegram_id = ? AND tokens >= ?",
                    (actual_cost, user_id, actual_cost),
                )
                if update.rowcount != 1:
                    cursor = await conn.execute(
                        "SELECT tokens FROM users WHERE telegram_id = ?", (user_id,)
                    )
                    balance_row = await cursor.fetchone()
                    await conn.rollback()
                    return {"source": "insufficient", "amount": actual_cost, "balance": int(balance_row["tokens"] if balance_row else 0)}

                await conn.execute(
                    """INSERT INTO token_transactions
                       (user_id, amount, type, description)
                       VALUES (?, ?, 'spend', ?)""",
                    (user_id, -actual_cost, f"Генерация: {model_key}"),
                )
                await conn.commit()
                return {"source": "tokens", "amount": actual_cost, "balance": await self.get_user_tokens(user_id)}
            except Exception:
                await conn.rollback()
                raise

    async def refund_generation(
        self,
        user_id: int,
        generation_kind: str,
        model_key: str,
        amount: int,
        source: str,
        reason: str,
    ) -> None:
        """Возвращает списание при ошибке провайдера."""
        column = f"{generation_kind}_left"
        async with self.connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                if source == "free_trial":
                    await conn.execute(
                        f"UPDATE free_generation_credits SET {column} = {column} + 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                        (user_id,),
                    )
                elif source == "tokens" and amount > 0:
                    await conn.execute(
                        "UPDATE users SET tokens = tokens + ? WHERE telegram_id = ?",
                        (amount, user_id),
                    )
                await conn.execute(
                    """INSERT INTO token_transactions
                       (user_id, amount, type, description)
                       VALUES (?, ?, 'refund', ?)""",
                    (user_id, amount, f"{reason}: {model_key}"),
                )
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

    async def get_free_credits(self, user_id: int) -> Dict[str, int]:
        async with self.connection() as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO free_generation_credits (user_id) VALUES (?)",
                (user_id,),
            )
            await conn.commit()
            cursor = await conn.execute(
                "SELECT text_left, image_left, video_left FROM free_generation_credits WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else {"text_left": 0, "image_left": 0, "video_left": 0}

    async def set_model_price(self, model_key: str, token_cost: int, enabled: bool = True) -> None:
        if token_cost < 0:
            raise ValueError("Цена не может быть отрицательной")
        async with self.connection() as conn:
            await conn.execute(
                """INSERT INTO model_prices (model_key, token_cost, enabled, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(model_key) DO UPDATE SET
                     token_cost = excluded.token_cost,
                     enabled = excluded.enabled,
                     updated_at = CURRENT_TIMESTAMP""",
                (model_key, token_cost, int(enabled)),
            )
            await conn.commit()

    # ============================================================
    # USER OPERATIONS
    # ============================================================

    async def set_user_tariff(self, user_id: int, tariff: str):
        """Установить тариф пользователю."""
        async with self.connection() as conn:
            await conn.execute(
                "UPDATE users SET tariff = ? WHERE telegram_id = ?",
                (tariff, user_id)
            )
            await conn.commit()

    async def get_user_tariff(self, user_id: int) -> str:
        """Получить тариф пользователя."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT tariff FROM users WHERE telegram_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            return row["tariff"] if row else "free"

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить данные пользователя."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def add_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """Добавить пользователя."""
        async with self.connection() as conn:
            try:
                await conn.execute(
                    """
                    INSERT OR IGNORE INTO users (telegram_id, username, first_name, tokens)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, username, first_name, 0)
                )
                await conn.execute(
                    """
                    INSERT OR IGNORE INTO free_generation_credits
                    (user_id, text_left, image_left, video_left)
                    VALUES (?, 1, 1, 1)
                    """,
                    (user_id,),
                )
                await conn.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка добавления пользователя: {e}")
                return False

    async def update_activity(self, user_id: int) -> bool:
        """Обновить активность пользователя."""
        async with self.connection() as conn:
            try:
                await conn.execute(
                    "UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                    (user_id,)
                )
                await conn.commit()
                return True
            except Exception as e:
                logger.error(f"Ошибка обновления активности: {e}")
                return False

    async def get_subscription_end_date(self, user_id: int) -> Optional[str]:
        """Получить дату окончания подписки."""
        async with self.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT end_date FROM subscriptions
                WHERE user_id = ? AND status = 'active'
                ORDER BY end_date DESC LIMIT 1
                """,
                (user_id,)
            )
            row = await cursor.fetchone()
            return row["end_date"] if row else None

    async def is_onboarding_accepted(self, user_id: int) -> bool:
        async with self.connection() as conn:
            cursor = await conn.execute(
                "SELECT accepted FROM user_onboarding WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            return bool(row["accepted"]) if row else False

    async def accept_onboarding(self, user_id: int) -> None:
        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT INTO user_onboarding (user_id, accepted, accepted_at)
                VALUES (?, TRUE, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    accepted = TRUE,
                    accepted_at = CURRENT_TIMESTAMP
                """,
                (user_id,),
            )
            await conn.commit()


# ==================== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР ====================

db_manager = DatabaseConnectionManager(settings.DB_PATH)


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


# ============================================================
# USER REPOSITORY
# ============================================================

class UserRepository:
    async def add_user(self, telegram_id: int, username: Optional[str], first_name: Optional[str]) -> bool:
        return await db_manager.add_user(telegram_id, username, first_name)

    async def get_user(self, telegram_id: int) -> Optional[User]:
        data = await db_manager.get_user(telegram_id)
        if data:
            return User(
                id=data["id"],
                telegram_id=data["telegram_id"],
                username=data["username"],
                first_name=data["first_name"],
                tariff=data["tariff"],
                is_admin=data["is_admin"] == 1,
                tokens=data.get("tokens", 0),
                created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
            )
        return None

    async def update_activity(self, telegram_id: int) -> bool:
        return await db_manager.update_activity(telegram_id)


# ============================================================
# TOKEN REPOSITORY
# ============================================================

class TokenRepository:
    async def get_user_tokens(self, user_id: int) -> int:
        return await db_manager.get_user_tokens(user_id)

    async def add_tokens(self, user_id: int, amount: int, description: str = None, package: str = None) -> bool:
        return await db_manager.add_tokens(user_id, amount, description)

    async def add_bonus_tokens(self, user_id: int, amount: int, description: str = None) -> bool:
        return await db_manager.add_tokens(user_id, amount, f"Бонус: {description}")

    async def deduct_tokens(self, user_id: int, amount: int, description: str = None) -> bool:
        return await db_manager.deduct_tokens(user_id, amount, description)

    async def refund_tokens(self, user_id: int, amount: int, description: str = None) -> bool:
        return await db_manager.refund_tokens(user_id, amount, description)

    async def get_token_transactions(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        return await db_manager.get_token_transactions(user_id, limit)


# ============================================================
# REQUEST REPOSITORY
# ============================================================

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


# ============================================================
# LIMIT REPOSITORY
# ============================================================

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


# ============================================================
# РЕПОЗИТОРИИ (ЭКЗЕМПЛЯРЫ)
# ============================================================

user_repository = UserRepository()
request_repository = RequestRepository()
limit_repository = LimitRepository()
token_repository = TokenRepository()
