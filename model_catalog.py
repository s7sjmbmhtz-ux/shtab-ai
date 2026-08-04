"""Единый каталог моделей и внутренних цен ШТАБ AI."""
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class GenerationKind(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    key: str
    title: str
    kind: GenerationKind
    endpoint: str
    api_model: str | None
    token_cost: int
    defaults: Mapping[str, Any] = field(default_factory=dict)
    supports_input_image: bool = False
    requires_input_image: bool = False
    supports_end_image: bool = False
    enabled: bool = True


MODELS: dict[str, ModelSpec] = {
    # Текст: цена списывается за один обычный запрос. Позже можно перейти
    # на точный расчёт по usage из ответа API.
    "deepseek-v4-flash": ModelSpec(
        "deepseek-v4-flash", "DeepSeek V4 Flash", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-flash", 5,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
    ),
    "deepseek-v4-pro": ModelSpec(
        "deepseek-v4-pro", "DeepSeek V4 Pro", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-pro", 8,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
    ),
    "gpt-5.4-mini": ModelSpec(
        "gpt-5.4-mini", "GPT-5.4 Mini", GenerationKind.TEXT,
        "/v1/chat/completions", "gpt-5.4-mini", 12,
        {"temperature": 1, "max_tokens": 4096, "stream": False, "reasoning_effort": "none"},
    ),
    "gpt-5-5": ModelSpec(
        "gpt-5-5", "GPT-5.5", GenerationKind.TEXT,
        "/v1/chat/completions", "gpt-5-5", 20,
        {"temperature": 1, "max_tokens": 4096, "stream": False, "reasoning_effort": "none"},
    ),

    # Изображения
    "flux-schnell": ModelSpec(
        "flux-schnell", "Flux Schnell", GenerationKind.IMAGE,
        "/api/v1/networks/flux", "schnell", 20,
        {"translate_input": True, "width": 1024, "height": 1024,
         "num_inference_steps": 4, "guidance_scale": 1, "num_images": 1,
         "enable_safety_checker": True, "strength": 0.8},
        supports_input_image=True,
    ),
    "flux-dev": ModelSpec(
        "flux-dev", "Flux Dev", GenerationKind.IMAGE,
        "/api/v1/networks/flux", "dev", 60,
        {"translate_input": True, "width": 1024, "height": 1024,
         "num_inference_steps": 28, "guidance_scale": 5, "num_images": 1,
         "enable_safety_checker": True, "strength": 0.8},
        supports_input_image=True,
    ),
    "flux-pro": ModelSpec(
        "flux-pro", "Flux Pro", GenerationKind.IMAGE,
        "/api/v1/networks/flux", "pro", 120,
        {"translate_input": True, "width": 1024, "height": 1024,
         "num_inference_steps": 28, "guidance_scale": 5, "num_images": 1,
         "enable_safety_checker": True, "strength": 0.8},
        supports_input_image=True,
    ),

    # Видео
    "cogvideox-5b": ModelSpec(
        "cogvideox-5b", "CogVideoX 5B", GenerationKind.VIDEO,
        "/api/v1/networks/cog-video-x-5b", None, 350,
        {"translate_input": True, "width": 720, "height": 480,
         "num_inference_steps": 50, "guidance_scale": 7,
         "use_rife": True, "export_fps": 30},
    ),
    "ltx-2-3": ModelSpec(
        "ltx-2-3", "LTX 2.3", GenerationKind.VIDEO,
        "/api/v1/networks/ltx-2-3", None, 500,
        {"translate_input": True, "mode": "pro", "duration": 6,
         "resolution": "1080p", "aspect_ratio": "16:9", "fps": 25,
         "generate_audio": True},
        supports_input_image=True, supports_end_image=True,
    ),
    "kling-o3": ModelSpec(
        "kling-o3", "Kling Video O3", GenerationKind.VIDEO,
        "/api/v1/networks/kling-video-o3", None, 650,
        {"translate_input": True, "duration": "5", "model": "text-to-video",
         "generate_audio": False, "shot_type": "customize",
         "keep_audio": False, "aspect_ratio": "16:9", "pro": False},
        supports_input_image=True, supports_end_image=True,
    ),
    "kling-v3": ModelSpec(
        "kling-v3", "Kling Video V3", GenerationKind.VIDEO,
        "/api/v1/networks/kling-video-v3", None, 700,
        {"translate_input": True, "model": "pro", "shot_type": "customize",
         "aspect_ratio": "16:9", "duration": 5, "generate_audio": True,
         "negative_prompt": "blur, distort, and low quality", "cfg_scale": 0.5},
        supports_input_image=True, supports_end_image=True,
    ),
    "veo-3-1-lite": ModelSpec(
        "veo-3-1-lite", "Veo 3.1 Lite", GenerationKind.VIDEO,
        "/api/v1/networks/veo-3-1-lite", None, 900,
        {"aspect_ratio": "16:9", "resolution": "720p", "duration": "8s",
         "generate_audio": True, "auto_fix": True},
        supports_input_image=True, supports_end_image=True,
    ),
    "veo-3-1": ModelSpec(
        "veo-3-1", "Veo 3.1", GenerationKind.VIDEO,
        "/api/v1/networks/veo-3.1", None, 1200,
        {"translate_input": True, "mode": "img2video", "resolution": "720p",
         "duration": "8s", "generate_audio": True, "aspect_ratio": "16:9",
         "enhance_prompt": False, "fast": False, "auto_fix": True},
        supports_input_image=True,
    ),
    "luma-ray2": ModelSpec(
        "luma-ray2", "Luma Ray2", GenerationKind.VIDEO,
        "/api/v1/networks/luma", "ray-2-flash", 800,
        {"translate_input": True, "aspect_ratio": "16:9", "expand_prompt": True,
         "loop": False, "resolution": "720p", "duration": "5s"},
        supports_input_image=True, supports_end_image=True,
    ),
    "runway-gen4": ModelSpec(
        "runway-gen4", "Runway Gen-4", GenerationKind.VIDEO,
        "/api/v1/networks/runway-gen4", "gen4_turbo", 1000,
        {"translate_input": True, "duration": 5, "ratio": "1280:720"},
        supports_input_image=True, requires_input_image=True,
    ),
    # Бизнес-инструменты: отдельные коммерческие продукты поверх DeepSeek V4 Flash.
    "business-sales-script": ModelSpec(
        "business-sales-script", "Скрипт продаж", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-flash", 12,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
    ),
    "business-client-reply": ModelSpec(
        "business-client-reply", "Ответ клиенту", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-flash", 8,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
    ),
    "business-commercial-offer": ModelSpec(
        "business-commercial-offer", "Коммерческое предложение", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-flash", 18,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
    ),
    "business-objections": ModelSpec(
        "business-objections", "Работа с возражениями", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-flash", 10,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
    ),
    "business-chat-analysis": ModelSpec(
        "business-chat-analysis", "Анализ переписки", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-flash", 15,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
    ),
    "business-marketing-post": ModelSpec(
        "business-marketing-post", "Маркетинговый пост", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-flash", 10,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
    ),
    "business-content-plan": ModelSpec(
        "business-content-plan", "Контент-план", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-flash", 20,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
    ),
    "business-audience-analysis": ModelSpec(
        "business-audience-analysis", "Анализ аудитории", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-flash", 20,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
    ),
    "business-email-campaign": ModelSpec(
        "business-email-campaign", "Email-рассылка", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-flash", 12,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
    ),
    "marketplace-seo": ModelSpec(
        "marketplace-seo", "SEO-описание товара", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-flash", 18,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
    ),
    "marketplace-main": ModelSpec("marketplace-main", "Главное фото товара", GenerationKind.IMAGE, "/api/v1/networks/flux", "dev", 80, {"translate_input": True, "width": 1024, "height": 1280, "num_inference_steps": 28, "guidance_scale": 5, "num_images": 1, "enable_safety_checker": True, "strength": 0.72}, supports_input_image=True),
    "marketplace-lifestyle": ModelSpec("marketplace-lifestyle", "Lifestyle-фото товара", GenerationKind.IMAGE, "/api/v1/networks/flux", "dev", 90, {"translate_input": True, "width": 1024, "height": 1280, "num_inference_steps": 28, "guidance_scale": 5, "num_images": 1, "enable_safety_checker": True, "strength": 0.72}, supports_input_image=True),
    "marketplace-infographic": ModelSpec("marketplace-infographic", "Основа инфографики", GenerationKind.IMAGE, "/api/v1/networks/flux", "pro", 140, {"translate_input": True, "width": 1024, "height": 1280, "num_inference_steps": 28, "guidance_scale": 5, "num_images": 1, "enable_safety_checker": True, "strength": 0.72}, supports_input_image=True),
    "marketplace-bundle-item": ModelSpec("marketplace-bundle-item", "Изображение комплекта карточек", GenerationKind.IMAGE, "/api/v1/networks/flux", "dev", 60, {"translate_input": True, "width": 1024, "height": 1280, "num_inference_steps": 28, "guidance_scale": 5, "num_images": 1, "enable_safety_checker": True, "strength": 0.72}, supports_input_image=True),

}

TOKEN_PACKAGES = {
    "start": {"title": "Старт", "tokens": 500, "price_rub": 199},
    "popular": {"title": "Популярный", "tokens": 1500, "price_rub": 499},
    "pro": {"title": "PRO", "tokens": 4000, "price_rub": 999},
    "max": {"title": "MAX", "tokens": 10000, "price_rub": 1999},
}


def get_model(model_key: str) -> ModelSpec:
    try:
        return MODELS[model_key]
    except KeyError as exc:
        raise ValueError(f"Неизвестная модель: {model_key}") from exc


def list_models(kind: GenerationKind) -> list[ModelSpec]:
    return [m for m in MODELS.values() if m.kind == kind and m.enabled]
