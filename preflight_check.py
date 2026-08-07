"""Предварительная проверка проекта перед запуском Telegram-бота."""
from __future__ import annotations

import asyncio
import importlib
import os
import platform
import re
import sqlite3
import sys
from pathlib import Path

REQUIRED_MODULES = (
    "aiogram",
    "httpx",
    "dotenv",
    "pydantic",
    "aiosqlite",
)

REQUIRED_ENV = (
    "BOT_TOKEN",
    "GENAPI_API_KEY",
    "YOOKASSA_SHOP_ID",
    "YOOKASSA_SECRET_KEY",
    "YOOKASSA_RETURN_URL",
)

REQUIRED_PROJECT_FILES = (
    "app.py",
    "settings.py",
    "database.py",
    "model_catalog.py",
    "generation_handlers.py",
    "generation_keyboards.py",
    "generation_states.py",
    "model_descriptions.py",
    "video_options.py",
    "business_handlers.py",
    "business_keyboards.py",
    "business_states.py",
    "payment_handlers.py",
    "token_admin_handlers.py",
    "admin_handlers.py",
    "admin_keyboards.py",
    "admin_states.py",
    "access_middleware.py",
    "history_handlers.py",
    "support_handlers.py",
    "support_states.py",
    "services/genapi_client.py",
    "services/generation_service.py",
    "services/generation_guard.py",
    "services/generation_jobs.py",
    "services/billing_service.py",
    "services/payment_service.py",
    "services/operations_service.py",
    "services/fsm_storage.py",
    "services/funnel_service.py",
    "services/media_storage.py",
    "services/public_media_service.py",
)


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def check_python() -> bool:
    version = sys.version_info
    if version < (3, 11):
        fail(f"Нужен Python 3.11+, установлен {platform.python_version()}")
        return False
    ok(f"Python {platform.python_version()}")
    return True


def check_files(base_dir: Path) -> bool:
    success = True
    for relative_path in REQUIRED_PROJECT_FILES:
        path = base_dir / relative_path
        if not path.is_file():
            fail(f"Нет файла: {relative_path}")
            success = False
    if success:
        ok("Все обязательные файлы проекта найдены")
    return success


def check_modules() -> bool:
    success = True
    for module_name in REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            fail(f"Не импортируется {module_name}: {exc}")
            success = False
    if success:
        ok("Все Python-зависимости импортируются")
    return success


def check_source_secrets(base_dir: Path) -> bool:
    """Не допускает случайно встроенные API-ключи в Python-файлах."""
    patterns = (
        re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
        re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"),
    )
    matches: list[str] = []
    for path in base_dir.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, 1):
            if any(pattern.search(line) for pattern in patterns):
                matches.append(f"{path.relative_to(base_dir)}:{line_number}")

    if matches:
        fail("В исходниках найдены похожие на секреты значения: " + ", ".join(matches))
        return False
    ok("В Python-исходниках нет встроенных API-ключей")
    return True


def check_economics() -> bool:
    from model_catalog import MIN_PACKAGE_TOKEN_PRICE_KOPEKS, TOKEN_PACKAGES
    from settings import settings
    from video_options import _tokens_from_rubles

    packages = sorted(TOKEN_PACKAGES.values(), key=lambda item: int(item["tokens"]))
    for package in packages:
        tokens = int(package["tokens"])
        price = int(package["price_rub"])
        if tokens <= 0 or price <= 0:
            fail("Пакеты токенов должны иметь положительные цену и объём")
            return False
        if price * 100 < tokens * MIN_PACKAGE_TOKEN_PRICE_KOPEKS:
            fail(f"Пакет {package['title']} ниже защитного порога экономики")
            return False

    unit_prices = [item["price_rub"] / item["tokens"] for item in packages]
    if any(left < right for left, right in zip(unit_prices, unit_prices[1:])):
        fail("Цена токена должна снижаться только в более крупных пакетах")
        return False
    if _tokens_from_rubles(100) < 600:
        fail("Коэффициент видео ниже согласованного значения ×6")
        return False
    if settings.ECONOMY_TOKEN_VALUE_KOPEKS > MIN_PACKAGE_TOKEN_PRICE_KOPEKS:
        fail("Расчётная стоимость токена выше защитного минимума пакетов")
        return False
    if not 0 <= settings.ECONOMY_MIN_MARGIN_PERCENT < 100:
        fail("Минимальная маржа должна быть от 0 до 99 процентов")
        return False
    if settings.ECONOMY_RESERVE_PERCENT < 0:
        fail("Резерв экономики не может быть отрицательным")
        return False
    ok("Защитные ограничения экономики соблюдены")
    return True


