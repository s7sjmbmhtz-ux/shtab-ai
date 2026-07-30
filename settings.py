from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ============================================================
    # TELEGRAM
    # ============================================================
    bot_token: str
    bot_username: str = "@ShtabProBot"

    # ============================================================
    # AI PROVIDER
    # ============================================================
    provod_api_key: str
    provod_base_url: str = "https://api.provod.ai/v1"

    # ============================================================
    # ADMIN
    # ============================================================
    admin_telegram_id: int = 548576688

    # ============================================================
    # DATABASE
    # ============================================================
    db_path: str = "ai_shtab.db"

    # ============================================================
    # AI SERVICE
    # ============================================================
    ai_timeout: int = 60
    ai_max_retries: int = 3

    # ============================================================
    # MODELS — FREE
    # ============================================================
    free_text_model: str = "deepseek/deepseek-v4-flash"
    free_image_model: str = "google/gemini-3.1-flash-lite-image"

    # ============================================================
    # MODELS — LITE
    # ============================================================
    lite_text_model: str = "deepseek/deepseek-v4-pro"
    lite_image_model: str = "google/gemini-3.1-flash-image"

    # ============================================================
    # MODELS — PRO
    # ============================================================
    pro_text_model: str = "openai/gpt-5.4-mini"
    pro_image_model: str = "google/gemini-3-pro-image"

    # ============================================================
    # MODELS — BUSINESS
    # ============================================================
    business_text_model: str = "openai/gpt-5.5"
    business_image_model: str = "google/gemini-3-pro-image"

    # ============================================================
    # LIMITS
    # ============================================================
    free_text_limit: int = 3
    free_image_limit: int = 1

    lite_text_limit: int = 20
    lite_image_limit: int = 5

    pro_text_limit: int = 100
    pro_image_limit: int = 20

    business_text_limit: int = 500
    business_image_limit: int = 100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()