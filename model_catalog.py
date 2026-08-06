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
    video_durations: tuple[int, ...] = ()
    default_duration: int | None = None
    description: str = ""
    tier: str = "standard"
    speed: str = "средняя"
    quality: str = "хорошее"
    use_cases: tuple[str, ...] = ()

    def cost_for_duration(self, duration: int | None = None) -> int:
        if self.kind != GenerationKind.VIDEO or duration is None:
            return self.token_cost
        base = self.default_duration or (self.video_durations[0] if self.video_durations else duration)
        if base <= 0:
            return self.token_cost
        # Округляем вверх: длинный ролик никогда не должен стоить дешевле себестоимости.
        return max(1, (self.token_cost * duration + base - 1) // base)


MODELS: dict[str, ModelSpec] = {
    # Текст: цена списывается за один обычный запрос. Позже можно перейти
    # на точный расчёт по usage из ответа API.
    "deepseek-v4-flash": ModelSpec(
        "deepseek-v4-flash", "DeepSeek V4 Flash", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-flash", 5,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
        description="Быстрые тексты, ответы, идеи и повседневные задачи.",
        tier="economy", speed="высокая", quality="хорошее",
        use_cases=("ответы", "идеи", "короткие тексты"),
    ),
    "deepseek-v4-pro": ModelSpec(
        "deepseek-v4-pro", "DeepSeek V4 Pro", GenerationKind.TEXT,
        "/v1/chat/completions", "deepseek-v4-pro", 8,
        {"temperature": 1, "max_tokens": 4096, "stream": False},
        description="Усиленная модель для аналитики, документов и сложных текстов.",
        tier="standard", speed="средняя", quality="высокое",
        use_cases=("аналитика", "документы", "бизнес-тексты"),
    ),
    "gpt-5.4-mini": ModelSpec(
        "gpt-5.4-mini", "GPT-5.4 Mini", GenerationKind.TEXT,
        "/v1/chat/completions", "gpt-5.4-mini", 12,
        {"temperature": 1, "max_tokens": 4096, "stream": False, "reasoning_effort": "none"},
        description="Баланс скорости и качества для бизнеса, кода и сложных задач.",
        tier="standard", speed="высокая", quality="высокое",
        use_cases=("бизнес", "код", "сложные задачи"),
    ),
    "gpt-5-5": ModelSpec(
        "gpt-5-5", "GPT-5.5", GenerationKind.TEXT,
        "/v1/chat/completions", "gpt-5-5", 20,
        {"temperature": 1, "max_tokens": 4096, "stream": False, "reasoning_effort": "none"},
        description="Премиальная текстовая модель для стратегии, продаж и глубокого анализа.",
        tier="premium", speed="средняя", quality="максимальное",
        use_cases=("стратегия", "продажи", "глубокий анализ"),
    ),

    # Изображения: публичный каталог
    "gpt-image-2": ModelSpec(
        "gpt-image-2", "🥇 GPT Image 2", GenerationKind.IMAGE,
        "/api/v1/networks/gpt-image-2", None, 70,
        {"quality": "high", "image_size": "1024x768",
         "num_images": 1, "output_format": "png"},
        supports_input_image=True,
        description="Универсальная генерация и редактирование фотографий.",
        tier="premium", speed="средняя", quality="максимальное",
    ),
    "nano-banana-2": ModelSpec(
        "nano-banana-2", "🎨 Nano Banana 2", GenerationKind.IMAGE,
        "/api/v1/networks/nano-banana-2", None, 70,
        {"is_sync": False, "aspect_ratio": "1:1", "resolution": "1K",
         "num_images": 1, "output_format": "png",
         "enable_web_search": False},
        supports_input_image=True,
        description="Стилизация и креативные преобразования.",
        tier="premium", speed="средняя", quality="максимальное",
    ),
    "flux-2-pro": ModelSpec(
        "flux-2-pro", "⭐ Flux 2 Pro", GenerationKind.IMAGE,
        "/api/v1/networks/flux-2-pro", None, 55,
        {"translate_input": True, "width": 1024, "height": 768,
         "enable_safety_checker": False, "output_format": "png"},
        supports_input_image=True,
        description="Фотореализм, реклама и коммерческие изображения.",
        tier="premium", speed="средняя", quality="высокое",
    ),
    "nano-banana-lite": ModelSpec(
        "nano-banana-lite", "⚡ Nano Banana Lite", GenerationKind.IMAGE,
        "/api/v1/networks/nano-banana-lite", "v1", 45,
        {"is_sync": False, "aspect_ratio": "1:1", "model": "v1",
         "num_images": 1, "output_format": "png"},
        supports_input_image=True,
        description="Быстрая и недорогая генерация.",
        tier="economy", speed="высокая", quality="хорошее",
    ),
    "qwen-image-2": ModelSpec(
        "qwen-image-2", "🖌 Qwen Image 2 Pro", GenerationKind.IMAGE,
        "/api/v1/networks/qwen-image-2", "pro", 55,
        {"translate_input": False, "is_sync": False,
         "negative_prompt": "disfigured, ugly, deformed",
         "width": 832, "height": 832, "model": "pro",
         "num_images": 1, "output_format": "png",
         "enable_prompt_expansion": True, "enable_safety_checker": False},
        supports_input_image=True,
        description="Генерация и точное редактирование по инструкции.",
        tier="premium", speed="средняя", quality="высокое",
    ),
    "flux-kontext": ModelSpec(
        "flux-kontext", "⭐ Flux Kontext", GenerationKind.IMAGE,
        "/api/v1/networks/flux-kontext", "max", 70,
        {"is_sync": False, "translate_input": True, "model": "max",
         "guidance_scale": 3.5, "num_images": 1,
         "output_format": "jpeg", "safety_tolerance": 6},
        supports_input_image=True, requires_input_image=True,
        description="Локально меняет указанные элементы, сохраняя композицию.",
        tier="premium", speed="средняя", quality="максимальное",
    ),
    "cartoonify": ModelSpec(
        "cartoonify", "🧸 Cartoonify", GenerationKind.IMAGE,
        "/api/v1/networks/cartoonify", None, 110,
        {"scale": 1.0, "guidance_scale": 1,
         "num_inference_steps": 28, "enable_safety_checker": False},
        supports_input_image=True, requires_input_image=True,
        description="Мультяшная обработка с выбором силы эффекта.",
        tier="premium", speed="средняя", quality="высокое",
    ),
    "flux-dev": ModelSpec(
        "flux-dev", "⚡ Flux Dev", GenerationKind.IMAGE,
        "/api/v1/networks/flux", "dev", 35,
        {"translate_input": True, "width": 1024, "height": 1024,
         "num_inference_steps": 28, "guidance_scale": 5,
         "num_images": 1, "enable_safety_checker": True},
        supports_input_image=True,
        description="Быстрое универсальное редактирование фотографии.",
        tier="economy", speed="средняя", quality="высокое",
    ),

    # Старые модели сохранены для совместимости внутренних модулей.
    "flux-schnell": ModelSpec(
        "flux-schnell", "Flux Schnell", GenerationKind.IMAGE,
        "/api/v1/networks/flux", "schnell", 20,
        {"translate_input": True, "width": 1024, "height": 1024,
         "num_inference_steps": 4, "guidance_scale": 1,
         "num_images": 1, "enable_safety_checker": True},
    ),
    "flux-pro": ModelSpec(
        "flux-pro", "Flux Pro", GenerationKind.IMAGE,
        "/api/v1/networks/flux", "pro", 120,
        {"translate_input": True, "width": 1024, "height": 1024,
         "num_inference_steps": 28, "guidance_scale": 5,
         "num_images": 1, "enable_safety_checker": True},
        supports_input_image=True,
    ),

    # Видео
    "cogvideox-5b": ModelSpec(
        "cogvideox-5b", "CogVideoX 5B", GenerationKind.VIDEO,
        "/api/v1/networks/cog-video-x-5b", None, 350,
        {"translate_input": True, "width": 720, "height": 480,
         "num_inference_steps": 50, "guidance_scale": 7,
         "use_rife": True, "export_fps": 30},
        video_durations=(3, 5, 10), default_duration=5,
        description="Бюджетное видео по тексту. Подходит для черновиков и тестов.",
        tier="economy", speed="высокая", quality="базовое",
        use_cases=("черновики", "тесты", "простые ролики"),
    ),
    "ltx-2-3": ModelSpec(
        "ltx-2-3", "LTX 2.3", GenerationKind.VIDEO,
        "/api/v1/networks/ltx-2-3", None, 500,
        {"translate_input": True, "mode": "pro", "duration": 6,
         "resolution": "1080p", "aspect_ratio": "16:9", "fps": 25,
         "generate_audio": True},
        supports_input_image=True, supports_end_image=True,
        video_durations=(3, 6, 10), default_duration=6,
        description="Текст или фото в видео, поддерживает начальный и конечный кадр.",
        tier="standard", speed="средняя", quality="хорошее",
        use_cases=("анимация фото", "сцены", "короткие ролики"),
    ),
    "kling-o3": ModelSpec(
        "kling-o3", "Kling Video O3", GenerationKind.VIDEO,
        "/api/v1/networks/kling-video-o3", None, 650,
        {"translate_input": True, "duration": "5", "model": "text-to-video",
         "generate_audio": False, "shot_type": "customize",
         "keep_audio": False, "aspect_ratio": "16:9", "pro": False},
        supports_input_image=True, supports_end_image=True,
        video_durations=(5, 10), default_duration=5,
        description="Текст или фото в видео. Гибкая настройка сцены.",
        tier="standard", speed="средняя", quality="высокое",
        use_cases=("реклама", "оживление фото", "сцены"),
    ),
    "kling-v3": ModelSpec(
        "kling-v3", "Kling Video V3", GenerationKind.VIDEO,
        "/api/v1/networks/kling-video-v3", None, 700,
        {"translate_input": True, "model": "pro", "shot_type": "customize",
         "aspect_ratio": "16:9", "duration": 5, "generate_audio": True,
         "negative_prompt": "blur, distort, and low quality", "cfg_scale": 0.5},
        supports_input_image=True, supports_end_image=True,
        video_durations=(5, 10), default_duration=5,
        description="Качественное видео по тексту или фото, поддерживает звук.",
        tier="premium", speed="средняя", quality="высокое",
        use_cases=("реклама", "соцсети", "видео со звуком"),
    ),
    "veo-3-1-lite": ModelSpec(
        "veo-3-1-lite", "Veo 3.1 Lite", GenerationKind.VIDEO,
        "/api/v1/networks/veo-3-1-lite", None, 900,
        {"aspect_ratio": "16:9", "resolution": "720p", "duration": "8s",
         "generate_audio": True, "auto_fix": True},
        supports_input_image=True, supports_end_image=True,
        video_durations=(4, 6, 8), default_duration=8,
        description="Быстрый премиальный режим Veo: текст или фото, звук.",
        tier="premium", speed="высокая", quality="высокое",
        use_cases=("reels", "реклама", "видео со звуком"),
    ),
    "veo-3-1": ModelSpec(
        "veo-3-1", "Veo 3.1", GenerationKind.VIDEO,
        "/api/v1/networks/veo-3.1", None, 1200,
        {"translate_input": True, "mode": "img2video", "resolution": "720p",
         "duration": "8s", "generate_audio": True, "aspect_ratio": "16:9",
         "enhance_prompt": False, "fast": False, "auto_fix": True},
        supports_input_image=True,
        video_durations=(4, 6, 8), default_duration=8,
        description="Максимальное качество Veo, текст или фото, звук.",
        tier="premium", speed="средняя", quality="максимальное",
        use_cases=("коммерческие ролики", "реклама", "киношные сцены"),
    ),
    "luma-ray2": ModelSpec(
        "luma-ray2", "Luma Ray2", GenerationKind.VIDEO,
        "/api/v1/networks/luma", "ray-2-flash", 800,
        {"translate_input": True, "aspect_ratio": "16:9", "expand_prompt": True,
         "loop": False, "resolution": "720p", "duration": "5s"},
        supports_input_image=True, supports_end_image=True,
        video_durations=(5, 9), default_duration=5,
        description="Плавные кинематографичные сцены по тексту или фото.",
        tier="premium", speed="средняя", quality="высокое",
        use_cases=("кинематографичные сцены", "lifestyle", "реклама"),
    ),
    "runway-gen4": ModelSpec(
        "runway-gen4", "Runway Gen-4", GenerationKind.VIDEO,
        "/api/v1/networks/runway-gen4", "gen4_turbo", 1000,
        {"translate_input": True, "duration": 5, "ratio": "1280:720"},
        supports_input_image=True, requires_input_image=True,
        video_durations=(5, 10), default_duration=5,
        description="Фото в видео. Исходное изображение обязательно.",
        tier="premium", speed="высокая", quality="максимальное",
        use_cases=("оживление фото", "товарные ролики", "реклама"),
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


# Публичный каталог моделей изображений. Режимы и справка хранятся
# централизованно, чтобы меню «по описанию» и «по фотографии» не расходились.
IMAGE_MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "flux-dev": {
        "modes": ("text",),
        "text_description": (
            "Быстрая универсальная модель для создания изображения с нуля по описанию."
        ),
        "text_use_cases": (
            "черновики и идеи",
            "посты и иллюстрации",
            "простые рекламные сцены",
        ),
        "text_note": "Хороший бюджетный вариант, когда важнее скорость, чем максимальная детализация.",
    },
    "nano-banana-lite": {
        "modes": ("text", "photo"),
        "text_description": (
            "Недорогая модель для быстрых изображений по текстовому описанию."
        ),
        "photo_description": (
            "Быстро меняет стиль, фон и общую подачу загруженной фотографии."
        ),
        "text_use_cases": (
            "идеи и варианты",
            "простые сцены",
            "контент для соцсетей",
        ),
        "photo_use_cases": (
            "смена фона",
            "стилизация",
            "простые правки фото",
        ),
        "text_note": "Самый доступный вариант для быстрых генераций.",
        "photo_note": "При сложных правках может хуже сохранять мелкие детали, чем более дорогие модели.",
    },
    "flux-2-pro": {
        "modes": ("text",),
        "text_description": (
            "Качественная генерация по описанию с упором на фотореализм и коммерческую подачу."
        ),
        "text_use_cases": (
            "реклама и баннеры",
            "предметные сцены",
            "фотореалистичные изображения",
        ),
        "text_note": "Подходит, когда важны аккуратная композиция и реалистичная картинка.",
    },
    "qwen-image-2": {
        "modes": ("text", "photo"),
        "text_description": (
            "Универсальная Pro-модель для точного следования текстовой инструкции."
        ),
        "photo_description": (
            "Редактирует загруженное изображение по подробной инструкции пользователя."
        ),
        "text_use_cases": (
            "сложные композиции",
            "иллюстрации",
            "изображения с несколькими объектами",
        ),
        "photo_use_cases": (
            "замена и удаление объектов",
            "смена фона",
            "изменение цвета и деталей",
        ),
        "text_note": "Лучше работает с конкретным и подробным описанием результата.",
        "photo_note": "Опишите, что изменить и что обязательно сохранить без изменений.",
    },
    "gpt-image-2": {
        "modes": ("text",),
        "text_description": (
            "Премиальная генерация изображений по описанию с высокой детализацией."
        ),
        "text_use_cases": (
            "сложные сцены",
            "детализированные иллюстрации",
            "премиальные визуалы",
        ),
        "text_note": (
            "Может отвечать дольше других моделей. У модели есть собственная модерация запросов."
        ),
    },
    "flux-kontext": {
        "modes": ("photo",),
        "photo_description": (
            "Точно меняет отдельные элементы фотографии, стараясь сохранить остальную композицию."
        ),
        "photo_use_cases": (
            "удаление объектов",
            "замена фона",
            "локальные правки",
        ),
        "photo_note": "Лучший выбор, когда нужно изменить конкретную часть изображения, а остальное сохранить.",
    },
    "nano-banana-2": {
        "modes": ("text", "photo"),
        "text_description": (
            "Сильная модель для качественных изображений и сложных творческих сцен."
        ),
        "photo_description": (
            "Качественно перерабатывает фото, меняет сцену и выполняет сложную стилизацию."
        ),
        "text_use_cases": (
            "сложные сцены",
            "креативные визуалы",
            "детализированные изображения",
        ),
        "photo_use_cases": (
            "сложная стилизация",
            "переработка сцены",
            "качественные изменения фото",
        ),
        "text_note": "Выбирайте для более сложного результата, когда скорость не на первом месте.",
        "photo_note": "Подходит для заметных изменений всей сцены, а не только одной детали.",
    },
    "cartoonify": {
        "modes": ("photo",),
        "photo_description": (
            "Превращает фотографию в мультяшную иллюстрацию с выбранной силой эффекта."
        ),
        "photo_use_cases": (
            "мультяшные портреты",
            "аватары",
            "cartoon-обработка фото",
        ),
        "photo_note": (
            "Модель не принимает текстовую инструкцию: после загрузки фото нужно выбрать силу эффекта."
        ),
    },
}


def image_model_supports_mode(model_key: str, mode: str) -> bool:
    profile = IMAGE_MODEL_PROFILES.get(model_key, {})
    return mode in profile.get("modes", ())


def get_image_model_profile(model_key: str) -> dict[str, Any]:
    return IMAGE_MODEL_PROFILES.get(model_key, {})


def list_image_models(mode: str) -> list[ModelSpec]:
    models = [
        MODELS[key]
        for key, profile in IMAGE_MODEL_PROFILES.items()
        if mode in profile.get("modes", ())
        and key in MODELS
        and MODELS[key].enabled
    ]
    return sorted(models, key=lambda model: (model.token_cost, model.title.lower()))

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
    models = [m for m in MODELS.values() if m.kind == kind and m.enabled]
    return sorted(models, key=lambda model: (model.token_cost, model.title.lower()))
