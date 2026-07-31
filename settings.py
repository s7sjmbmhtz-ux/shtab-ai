import os
import json
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ============================================================
    # TELEGRAM
    # ============================================================
    BOT_TOKEN = os.getenv("BOT_TOKEN", "ваш_токен_бота")
    BOT_USERNAME = os.getenv("BOT_USERNAME", "@ShtabProBot")

    # ============================================================
    # AI PROVIDER — GENAPI
    # ============================================================
    GENAPI_API_KEY = os.getenv("GENAPI_API_KEY", "")
    GENAPI_BASE_URL = os.getenv("GENAPI_BASE_URL", "https://api.gen-api.ru")

    # ============================================================
    # ADMIN
    # ============================================================
    ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "548576688"))

    @property
    def admin_telegram_id(self):
        return self.ADMIN_TELEGRAM_ID

    # ============================================================
    # DATABASE
    # ============================================================
    DB_PATH = os.getenv("DB_PATH", "ai_shtab.db")

    @property
    def db_path(self):
        return self.DB_PATH

    # ============================================================
    # AI SERVICE
    # ============================================================
    AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))
    AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))

    # ============================================================
    # MODELS — ТЕКСТ (GenAPI)
    # ============================================================
    FREE_TEXT_MODEL = os.getenv("FREE_TEXT_MODEL", "deepseek-v4-flash")
    LITE_TEXT_MODEL = os.getenv("LITE_TEXT_MODEL", "deepseek-v4-pro")
    PRO_TEXT_MODEL = os.getenv("PRO_TEXT_MODEL", "gpt-5.4-mini")
    BUSINESS_TEXT_MODEL = os.getenv("BUSINESS_TEXT_MODEL", "gpt-5.5")

    # ============================================================
    # MODELS — ИЗОБРАЖЕНИЯ (GenAPI)
    # ============================================================
    FREE_IMAGE_MODEL = os.getenv("FREE_IMAGE_MODEL", "flux-schnell")
    LITE_IMAGE_MODEL = os.getenv("LITE_IMAGE_MODEL", "flux-dev")
    PRO_IMAGE_MODEL = os.getenv("PRO_IMAGE_MODEL", "flux-pro")
    BUSINESS_IMAGE_MODEL = os.getenv("BUSINESS_IMAGE_MODEL", "flux-pro")

    # ============================================================
    # MODELS — ВИДЕО (GenAPI)
    # ============================================================
    FREE_VIDEO_MODEL = os.getenv("FREE_VIDEO_MODEL", "ltx-2-3")
    LITE_VIDEO_MODEL = os.getenv("LITE_VIDEO_MODEL", "veo-3-1-lite")
    PRO_VIDEO_MODEL = os.getenv("PRO_VIDEO_MODEL", "veo-3.1")
    BUSINESS_VIDEO_MODEL = os.getenv("BUSINESS_VIDEO_MODEL", "veo-3.1")

    # ============================================================
    # LIMITS
    # ============================================================
    FREE_TEXT_LIMIT = int(os.getenv("FREE_TEXT_LIMIT", "3"))
    FREE_IMAGE_LIMIT = int(os.getenv("FREE_IMAGE_LIMIT", "1"))

    LITE_TEXT_LIMIT = int(os.getenv("LITE_TEXT_LIMIT", "20"))
    LITE_IMAGE_LIMIT = int(os.getenv("LITE_IMAGE_LIMIT", "5"))

    PRO_TEXT_LIMIT = int(os.getenv("PRO_TEXT_LIMIT", "100"))
    PRO_IMAGE_LIMIT = int(os.getenv("PRO_IMAGE_LIMIT", "20"))

    BUSINESS_TEXT_LIMIT = int(os.getenv("BUSINESS_TEXT_LIMIT", "500"))
    BUSINESS_IMAGE_LIMIT = int(os.getenv("BUSINESS_IMAGE_LIMIT", "100"))

    # ============================================================
    # AUDIO
    # ============================================================
    MAX_AUDIO_DURATION_SEC = int(os.getenv("MAX_AUDIO_DURATION_SEC", "300"))
    MAX_AUDIO_SIZE_MB = int(os.getenv("MAX_AUDIO_SIZE_MB", "20"))

    # ============================================================
    # ТОКЕНЫ — ПАКЕТЫ ДЛЯ ПОКУПКИ
    # ============================================================
    @property
    def TOKEN_PACKAGES(self):
        return {
            "free": {"name": "💡 Пробный", "tokens": 10, "price": 0},
            "starter": {"name": "⚡ Стартовый", "tokens": 50, "price": 100},
            "optimal": {"name": "🚀 Оптимальный", "tokens": 250, "price": 500},
            "pro": {"name": "💎 Профессиональный", "tokens": 700, "price": 1190},
            "max": {"name": "👑 Максимальный", "tokens": 2000, "price": 3000},
        }


settings = Settings()
