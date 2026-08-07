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


def _get_float(name: str, default: float) -> float:
    """Безопасно читает дробное число из переменных окружения."""
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        return float(raw_value.replace(",", "."))
    except ValueError as exc:
        raise RuntimeError(
            f"Переменная окружения {name} должна быть числом, "
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
    PAYMENT_RECONCILE_INTERVAL_SECONDS = _get_int(
        "PAYMENT_RECONCILE_INTERVAL_SECONDS",
        60,
    )
    PAYMENT_RECONCILE_BATCH_SIZE = _get_int(
        "PAYMENT_RECONCILE_BATCH_SIZE",
        25,
    )
    YOOKASSA_WEBHOOK_PATH = os.getenv(
        "YOOKASSA_WEBHOOK_PATH",
        "/webhooks/yookassa",
    ).strip()

    # База данных
    DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "ai_shtab.db"))

    # Экономика. TOKEN_VALUE_KOPEKS — консервативная стоимость одного
    # внутреннего токена: берём минимальную цену среди активных пакетов.
    ECONOMY_TOKEN_VALUE_KOPEKS = _get_int("ECONOMY_TOKEN_VALUE_KOPEKS", 32)
    ECONOMY_MIN_MARGIN_PERCENT = _get_float("ECONOMY_MIN_MARGIN_PERCENT", 30.0)
    ECONOMY_RESERVE_PERCENT = _get_float("ECONOMY_RESERVE_PERCENT", 10.0)
    ECONOMY_REQUIRE_KNOWN_COST = _get_bool("ECONOMY_REQUIRE_KNOWN_COST", True)

    # Восстановление асинхронных генераций после рестарта.
    GENERATION_RECOVERY_INTERVAL_SECONDS = _get_int(
        "GENERATION_RECOVERY_INTERVAL_SECONDS",
        30,
    )
    GENERATION_RECOVERY_BATCH_SIZE = _get_int(
        "GENERATION_RECOVERY_BATCH_SIZE",
        10,
    )
    GENERATION_MAX_PENDING_HOURS = _get_int("GENERATION_MAX_PENDING_HOURS", 24)

    # Резервные копии и технические уведомления.
    BACKUP_ENABLED = _get_bool("BACKUP_ENABLED", True)
    BACKUP_INTERVAL_SECONDS = _get_int("BACKUP_INTERVAL_SECONDS", 21600)
    BACKUP_KEEP_COUNT = _get_int("BACKUP_KEEP_COUNT", 14)
    BACKUP_DIR = os.getenv("BACKUP_DIR", str(BASE_DIR / "backups")).strip()
    MONITOR_INTERVAL_SECONDS = _get_int("MONITOR_INTERVAL_SECONDS", 60)
    ALERT_ERROR_RATE_PERCENT = _get_float("ALERT_ERROR_RATE_PERCENT", 25.0)
    ALERT_MIN_GENERATIONS = _get_int("ALERT_MIN_GENERATIONS", 5)
    ALERT_DISK_FREE_MB = _get_int("ALERT_DISK_FREE_MB", 500)
    ALERT_THROTTLE_SECONDS = _get_int("ALERT_THROTTLE_SECONDS", 1800)

    # Постоянные состояния диалогов и защита от спама.
    FSM_STATE_TTL_DAYS = _get_int("FSM_STATE_TTL_DAYS", 7)
    RATE_LIMIT_MESSAGES_PER_MINUTE = _get_int(
        "RATE_LIMIT_MESSAGES_PER_MINUTE",
        30,
    )
    RATE_LIMIT_CALLBACKS_PER_MINUTE = _get_int(
        "RATE_LIMIT_CALLBACKS_PER_MINUTE",
        60,
    )

    # Автоматический предохранитель проблемных моделей.
    MODEL_CIRCUIT_BREAKER_ENABLED = _get_bool(
        "MODEL_CIRCUIT_BREAKER_ENABLED",
        True,
    )
    MODEL_CIRCUIT_WINDOW_MINUTES = _get_int(
        "MODEL_CIRCUIT_WINDOW_MINUTES",
        15,
    )
    MODEL_CIRCUIT_MIN_ATTEMPTS = _get_int(
        "MODEL_CIRCUIT_MIN_ATTEMPTS",
        5,
    )
    MODEL_CIRCUIT_FAILURE_PERCENT = _get_float(
        "MODEL_CIRCUIT_FAILURE_PERCENT",
        50.0,
    )
    MODEL_CIRCUIT_COOLDOWN_MINUTES = _get_int(
        "MODEL_CIRCUIT_COOLDOWN_MINUTES",
        30,
    )

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
        required = {
            "BOT_TOKEN": self.BOT_TOKEN,
            "GENAPI_API_KEY": self.GENAPI_API_KEY,
            "YOOKASSA_SHOP_ID": self.YOOKASSA_SHOP_ID,
            "YOOKASSA_SECRET_KEY": self.YOOKASSA_SECRET_KEY,
            "YOOKASSA_RETURN_URL": self.YOOKASSA_RETURN_URL,
        }
        missing = [
            name
            for name, value in required.items()
            if not value or value.lower().startswith("ваш_")
        ]

        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(
                f"Не заданы обязательные переменные окружения: {joined}. "
                f"Проверь файл {ENV_PATH}."
            )

        if not self.YOOKASSA_SHOP_ID.isdigit():
            raise RuntimeError("YOOKASSA_SHOP_ID должен состоять только из цифр")
        if not self.YOOKASSA_RETURN_URL.startswith(("https://", "http://")):
            raise RuntimeError("YOOKASSA_RETURN_URL должен быть корректным URL")
        if not self.YOOKASSA_WEBHOOK_PATH.startswith("/"):
            raise RuntimeError("YOOKASSA_WEBHOOK_PATH должен начинаться с /")
        if self.ECONOMY_TOKEN_VALUE_KOPEKS <= 0:
            raise RuntimeError("ECONOMY_TOKEN_VALUE_KOPEKS должен быть больше нуля")
        if not 0 <= self.ECONOMY_MIN_MARGIN_PERCENT < 100:
            raise RuntimeError("ECONOMY_MIN_MARGIN_PERCENT должен быть от 0 до 99")
        if self.ECONOMY_RESERVE_PERCENT < 0:
            raise RuntimeError("ECONOMY_RESERVE_PERCENT не может быть отрицательным")
        if self.RATE_LIMIT_MESSAGES_PER_MINUTE <= 0:
            raise RuntimeError("RATE_LIMIT_MESSAGES_PER_MINUTE должен быть больше нуля")
        if self.RATE_LIMIT_CALLBACKS_PER_MINUTE <= 0:
            raise RuntimeError("RATE_LIMIT_CALLBACKS_PER_MINUTE должен быть больше нуля")
        if self.FSM_STATE_TTL_DAYS <= 0:
            raise RuntimeError("FSM_STATE_TTL_DAYS должен быть больше нуля")
        if self.MODEL_CIRCUIT_WINDOW_MINUTES <= 0:
            raise RuntimeError("MODEL_CIRCUIT_WINDOW_MINUTES должен быть больше нуля")
        if self.MODEL_CIRCUIT_MIN_ATTEMPTS <= 0:
            raise RuntimeError("MODEL_CIRCUIT_MIN_ATTEMPTS должен быть больше нуля")
        if self.MODEL_CIRCUIT_COOLDOWN_MINUTES <= 0:
            raise RuntimeError("MODEL_CIRCUIT_COOLDOWN_MINUTES должен быть больше нуля")
        if not 0 < self.MODEL_CIRCUIT_FAILURE_PERCENT <= 100:
            raise RuntimeError("MODEL_CIRCUIT_FAILURE_PERCENT должен быть от 1 до 100")

        from model_catalog import GenerationKind, get_model

        free_models = (
            ("FREE_TEXT_MODEL", self.FREE_TEXT_MODEL, GenerationKind.TEXT),
            ("FREE_IMAGE_MODEL", self.FREE_IMAGE_MODEL, GenerationKind.IMAGE),
            ("FREE_VIDEO_MODEL", self.FREE_VIDEO_MODEL, GenerationKind.VIDEO),
        )
        for setting_name, model_key, expected_kind in free_models:
            try:
                model = get_model(model_key)
            except ValueError as exc:
                raise RuntimeError(f"{setting_name}: {exc}") from exc
            if model.kind != expected_kind:
                raise RuntimeError(
                    f"{setting_name} должен указывать модель типа {expected_kind.value}"
                )

        free_limits = (
            self.FREE_TEXT_GENERATIONS,
            self.FREE_IMAGE_GENERATIONS,
            self.FREE_VIDEO_GENERATIONS,
        )
        if any(value < 0 for value in free_limits):
            raise RuntimeError("Количество бесплатных генераций не может быть отрицательным")


settings = Settings()
