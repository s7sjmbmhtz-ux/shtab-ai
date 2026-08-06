"""Настройки приложения ШТАБ AI.

Все секреты и изменяемые параметры читаются из файла .env,
расположенного рядом с этим модулем.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def _get_int(name: str, default: int) -> int:
    """Безопасно читает целое число из переменных окружения."""
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            f"Переменная окружения {name} должна быть целым числом, "
            f"получено: {raw_value!r}"
        ) from exc



def _get_int_set(name: str) -> frozenset[int]:
    """Читает список Telegram ID через запятую или пробел."""
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return frozenset()
    normalized = raw_value.replace(";", ",").replace(" ", ",")
    result: set[int] = set()
    for part in normalized.split(","):
        value = part.strip()
        if not value:
            continue
        try:
            result.add(int(value))
        except ValueError as exc:
            raise RuntimeError(
                f"Переменная окружения {name} должна содержать Telegram ID, "
                f"получено: {value!r}"
            ) from exc
    return frozenset(result)


def _get_bool(name: str, default: bool) -> bool:
    """Читает логическое значение из .env."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on", "да"}:
        return True
    if normalized in {"0", "false", "no", "off", "нет"}:
        return False

    raise RuntimeError(
        f"Переменная окружения {name} должна быть true/false, "
        f"получено: {raw_value!r}"
    )


def _normalize_public_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        return ""
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value


