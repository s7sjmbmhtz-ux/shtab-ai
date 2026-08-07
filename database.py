import asyncio
import json
import math
import aiosqlite
from datetime import date, datetime
from typing import Optional, Dict, Any, List, Tuple
from contextlib import asynccontextmanager

from settings import settings
from models import GenerationStatus, ResponseType, User
from utils import logger


# ==================== CONNECTION MANAGER ====================

class DatabaseConnectionManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._pool: Optional[aiosqlite.Connection] = None
        self._initialized = False
        self._initialize_lock = asyncio.Lock()
        # aiosqlite не является пулом: все корутины используют одно соединение.
        # Реентерабельная блокировка не даёт транзакциям разных апдейтов
        # перемешиваться и при этом разрешает вложенные чтения в одной задаче.
        self._connection_lock = asyncio.Lock()
        self._connection_owner: Optional[asyncio.Task[Any]] = None
        self._connection_depth = 0
        self._model_enabled_cache: dict[str, bool] = {}
        self._model_price_cache: dict[str, int] = {}
        self._model_provider_cost_cache: dict[str, float] = {}
        self._model_margin_cache: dict[str, float] = {}
        self._model_cost_source_cache: dict[str, str] = {}
        self._package_cache: dict[str, dict[str, Any]] = {}

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if self._initialized:
                return
            connection = await aiosqlite.connect(
                self.db_path,
                timeout=30.0,
            )
            connection.row_factory = aiosqlite.Row
            self._pool = connection
            try:
                await connection.execute("PRAGMA busy_timeout = 30000;")
                await connection.execute("PRAGMA journal_mode = WAL;")
                await connection.execute("PRAGMA synchronous = NORMAL;")
                await connection.execute("PRAGMA foreign_keys = ON;")

                await self._create_tables()
            except Exception:
                await connection.close()
                self._pool = None
                self._initialized = False
                raise
            self._initialized = True
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
        await self._pool.execute(
            "CREATE INDEX IF NOT EXISTS idx_payments_public_id "
            "ON payments(provider_payment_id)"
        )
        await self._pool.execute(
            "CREATE INDEX IF NOT EXISTS idx_payments_status_created "
            "ON payments(status, created_at)"
        )

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
                provider_cost_rub REAL,
                min_margin_percent REAL,
                cost_source TEXT NOT NULL DEFAULT 'estimated',
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

        # Служебные таблицы админ-панели.
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS admin_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                target_user_id INTEGER,
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS token_packages (
                package_key TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                tokens INTEGER NOT NULL CHECK(tokens > 0),
                price_rub INTEGER NOT NULL CHECK(price_rub > 0),
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS admin_broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                target_count INTEGER NOT NULL DEFAULT 0,
                sent_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'created',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                finished_at DATETIME
            )
        """)

        # Единый журнал расходов и расчётной выручки по генерациям.
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS generation_economics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                model_key TEXT NOT NULL,
                kind TEXT NOT NULL,
                charge_source TEXT NOT NULL,
                tokens_charged INTEGER NOT NULL DEFAULT 0,
                revenue_rub REAL NOT NULL DEFAULT 0,
                provider_cost_rub REAL,
                status TEXT NOT NULL DEFAULT 'reserved',
                provider_request_id TEXT,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id)
            )
        """)
        await self._pool.execute(
            "CREATE INDEX IF NOT EXISTS idx_generation_economics_created "
            "ON generation_economics(created_at, status)"
        )
        await self._pool.execute(
            "CREATE INDEX IF NOT EXISTS idx_generation_economics_model "
            "ON generation_economics(model_key, created_at)"
        )

        # Асинхронные медиа-задачи переживают перезапуск процесса.
        await self._pool.execute("""
            CREATE TABLE IF NOT EXISTS generation_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                model_key TEXT NOT NULL,
                kind TEXT NOT NULL,
                provider_request_id TEXT,
                economic_id INTEGER NOT NULL UNIQUE,
                token_cost INTEGER NOT NULL DEFAULT 0,
                charge_source TEXT NOT NULL,
                caption TEXT,
                duration INTEGER,
                result_limit INTEGER NOT NULL DEFAULT 1,
                result_urls TEXT,
                status TEXT NOT NULL DEFAULT 'processing',
                attempts INTEGER NOT NULL DEFAULT 0,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                delivered_at DATETIME,
                FOREIGN KEY (user_id) REFERENCES users(telegram_id),
                FOREIGN KEY (economic_id) REFERENCES generation_economics(id)
            )
        """)
        await self._pool.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_generation_jobs_request "
            "ON generation_jobs(provider_request_id) "
            "WHERE provider_request_id IS NOT NULL"
        )
        await self._pool.execute(
            "CREATE INDEX IF NOT EXISTS idx_generation_jobs_pending "
            "ON generation_jobs(status, updated_at)"
        )
        await self._pool.execute(
            "CREATE INDEX IF NOT EXISTS idx_generation_jobs_user "
            "ON generation_jobs(user_id, status)"
        )

        # CREATE TABLE IF NOT EXISTS не добавляет колонки в существующую БД.
        await self._ensure_column("users", "is_blocked", "BOOLEAN NOT NULL DEFAULT FALSE")
        await self._ensure_column("users", "blocked_at", "DATETIME")
        await self._ensure_column("users", "blocked_reason", "TEXT")
        await self._ensure_column("model_prices", "provider_cost_rub", "REAL")
        await self._ensure_column("model_prices", "min_margin_percent", "REAL")
        await self._ensure_column(
            "model_prices",
            "cost_source",
            "TEXT NOT NULL DEFAULT 'estimated'",
        )

        await self._pool.commit()
        await self._seed_model_prices()
        await self._seed_token_packages()
        await self.refresh_runtime_caches()

    async def _ensure_column(self, table: str, column: str, definition: str) -> None:
        cursor = await self._pool.execute(f"PRAGMA table_info({table})")
        rows = await cursor.fetchall()
        if any(row[1] == column for row in rows):
            return
        await self._pool.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    async def _seed_model_prices(self) -> None:
        from model_catalog import MODELS
        from video_options import default_video_selection, video_cost_rubles
        for model in MODELS.values():
            estimated_provider_cost = round(model.token_cost / 6.0, 4)
            if model.kind.value == "video":
                try:
                    estimated_provider_cost = round(
                        video_cost_rubles(
                            model.key,
                            default_video_selection(model.key),
                        ),
                        4,
                    )
                except (KeyError, ValueError):
                    pass
            await self._pool.execute(
                """
                INSERT INTO model_prices
                    (model_key, token_cost, enabled, provider_cost_rub,
                     min_margin_percent, cost_source)
                VALUES (?, ?, ?, ?, ?, 'estimated')
                ON CONFLICT(model_key) DO NOTHING
                """,
                (
                    model.key,
                    model.token_cost,
                    int(model.enabled),
                    estimated_provider_cost,
                    settings.ECONOMY_MIN_MARGIN_PERCENT,
                ),
            )
            # Для старой БД новые поля заполняются консервативной оценкой.
            await self._pool.execute(
                """UPDATE model_prices
                   SET provider_cost_rub=COALESCE(provider_cost_rub, ?),
                       min_margin_percent=COALESCE(min_margin_percent, ?),
                       cost_source=COALESCE(cost_source, 'estimated')
                   WHERE model_key=?""",
                (
                    estimated_provider_cost,
                    settings.ECONOMY_MIN_MARGIN_PERCENT,
                    model.key,
                ),
            )
        await self._pool.commit()

    async def _seed_token_packages(self) -> None:
        from model_catalog import TOKEN_PACKAGES
        for index, (key, package) in enumerate(TOKEN_PACKAGES.items()):
            await self._pool.execute(
                """
                INSERT INTO token_packages
                    (package_key, title, tokens, price_rub, enabled, sort_order)
                VALUES (?, ?, ?, ?, TRUE, ?)
                ON CONFLICT(package_key) DO NOTHING
                """,
                (key, package["title"], int(package["tokens"]), int(package["price_rub"]), index),
            )
        await self._pool.commit()

    async def refresh_runtime_caches(self) -> None:
        model_rows = await (await self._pool.execute(
            """SELECT model_key, token_cost, enabled, provider_cost_rub,
                      min_margin_percent, cost_source
               FROM model_prices"""
        )).fetchall()
        self._model_enabled_cache = {
            str(row["model_key"]): bool(row["enabled"]) for row in model_rows
        }
        self._model_price_cache = {
            str(row["model_key"]): int(row["token_cost"]) for row in model_rows
        }
        self._model_provider_cost_cache = {
            str(row["model_key"]): float(row["provider_cost_rub"])
            for row in model_rows if row["provider_cost_rub"] is not None
        }
        self._model_margin_cache = {
            str(row["model_key"]): float(
                row["min_margin_percent"]
                if row["min_margin_percent"] is not None
                else settings.ECONOMY_MIN_MARGIN_PERCENT
            )
            for row in model_rows
        }
        self._model_cost_source_cache = {
            str(row["model_key"]): str(row["cost_source"] or "estimated")
            for row in model_rows
        }

        package_rows = await (await self._pool.execute(
            """SELECT package_key, title, tokens, price_rub, enabled, sort_order
               FROM token_packages ORDER BY sort_order, package_key"""
        )).fetchall()
        self._package_cache = {
            str(row["package_key"]): dict(row) for row in package_rows
        }

    def is_model_enabled_cached(self, model_key: str) -> bool:
        enabled = self._model_enabled_cache.get(model_key, True)
        price = self._model_price_cache.get(model_key)
        if not enabled or (price is not None and price <= 0):
            return False
        if price is None:
            return True
        price = self.get_model_safety_price(model_key, price)
        return self.is_generation_price_safe(model_key, price)

    @staticmethod
    def get_model_safety_price(model_key: str, fallback: int) -> int:
        """Для видео использует цену конфигурации по умолчанию, не старую базу."""
        try:
            from model_catalog import GenerationKind, get_model
            from video_options import default_video_selection, video_cost_tokens

            model = get_model(model_key)
            if model.kind == GenerationKind.VIDEO:
                return video_cost_tokens(
                    model_key,
                    default_video_selection(model_key),
                )
        except (KeyError, ValueError):
            pass
        return int(fallback)

    def get_model_price_cached(self, model_key: str, default: int) -> int:
        """Возвращает актуальную цену модели из админки без запроса к БД."""
        return int(self._model_price_cache.get(model_key, default))

    def get_model_provider_cost_cached(
        self,
        model_key: str,
        default: Optional[float] = None,
    ) -> Optional[float]:
        value = self._model_provider_cost_cache.get(model_key, default)
        return float(value) if value is not None else None

    def get_model_margin_cached(self, model_key: str) -> float:
        return float(
            self._model_margin_cache.get(
                model_key,
                settings.ECONOMY_MIN_MARGIN_PERCENT,
            )
        )

    def get_model_cost_source_cached(self, model_key: str) -> str:
        return self._model_cost_source_cache.get(model_key, "estimated")

    def minimum_safe_tokens(
        self,
        model_key: str,
        *,
        provider_cost_rub: Optional[float] = None,
    ) -> Optional[int]:
        """Минимальная цена с учётом резерва и требуемой маржи."""
        cost = (
            self.get_model_provider_cost_cached(model_key)
            if provider_cost_rub is None
            else float(provider_cost_rub)
        )
        if cost is None or cost <= 0:
            return None
        margin = min(99.0, max(0.0, self.get_model_margin_cached(model_key)))
        reserve = max(0.0, settings.ECONOMY_RESERVE_PERCENT)
        required_revenue = cost * (1.0 + reserve / 100.0) / (1.0 - margin / 100.0)
        token_value_rub = settings.ECONOMY_TOKEN_VALUE_KOPEKS / 100.0
        return max(1, int(math.ceil(required_revenue / token_value_rub)))

    def is_generation_price_safe(
        self,
        model_key: str,
        token_cost: int,
        *,
        provider_cost_rub: Optional[float] = None,
    ) -> bool:
        minimum = self.minimum_safe_tokens(
            model_key,
            provider_cost_rub=provider_cost_rub,
        )
        if minimum is None:
            return not settings.ECONOMY_REQUIRE_KNOWN_COST
        return int(token_cost) >= minimum

    def assert_generation_price_safe(
        self,
        model_key: str,
        token_cost: int,
        *,
        provider_cost_rub: Optional[float] = None,
    ) -> None:
        minimum = self.minimum_safe_tokens(
            model_key,
            provider_cost_rub=provider_cost_rub,
        )
        if minimum is None and settings.ECONOMY_REQUIRE_KNOWN_COST:
            raise ValueError(
                "Модель временно отключена: себестоимость не настроена"
            )
        if minimum is not None and int(token_cost) < minimum:
            raise ValueError(
                "Модель временно отключена защитой маржи. "
                f"Требуется не менее {minimum} 💎"
            )

    def get_token_packages_cached(self, *, enabled_only: bool = True) -> list[dict[str, Any]]:
        packages = list(self._package_cache.values())
        if enabled_only:
            packages = [
                item
                for item in packages
                if bool(item.get("enabled")) and self.is_token_package_safe(item)
            ]
        return [dict(item) for item in packages]

    def get_token_package_cached(self, package_key: str) -> Optional[dict[str, Any]]:
        value = self._package_cache.get(package_key)
        return dict(value) if value else None

    @staticmethod
    def is_token_package_safe(package: Dict[str, Any]) -> bool:
        from model_catalog import MIN_PACKAGE_TOKEN_PRICE_KOPEKS

        try:
            tokens = int(package["tokens"])
            price_rub = int(package["price_rub"])
        except (KeyError, TypeError, ValueError):
            return False
        return (
            tokens > 0
            and price_rub > 0
            and price_rub * 100 >= tokens * MIN_PACKAGE_TOKEN_PRICE_KOPEKS
        )

    @asynccontextmanager
    async def connection(self):
        if not self._initialized:
            await self.initialize()

        task = asyncio.current_task()
        if task is not None and self._connection_owner is task:
            self._connection_depth += 1
            try:
                yield self._pool
            except Exception as e:
                await self._pool.rollback()
                logger.error(f"Ошибка вложенной транзакции: {e}")
                raise
            finally:
                self._connection_depth -= 1
            return

        await self._connection_lock.acquire()
        self._connection_owner = task
        self._connection_depth = 1
        try:
            yield self._pool
        except Exception as e:
            await self._pool.rollback()
            logger.error(f"Ошибка транзакции: {e}")
            raise
        finally:
            # Пойманная внутри метода ошибка не должна оставлять незавершённую
            # транзакцию, которая затем повлияет на другого пользователя.
            try:
                if self._pool.in_transaction:
                    await self._pool.rollback()
            finally:
                self._connection_owner = None
                self._connection_depth = 0
                self._connection_lock.release()

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False
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
        allow_free_trial: bool = False,
        use_supplied_cost: bool = False,
        provider_cost_rub: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Атомарно использует разрешённую бесплатную попытку или токены.

        ``allow_free_trial`` вычисляется биллингом по точному ключу модели.
        Поэтому бесплатный кредит раздела нельзя случайно потратить на
        дорогую модель того же типа.
        """
        if generation_kind not in {"text", "image", "video"}:
            raise ValueError("Некорректный тип генерации")
        column = f"{generation_kind}_left"
        async with self.connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                price_cursor = await conn.execute(
                    """SELECT token_cost, enabled, provider_cost_rub
                       FROM model_prices WHERE model_key = ?""",
                    (model_key,),
                )
                price_row = await price_cursor.fetchone()
                actual_cost = (
                    int(token_cost)
                    if use_supplied_cost
                    else int(price_row["token_cost"]) if price_row else int(token_cost)
                )
                if price_row and not bool(price_row["enabled"]):
                    raise ValueError("Модель временно отключена")
                if actual_cost <= 0:
                    raise ValueError("У модели настроена некорректная цена")
                actual_provider_cost = (
                    float(provider_cost_rub)
                    if provider_cost_rub is not None
                    else float(price_row["provider_cost_rub"])
                    if price_row and price_row["provider_cost_rub"] is not None
                    else None
                )
                self.assert_generation_price_safe(
                    model_key,
                    actual_cost,
                    provider_cost_rub=actual_provider_cost,
                )

                await conn.execute(
                    """
                    INSERT OR IGNORE INTO free_generation_credits
                    (user_id, text_left, image_left, video_left)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        settings.FREE_TEXT_GENERATIONS,
                        settings.FREE_IMAGE_GENERATIONS,
                        settings.FREE_VIDEO_GENERATIONS,
                    ),
                )

                if allow_free_trial:
                    cursor = await conn.execute(
                        f"SELECT {column} FROM free_generation_credits WHERE user_id = ?",
                        (user_id,),
                    )
                    row = await cursor.fetchone()
                    if row and row[column] > 0:
                        update = await conn.execute(
                            f"""
                            UPDATE free_generation_credits
                            SET {column} = {column} - 1,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = ? AND {column} > 0
                            """,
                            (user_id,),
                        )
                        if update.rowcount == 1:
                            await conn.execute(
                                """INSERT INTO token_transactions
                                   (user_id, amount, type, description)
                                   VALUES (?, 0, 'free_trial', ?)""",
                                (user_id, f"Бесплатная генерация: {model_key}"),
                            )
                            ledger = await conn.execute(
                                """INSERT INTO generation_economics
                                   (user_id, model_key, kind, charge_source,
                                    tokens_charged, revenue_rub, provider_cost_rub)
                                   VALUES (?, ?, ?, 'free_trial', 0, 0, ?)""",
                                (
                                    user_id,
                                    model_key,
                                    generation_kind,
                                    actual_provider_cost,
                                ),
                            )
                            await conn.commit()
                            return {
                                "source": "free_trial",
                                "amount": 0,
                                "balance": await self.get_user_tokens(user_id),
                                "ledger_id": int(ledger.lastrowid),
                                "provider_cost_rub": actual_provider_cost,
                            }

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
                    return {
                        "source": "insufficient",
                        "amount": actual_cost,
                        "balance": int(balance_row["tokens"] if balance_row else 0),
                    }

                await conn.execute(
                    """INSERT INTO token_transactions
                       (user_id, amount, type, description)
                       VALUES (?, ?, 'spend', ?)""",
                    (user_id, -actual_cost, f"Генерация: {model_key}"),
                )
                ledger = await conn.execute(
                    """INSERT INTO generation_economics
                       (user_id, model_key, kind, charge_source,
                        tokens_charged, revenue_rub, provider_cost_rub)
                       VALUES (?, ?, ?, 'tokens', ?, ?, ?)""",
                    (
                        user_id,
                        model_key,
                        generation_kind,
                        actual_cost,
                        actual_cost * settings.ECONOMY_TOKEN_VALUE_KOPEKS / 100.0,
                        actual_provider_cost,
                    ),
                )
                await conn.commit()
                return {
                    "source": "tokens",
                    "amount": actual_cost,
                    "balance": await self.get_user_tokens(user_id),
                    "ledger_id": int(ledger.lastrowid),
                    "provider_cost_rub": actual_provider_cost,
                }
            except Exception:
                await conn.rollback()
                raise

    async def create_admin_generation_ledger(
        self,
        user_id: int,
        generation_kind: str,
        model_key: str,
        provider_cost_rub: Optional[float],
    ) -> int:
        async with self.connection() as conn:
            cursor = await conn.execute(
                """INSERT INTO generation_economics
                   (user_id, model_key, kind, charge_source,
                    tokens_charged, revenue_rub, provider_cost_rub)
                   VALUES (?, ?, ?, 'admin', 0, 0, ?)""",
                (user_id, model_key, generation_kind, provider_cost_rub),
            )
            await conn.commit()
            return int(cursor.lastrowid)

    async def refund_generation(
        self,
        user_id: int,
        generation_kind: str,
        model_key: str,
        amount: int,
        source: str,
        reason: str,
        ledger_id: Optional[int] = None,
    ) -> bool:
        """Идемпотентно возвращает списание при ошибке провайдера."""
        column = f"{generation_kind}_left"
        async with self.connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                if ledger_id is not None:
                    updated = await conn.execute(
                        """UPDATE generation_economics
                           SET status='refunded', revenue_rub=0,
                               error_message=?, completed_at=CURRENT_TIMESTAMP
                           WHERE id=? AND status NOT IN ('completed','refunded')""",
                        (reason[:2000], ledger_id),
                    )
                    if updated.rowcount != 1:
                        await conn.commit()
                        return False
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
                return True
            except Exception:
                await conn.rollback()
                raise

    async def attach_generation_request(
        self,
        ledger_id: int,
        provider_request_id: Optional[str],
    ) -> None:
        async with self.connection() as conn:
            await conn.execute(
                """UPDATE generation_economics
                   SET status='processing', provider_request_id=?
                   WHERE id=? AND status='reserved'""",
                (provider_request_id, ledger_id),
            )
            await conn.commit()

    async def complete_generation(
        self,
        ledger_id: int,
        *,
        provider_cost_rub: Optional[float] = None,
        provider_request_id: Optional[str] = None,
    ) -> bool:
        async with self.connection() as conn:
            cursor = await conn.execute(
                """UPDATE generation_economics
                   SET status='completed',
                       provider_cost_rub=COALESCE(?, provider_cost_rub),
                       provider_request_id=COALESCE(?, provider_request_id),
                       completed_at=CURRENT_TIMESTAMP
                   WHERE id=? AND status NOT IN ('completed','refunded')""",
                (provider_cost_rub, provider_request_id, ledger_id),
            )
            await conn.commit()
            return cursor.rowcount == 1

    async def create_generation_job(
        self,
        *,
        user_id: int,
        chat_id: int,
        model_key: str,
        kind: str,
        provider_request_id: Optional[str],
        economic_id: int,
        token_cost: int,
        charge_source: str,
        caption: str,
        duration: Optional[int] = None,
        result_limit: int = 1,
        result_urls: Optional[List[str]] = None,
    ) -> int:
        status = "ready" if result_urls else "processing"
        async with self.connection() as conn:
            cursor = await conn.execute(
                """INSERT INTO generation_jobs
                   (user_id, chat_id, model_key, kind, provider_request_id,
                    economic_id, token_cost, charge_source, caption, duration,
                    result_limit, result_urls, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    chat_id,
                    model_key,
                    kind,
                    provider_request_id,
                    economic_id,
                    token_cost,
                    charge_source,
                    caption[:1000],
                    duration,
                    max(1, min(4, int(result_limit))),
                    json.dumps(result_urls, ensure_ascii=False) if result_urls else None,
                    status,
                ),
            )
            await conn.execute(
                """UPDATE generation_economics
                   SET status=?, provider_request_id=COALESCE(?, provider_request_id)
                   WHERE id=? AND status NOT IN ('completed','refunded')""",
                (
                    "completed" if result_urls else "processing",
                    provider_request_id,
                    economic_id,
                ),
            )
            if result_urls:
                await conn.execute(
                    """UPDATE generation_economics
                       SET completed_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (economic_id,),
                )
            await conn.commit()
            return int(cursor.lastrowid)

    async def get_generation_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        async with self.connection() as conn:
            row = await (await conn.execute(
                "SELECT * FROM generation_jobs WHERE id=?",
                (job_id,),
            )).fetchone()
        return dict(row) if row else None

    async def has_active_generation_job(self, user_id: int) -> bool:
        async with self.connection() as conn:
            row = await (await conn.execute(
                """SELECT 1 FROM generation_jobs
                   WHERE user_id=? AND status IN ('processing','ready')
                   LIMIT 1""",
                (user_id,),
            )).fetchone()
        return row is not None

    async def get_pending_generation_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        async with self.connection() as conn:
            rows = await (await conn.execute(
                """SELECT * FROM generation_jobs
                   WHERE status IN ('processing','ready')
                   ORDER BY updated_at, id LIMIT ?""",
                (max(1, min(50, int(limit))),),
            )).fetchall()
        return [dict(row) for row in rows]

    async def mark_generation_job_ready(
        self,
        job_id: int,
        result_urls: List[str],
        *,
        provider_cost_rub: Optional[float] = None,
    ) -> bool:
        if not result_urls:
            raise ValueError("Нельзя сохранить пустой результат генерации")
        async with self.connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                row = await (await conn.execute(
                    "SELECT economic_id FROM generation_jobs WHERE id=?",
                    (job_id,),
                )).fetchone()
                if not row:
                    await conn.rollback()
                    return False
                updated = await conn.execute(
                    """UPDATE generation_jobs
                       SET status='ready', result_urls=?, error_message=NULL,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE id=? AND status='processing'""",
                    (json.dumps(result_urls, ensure_ascii=False), job_id),
                )
                await conn.execute(
                    """UPDATE generation_economics
                       SET status='completed',
                           provider_cost_rub=COALESCE(?, provider_cost_rub),
                           completed_at=COALESCE(completed_at, CURRENT_TIMESTAMP)
                       WHERE id=? AND status!='refunded'""",
                    (provider_cost_rub, int(row["economic_id"])),
                )
                await conn.commit()
                return updated.rowcount == 1
            except Exception:
                await conn.rollback()
                raise

    async def mark_generation_job_delivered(self, job_id: int) -> bool:
        async with self.connection() as conn:
            cursor = await conn.execute(
                """UPDATE generation_jobs
                   SET status='completed', delivered_at=CURRENT_TIMESTAMP,
                       completed_at=CURRENT_TIMESTAMP,
                       updated_at=CURRENT_TIMESTAMP, error_message=NULL
                   WHERE id=? AND status='ready'""",
                (job_id,),
            )
            await conn.commit()
            return cursor.rowcount == 1

    async def record_generation_job_attempt(self, job_id: int, error: str) -> None:
        async with self.connection() as conn:
            await conn.execute(
                """UPDATE generation_jobs
                   SET attempts=attempts+1, error_message=?,
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND status IN ('processing','ready')""",
                (error[:2000], job_id),
            )
            await conn.commit()

    async def refund_generation_job(self, job_id: int, reason: str) -> bool:
        """Одной транзакцией закрывает задание и возвращает его списание."""
        async with self.connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                row = await (await conn.execute(
                    """SELECT user_id, model_key, kind, economic_id,
                              token_cost, charge_source, status
                       FROM generation_jobs WHERE id=?""",
                    (job_id,),
                )).fetchone()
                if not row or row["status"] not in {"processing", "ready"}:
                    await conn.commit()
                    return False
                ledger = await (await conn.execute(
                    "SELECT status FROM generation_economics WHERE id=?",
                    (int(row["economic_id"]),),
                )).fetchone()
                if ledger and ledger["status"] == "refunded":
                    await conn.execute(
                        """UPDATE generation_jobs
                           SET status='refunded', error_message=?,
                               completed_at=CURRENT_TIMESTAMP,
                               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                        (reason[:2000], job_id),
                    )
                    await conn.commit()
                    return False

                source = str(row["charge_source"])
                amount = int(row["token_cost"])
                user_id = int(row["user_id"])
                if source == "free_trial":
                    column = f"{row['kind']}_left"
                    if column not in {"text_left", "image_left", "video_left"}:
                        raise ValueError("Некорректный тип задания")
                    await conn.execute(
                        f"""UPDATE free_generation_credits
                            SET {column}={column}+1,
                                updated_at=CURRENT_TIMESTAMP
                            WHERE user_id=?""",
                        (user_id,),
                    )
                elif source == "tokens" and amount > 0:
                    await conn.execute(
                        "UPDATE users SET tokens=tokens+? WHERE telegram_id=?",
                        (amount, user_id),
                    )
                if source != "admin":
                    await conn.execute(
                        """INSERT INTO token_transactions
                           (user_id, amount, type, description)
                           VALUES (?, ?, 'refund', ?)""",
                        (
                            user_id,
                            amount,
                            f"{reason}: {row['model_key']}",
                        ),
                    )
                await conn.execute(
                    """UPDATE generation_economics
                       SET status='refunded', revenue_rub=0,
                           error_message=?, completed_at=CURRENT_TIMESTAMP
                       WHERE id=? AND status!='refunded'""",
                    (reason[:2000], int(row["economic_id"])),
                )
                await conn.execute(
                    """UPDATE generation_jobs
                       SET status='refunded', error_message=?,
                           completed_at=CURRENT_TIMESTAMP,
                           updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (reason[:2000], job_id),
                )
                await conn.commit()
                return True
            except Exception:
                await conn.rollback()
                raise

    async def get_free_credits(self, user_id: int) -> Dict[str, int]:
        async with self.connection() as conn:
            await conn.execute(
                """
                INSERT OR IGNORE INTO free_generation_credits
                (user_id, text_left, image_left, video_left)
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    settings.FREE_TEXT_GENERATIONS,
                    settings.FREE_IMAGE_GENERATIONS,
                    settings.FREE_VIDEO_GENERATIONS,
                ),
            )
            await conn.commit()
            cursor = await conn.execute(
                "SELECT text_left, image_left, video_left FROM free_generation_credits WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else {"text_left": 0, "image_left": 0, "video_left": 0}

    async def set_model_price(self, model_key: str, token_cost: int, enabled: bool = True) -> None:
        if token_cost <= 0:
            raise ValueError("Цена модели должна быть больше нуля")
        if enabled:
            self.assert_generation_price_safe(
                model_key,
                self.get_model_safety_price(model_key, token_cost),
            )
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
        self._model_enabled_cache[model_key] = bool(enabled)
        self._model_price_cache[model_key] = int(token_cost)

    async def set_model_enabled(self, model_key: str, enabled: bool) -> None:
        if enabled and self._model_price_cache.get(model_key, 0) <= 0:
            raise ValueError("Нельзя включить модель с нулевой ценой")
        if enabled:
            self.assert_generation_price_safe(
                model_key,
                self.get_model_safety_price(
                    model_key,
                    self._model_price_cache.get(model_key, 0),
                ),
            )
        async with self.connection() as conn:
            cursor = await conn.execute(
                "UPDATE model_prices SET enabled=?, updated_at=CURRENT_TIMESTAMP WHERE model_key=?",
                (int(enabled), model_key),
            )
            if cursor.rowcount != 1:
                raise ValueError("Модель отсутствует в model_prices")
            await conn.commit()
        self._model_enabled_cache[model_key] = bool(enabled)

    async def set_model_economics(
        self,
        model_key: str,
        *,
        provider_cost_rub: Optional[float] = None,
        min_margin_percent: Optional[float] = None,
    ) -> bool:
        """Обновляет себестоимость/маржу и отключает убыточную модель."""
        current_cost = self.get_model_provider_cost_cached(model_key)
        current_margin = self.get_model_margin_cached(model_key)
        new_cost = current_cost if provider_cost_rub is None else float(provider_cost_rub)
        new_margin = current_margin if min_margin_percent is None else float(min_margin_percent)
        if new_cost is None or new_cost <= 0:
            raise ValueError("Себестоимость должна быть больше нуля")
        if not 0 <= new_margin < 100:
            raise ValueError("Маржа должна быть от 0 до 99 процентов")

        async with self.connection() as conn:
            cursor = await conn.execute(
                """UPDATE model_prices
                   SET provider_cost_rub=?, min_margin_percent=?,
                       cost_source='manual', updated_at=CURRENT_TIMESTAMP
                   WHERE model_key=?""",
                (new_cost, new_margin, model_key),
            )
            if cursor.rowcount != 1:
                raise ValueError("Модель отсутствует в model_prices")
            await conn.commit()

        self._model_provider_cost_cache[model_key] = new_cost
        self._model_margin_cache[model_key] = new_margin
        self._model_cost_source_cache[model_key] = "manual"
        token_cost = self.get_model_safety_price(
            model_key,
            self._model_price_cache.get(model_key, 0),
        )
        safe = self.is_generation_price_safe(model_key, token_cost)
        if not safe and self._model_enabled_cache.get(model_key, True):
            await self.set_model_enabled(model_key, False)
        return safe

    async def get_model_settings(self, model_key: str) -> Optional[Dict[str, Any]]:
        async with self.connection() as conn:
            row = await (await conn.execute(
                """SELECT model_key, token_cost, enabled, provider_cost_rub,
                          min_margin_percent, cost_source, updated_at
                   FROM model_prices WHERE model_key=?""",
                (model_key,),
            )).fetchone()
        return dict(row) if row else None

    async def get_all_model_settings(self) -> List[Dict[str, Any]]:
        async with self.connection() as conn:
            rows = await (await conn.execute(
                """SELECT model_key, token_cost, enabled, provider_cost_rub,
                          min_margin_percent, cost_source, updated_at
                   FROM model_prices ORDER BY model_key"""
            )).fetchall()
        return [dict(row) for row in rows]

    async def update_token_package(
        self,
        package_key: str,
        *,
        tokens: Optional[int] = None,
        price_rub: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        current = self.get_token_package_cached(package_key)
        if not current:
            raise ValueError("Пакет не найден")
        new_tokens = int(tokens if tokens is not None else current["tokens"])
        new_price = int(price_rub if price_rub is not None else current["price_rub"])
        new_enabled = bool(enabled if enabled is not None else current["enabled"])
        if new_tokens <= 0 or new_price <= 0:
            raise ValueError("Токены и цена должны быть больше нуля")
        from model_catalog import MIN_PACKAGE_TOKEN_PRICE_KOPEKS

        if (
            new_enabled
            and new_price * 100 < new_tokens * MIN_PACKAGE_TOKEN_PRICE_KOPEKS
        ):
            minimum_price = (
                new_tokens * MIN_PACKAGE_TOKEN_PRICE_KOPEKS + 99
            ) // 100
            raise ValueError(
                "Цена пакета ниже защитного порога экономики. "
                f"Для {new_tokens} токенов минимум {minimum_price} ₽."
            )
        async with self.connection() as conn:
            await conn.execute(
                """UPDATE token_packages
                   SET tokens=?, price_rub=?, enabled=?, updated_at=CURRENT_TIMESTAMP
                   WHERE package_key=?""",
                (new_tokens, new_price, int(new_enabled), package_key),
            )
            await conn.commit()
        current.update(tokens=new_tokens, price_rub=new_price, enabled=int(new_enabled))
        self._package_cache[package_key] = current

    async def admin_adjust_tokens(self, user_id: int, delta: int, description: str) -> int:
        if delta == 0:
            raise ValueError("Изменение баланса не может быть нулевым")
        async with self.connection() as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                row = await (await conn.execute(
                    "SELECT tokens FROM users WHERE telegram_id=?", (user_id,)
                )).fetchone()
                if not row:
                    await conn.rollback()
                    raise ValueError("Пользователь не найден")
                current = int(row["tokens"])
                new_balance = current + int(delta)
                if new_balance < 0:
                    await conn.rollback()
                    raise ValueError(f"Недостаточно токенов: баланс {current} 💎")
                await conn.execute(
                    "UPDATE users SET tokens=? WHERE telegram_id=?",
                    (new_balance, user_id),
                )
                await conn.execute(
                    """INSERT INTO token_transactions
                       (user_id, amount, type, description)
                       VALUES (?, ?, 'admin_adjustment', ?)""",
                    (user_id, int(delta), description[:1000]),
                )
                await conn.commit()
                return new_balance
            except Exception:
                await conn.rollback()
                raise

    async def set_free_credits(
        self,
        user_id: int,
        *,
        text_left: int,
        image_left: int,
        video_left: int,
    ) -> None:
        values = [max(0, int(text_left)), max(0, int(image_left)), max(0, int(video_left))]
        async with self.connection() as conn:
            await conn.execute(
                """INSERT INTO free_generation_credits
                   (user_id, text_left, image_left, video_left, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(user_id) DO UPDATE SET
                     text_left=excluded.text_left,
                     image_left=excluded.image_left,
                     video_left=excluded.video_left,
                     updated_at=CURRENT_TIMESTAMP""",
                (user_id, *values),
            )
            await conn.commit()

    async def is_user_blocked(self, user_id: int) -> bool:
        async with self.connection() as conn:
            row = await (await conn.execute(
                "SELECT is_blocked FROM users WHERE telegram_id=?", (user_id,)
            )).fetchone()
        return bool(row and row["is_blocked"])

    async def set_user_blocked(self, user_id: int, blocked: bool, reason: str = "") -> None:
        async with self.connection() as conn:
            await conn.execute(
                """UPDATE users SET
                     is_blocked=?,
                     blocked_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END,
                     blocked_reason=CASE WHEN ? THEN ? ELSE NULL END
                   WHERE telegram_id=?""",
                (int(blocked), int(blocked), int(blocked), reason or None, user_id),
            )
            await conn.commit()

    async def log_admin_action(
        self,
        admin_id: int,
        action: str,
        *,
        target_user_id: Optional[int] = None,
        details: str = "",
    ) -> None:
        async with self.connection() as conn:
            await conn.execute(
                """INSERT INTO admin_audit_log (admin_id, action, target_user_id, details)
                   VALUES (?, ?, ?, ?)""",
                (admin_id, action, target_user_id, details[:2000]),
            )
            await conn.commit()

    async def get_admin_audit(self, limit: int = 30) -> List[Dict[str, Any]]:
        async with self.connection() as conn:
            rows = await (await conn.execute(
                """SELECT id, admin_id, action, target_user_id, details, created_at
                   FROM admin_audit_log ORDER BY id DESC LIMIT ?""",
                (limit,),
            )).fetchall()
        return [dict(row) for row in rows]

    async def search_users(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        value = query.strip().lstrip("@")
        async with self.connection() as conn:
            if value.isdigit():
                rows = await (await conn.execute(
                    "SELECT * FROM users WHERE telegram_id=? LIMIT ?",
                    (int(value), limit),
                )).fetchall()
            else:
                pattern = f"%{value}%"
                rows = await (await conn.execute(
                    """SELECT * FROM users
                       WHERE username LIKE ? COLLATE NOCASE OR first_name LIKE ? COLLATE NOCASE
                       ORDER BY last_activity DESC, id DESC LIMIT ?""",
                    (pattern, pattern, limit),
                )).fetchall()
        return [dict(row) for row in rows]

    async def get_recent_users(self, limit: int = 20) -> List[Dict[str, Any]]:
        async with self.connection() as conn:
            rows = await (await conn.execute(
                "SELECT * FROM users ORDER BY id DESC LIMIT ?", (limit,)
            )).fetchall()
        return [dict(row) for row in rows]

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
                    INSERT INTO users (telegram_id, username, first_name, tokens)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(telegram_id) DO UPDATE SET
                        username=COALESCE(excluded.username, users.username),
                        first_name=COALESCE(excluded.first_name, users.first_name)
                    """,
                    (user_id, username, first_name, 0)
                )
                await conn.execute(
                    """
                    INSERT OR IGNORE INTO free_generation_credits
                    (user_id, text_left, image_left, video_left)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        settings.FREE_TEXT_GENERATIONS,
                        settings.FREE_IMAGE_GENERATIONS,
                        settings.FREE_VIDEO_GENERATIONS,
                    ),
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
            {"version": 2, "columns": ["schema_version", "response_type"]},
            {
                "version": 3,
                # Обновляем только неизменённые старые пакеты. Если администратор
                # уже правил цену или число токенов, его настройки сохраняются.
                "package_prices": {
                    "start": {"tokens": 500, "old_price": 199, "new_price": 249},
                    "popular": {"tokens": 1500, "old_price": 499, "new_price": 599},
                    "pro": {"tokens": 4000, "old_price": 999, "new_price": 1390},
                    "max": {"tokens": 10000, "old_price": 1999, "new_price": 3290},
                },
            },
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
                for column in mig.get("columns", []):
                    if not await self._apply_column_migration("requests", column):
                        return False
                try:
                    async with db_manager.connection() as conn:
                        if mig.get("package_prices"):
                            await conn.execute("BEGIN IMMEDIATE")
                            for package_key, change in mig["package_prices"].items():
                                await conn.execute(
                                    """UPDATE token_packages
                                       SET price_rub=?, updated_at=CURRENT_TIMESTAMP
                                       WHERE package_key=? AND tokens=? AND price_rub=?""",
                                    (
                                        int(change["new_price"]),
                                        package_key,
                                        int(change["tokens"]),
                                        int(change["old_price"]),
                                    ),
                                )
                        await conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
                        await conn.commit()
                    if mig.get("package_prices"):
                        await db_manager.refresh_runtime_caches()
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