def mask(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def check_environment(base_dir: Path) -> bool:
    from dotenv import load_dotenv

    env_path = base_dir / ".env"
    if not env_path.is_file():
        fail("Нет файла .env в корне проекта")
        return False

    load_dotenv(env_path, override=False)
    success = True
    for name in REQUIRED_ENV:
        value = os.getenv(name, "").strip()
        if not value or value.startswith("ВАШ_") or value.startswith("ваш_"):
            fail(f"Не заполнена переменная {name}")
            success = False
        else:
            ok(f"{name}={mask(value)}")

    shop_id = os.getenv("YOOKASSA_SHOP_ID", "").strip()
    if shop_id and not shop_id.isdigit():
        fail("YOOKASSA_SHOP_ID должен состоять только из цифр")
        success = False

    return_url = os.getenv("YOOKASSA_RETURN_URL", "").strip()
    if return_url and not return_url.startswith(("https://", "http://")):
        fail("YOOKASSA_RETURN_URL должен быть URL")
        success = False

    return success


def check_database_path(base_dir: Path) -> bool:
    from dotenv import load_dotenv

    load_dotenv(base_dir / ".env", override=False)
    raw_path = os.getenv("DB_PATH", "ai_shtab.db").strip()
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = base_dir / db_path

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.close()
        ok(f"База доступна для записи: {db_path}")
        return True
    except Exception as exc:
        fail(f"Нельзя открыть БД {db_path}: {exc}")
        return False


async def check_application_imports() -> bool:
    try:
        from settings import settings
        settings.validate()
        import app  # noqa: F401
        import generation_handlers  # noqa: F401
        import payment_handlers  # noqa: F401
        import admin_handlers  # noqa: F401
        import history_handlers  # noqa: F401
        import support_handlers  # noqa: F401
        ok("Основные модули проекта импортируются")
        return True
    except Exception as exc:
        fail(f"Ошибка импорта проекта: {type(exc).__name__}: {exc}")
        return False


async def check_database_schema() -> bool:
    try:
        from database import db_manager, run_migrations

        await db_manager.initialize()
        migrated = await run_migrations()
        if migrated is False:
            fail("Миграции БД вернули ошибку")
            return False

        required_tables = {
            "users",
            "token_transactions",
            "free_generation_credits",
            "model_prices",
            "payments",
            "admin_audit_log",
            "admin_broadcasts",
            "token_packages",
            "fsm_storage",
            "rate_limit_counters",
            "generation_history",
            "funnel_events",
            "model_health_events",
            "support_tickets",
            "support_messages",
        }
        async with db_manager.connection() as conn:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            existing = {row[0] for row in await cursor.fetchall()}

        missing = required_tables - existing
        if missing:
            fail("В БД не созданы таблицы: " + ", ".join(sorted(missing)))
            return False

        ok("Схема и миграции БД готовы")
        return True
    except Exception as exc:
        fail(f"Ошибка проверки БД: {type(exc).__name__}: {exc}")
        return False
    finally:
        try:
            from database import db_manager
            await db_manager.close()
        except Exception:
            pass


async def main() -> int:
    base_dir = Path(__file__).resolve().parent
    print("=== ШТАБ AI: предварительная проверка ===")

    checks = [
        check_python(),
        check_files(base_dir),
        check_modules(),
        check_source_secrets(base_dir),
        check_economics(),
        check_environment(base_dir),
        check_database_path(base_dir),
        await check_application_imports(),
        await check_database_schema(),
    ]

    print("========================================")
    if all(checks):
        ok("Проект готов к первому запуску: python app.py")
        return 0

    fail("Исправьте ошибки выше и запустите проверку повторно")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