class Settings:
    """Единый объект конфигурации приложения."""

    # Telegram
    BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
    BOT_USERNAME = os.getenv("BOT_USERNAME", "@ShtabProBot").strip()
    ADMIN_TELEGRAM_ID = _get_int("ADMIN_TELEGRAM_ID", 548576688)
    ADMIN_IDS = _get_int_set("ADMIN_IDS") or frozenset({ADMIN_TELEGRAM_ID})

    # GenAPI
    GENAPI_API_KEY = os.getenv("GENAPI_API_KEY", "").strip()
    GENAPI_BASE_URL = os.getenv(
        "GENAPI_BASE_URL",
        "https://api.gen-api.ru",
    ).rstrip("/")
    GENAPI_PROXY_URL = os.getenv(
        "GENAPI_PROXY_URL",
        "https://proxy.gen-api.ru",
    ).rstrip("/")

    # Публичная раздача временных входных фото для моделей, которые
    # принимают только массив URL (image_urls/images). BotHost заполняет
    # DOMAIN после включения опции «Использовать домен».
    PORT = _get_int("PORT", 3000)
    DOMAIN = os.getenv("DOMAIN", "").strip()
    MEDIA_PUBLIC_BASE_URL = _normalize_public_url(
        os.getenv("MEDIA_PUBLIC_BASE_URL", "").strip() or DOMAIN
    )
    MEDIA_URL_TTL_SECONDS = _get_int("MEDIA_URL_TTL_SECONDS", 1800)

    # Сеть и повторные попытки
    AI_TIMEOUT = _get_int("AI_TIMEOUT", 300)
    AI_MAX_RETRIES = _get_int("AI_MAX_RETRIES", 3)
    GENAPI_POLL_INTERVAL = _get_int("GENAPI_POLL_INTERVAL", 5)
    GENAPI_POLL_TIMEOUT = _get_int("GENAPI_POLL_TIMEOUT", 900)

    # ЮKassa
    YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "").strip()
    YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "").strip()
    YOOKASSA_RETURN_URL = os.getenv(
        "YOOKASSA_RETURN_URL",
        f"https://t.me/{BOT_USERNAME.lstrip('@')}",
    ).strip()
    YOOKASSA_API_URL = os.getenv(
        "YOOKASSA_API_URL",
        "https://api.yookassa.ru/v3",
    ).rstrip("/")

    # База данных
    DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "ai_shtab.db"))

    # Бесплатные попытки нового пользователя
    FREE_TEXT_GENERATIONS = _get_int("FREE_TEXT_GENERATIONS", 1)
    FREE_IMAGE_GENERATIONS = _get_int("FREE_IMAGE_GENERATIONS", 1)
    FREE_VIDEO_GENERATIONS = _get_int("FREE_VIDEO_GENERATIONS", 1)

    # Модели, которые используются для бесплатных попыток
    FREE_TEXT_MODEL = os.getenv(
        "FREE_TEXT_MODEL",
        "deepseek-v4-flash",
    ).strip()
    FREE_IMAGE_MODEL = os.getenv(
        "FREE_IMAGE_MODEL",
        "flux-schnell",
    ).strip()
    FREE_VIDEO_MODEL = os.getenv(
        "FREE_VIDEO_MODEL",
        "cogvideox-5b",
    ).strip()

    # Значения оставлены для совместимости со старым кодом.
    LITE_TEXT_MODEL = os.getenv("LITE_TEXT_MODEL", "gpt-5.4-mini").strip()
    PRO_TEXT_MODEL = os.getenv("PRO_TEXT_MODEL", "deepseek-v4-pro").strip()
    BUSINESS_TEXT_MODEL = os.getenv("BUSINESS_TEXT_MODEL", "gpt-5-5").strip()

    LITE_IMAGE_MODEL = os.getenv("LITE_IMAGE_MODEL", "flux-dev").strip()
    PRO_IMAGE_MODEL = os.getenv("PRO_IMAGE_MODEL", "flux-pro").strip()
    BUSINESS_IMAGE_MODEL = os.getenv("BUSINESS_IMAGE_MODEL", "flux-pro").strip()

    LITE_VIDEO_MODEL = os.getenv("LITE_VIDEO_MODEL", "ltx-2-3").strip()
    PRO_VIDEO_MODEL = os.getenv("PRO_VIDEO_MODEL", "veo-3-1-lite").strip()
    BUSINESS_VIDEO_MODEL = os.getenv("BUSINESS_VIDEO_MODEL", "veo-3-1").strip()

    # Старые лимиты пока сохранены, чтобы промежуточное обновление проекта
    # не ломало существующие модули подписок до их замены.
    FREE_TEXT_LIMIT = _get_int("FREE_TEXT_LIMIT", 1)
    FREE_IMAGE_LIMIT = _get_int("FREE_IMAGE_LIMIT", 1)
    LITE_TEXT_LIMIT = _get_int("LITE_TEXT_LIMIT", 20)
    LITE_IMAGE_LIMIT = _get_int("LITE_IMAGE_LIMIT", 5)
    PRO_TEXT_LIMIT = _get_int("PRO_TEXT_LIMIT", 100)
    PRO_IMAGE_LIMIT = _get_int("PRO_IMAGE_LIMIT", 20)
    BUSINESS_TEXT_LIMIT = _get_int("BUSINESS_TEXT_LIMIT", 500)
    BUSINESS_IMAGE_LIMIT = _get_int("BUSINESS_IMAGE_LIMIT", 100)

    # Медиа
    MAX_AUDIO_DURATION_SEC = _get_int("MAX_AUDIO_DURATION_SEC", 300)
    MAX_AUDIO_SIZE_MB = _get_int("MAX_AUDIO_SIZE_MB", 20)
    MAX_IMAGE_SIZE_MB = _get_int("MAX_IMAGE_SIZE_MB", 20)
    MAX_VIDEO_SIZE_MB = _get_int("MAX_VIDEO_SIZE_MB", 50)

    # Поведение приложения
    ENABLE_SAFETY_CHECKER = _get_bool("ENABLE_SAFETY_CHECKER", True)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper().strip()

    @property
    def admin_telegram_id(self) -> int:
        return self.ADMIN_TELEGRAM_ID

    def is_admin(self, user_id: int) -> bool:
        return int(user_id) in self.ADMIN_IDS

    @property
    def db_path(self) -> str:
        return self.DB_PATH

    # Совместимость с utils.py из исходного проекта.
    @property
    def max_audio_duration_sec(self) -> int:
        return self.MAX_AUDIO_DURATION_SEC

    @property
    def max_audio_size_mb(self) -> int:
        return self.MAX_AUDIO_SIZE_MB

    @property
    def TOKEN_PACKAGES(self) -> dict:
        """Возвращает пакеты внутренних токенов из каталога моделей."""
        from model_catalog import TOKEN_PACKAGES

        return TOKEN_PACKAGES

    def validate(self) -> None:
        """Проверяет обязательные настройки перед запуском бота."""
        missing: list[str] = []

        if not self.BOT_TOKEN:
            missing.append("BOT_TOKEN")
        if not self.GENAPI_API_KEY:
            missing.append("GENAPI_API_KEY")

        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(
                f"Не заданы обязательные переменные окружения: {joined}. "
                f"Проверь файл {ENV_PATH}."
            )


settings = Settings()
