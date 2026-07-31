import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # TELEGRAM
    BOT_TOKEN = os.getenv("BOT_TOKEN", "ваш_токен_бота")
    BOT_USERNAME = os.getenv("BOT_USERNAME", "@ShtabProBot")

    # GENAPI
    GENAPI_API_KEY = os.getenv("GENAPI_API_KEY", "sk-x44sRSwk2lzgUBOz3Z5RAu6uerXfgfIpYvOaXYibJfiW2M5EzDnEHJsGeBuO")
    GENAPI_BASE_URL = os.getenv("GENAPI_BASE_URL", "https://api.gen-api.ru")

    # ADMIN
    ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "548576688"))
    
    @property
    def admin_telegram_id(self):
        return self.ADMIN_TELEGRAM_ID

    # DATABASE
    DB_PATH = os.getenv("DB_PATH", "ai_shtab.db")

    # AI SERVICE
    AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))
    AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))

    # MODELS — FREE
    FREE_TEXT_MODEL = os.getenv("FREE_TEXT_MODEL", "deepseek/deepseek-v4-flash")
    FREE_IMAGE_MODEL = os.getenv("FREE_IMAGE_MODEL", "flux-schnell")
    FREE_VIDEO_MODEL = os.getenv("FREE_VIDEO_MODEL", "ltx-video")

    # MODELS — LITE
    LITE_TEXT_MODEL = os.getenv("LITE_TEXT_MODEL", "deepseek/deepseek-v4-pro")
    LITE_IMAGE_MODEL = os.getenv("LITE_IMAGE_MODEL", "flux-dev")
    LITE_VIDEO_MODEL = os.getenv("LITE_VIDEO_MODEL", "veo-3.1-lite")

    # MODELS — PRO
    PRO_TEXT_MODEL = os.getenv("PRO_TEXT_MODEL", "openai/gpt-5.4-mini")
    PRO_IMAGE_MODEL = os.getenv("PRO_IMAGE_MODEL", "flux-pro")
    PRO_VIDEO_MODEL = os.getenv("PRO_VIDEO_MODEL", "veo-3.1")

    # MODELS — BUSINESS
    BUSINESS_TEXT_MODEL = os.getenv("BUSINESS_TEXT_MODEL", "openai/gpt-5.5")
    BUSINESS_IMAGE_MODEL = os.getenv("BUSINESS_IMAGE_MODEL", "flux-pro")
    BUSINESS_VIDEO_MODEL = os.getenv("BUSINESS_VIDEO_MODEL", "veo-3.1")

    # LIMITS
    FREE_TEXT_LIMIT = int(os.getenv("FREE_TEXT_LIMIT", "3"))
    FREE_IMAGE_LIMIT = int(os.getenv("FREE_IMAGE_LIMIT", "1"))

    LITE_TEXT_LIMIT = int(os.getenv("LITE_TEXT_LIMIT", "20"))
    LITE_IMAGE_LIMIT = int(os.getenv("LITE_IMAGE_LIMIT", "5"))

    PRO_TEXT_LIMIT = int(os.getenv("PRO_TEXT_LIMIT", "100"))
    PRO_IMAGE_LIMIT = int(os.getenv("PRO_IMAGE_LIMIT", "20"))

    BUSINESS_TEXT_LIMIT = int(os.getenv("BUSINESS_TEXT_LIMIT", "500"))
    BUSINESS_IMAGE_LIMIT = int(os.getenv("BUSINESS_IMAGE_LIMIT", "100"))

    # AUDIO
    MAX_AUDIO_DURATION_SEC = int(os.getenv("MAX_AUDIO_DURATION_SEC", "300"))
    MAX_AUDIO_SIZE_MB = int(os.getenv("MAX_AUDIO_SIZE_MB", "20"))

    @property
    def db_path(self):
        return self.DB_PATH


settings = Settings()
