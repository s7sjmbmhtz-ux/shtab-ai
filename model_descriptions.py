"""Пользовательские карточки моделей ШТАБ AI.

Карточка показывается до запуска генерации, чтобы пользователь видел
назначение модели, доступные режимы и ограничения до списания токенов.
"""
from __future__ import annotations

from typing import Any

from model_catalog import (
    GenerationKind,
    get_image_model_profile,
    get_model,
)
from video_options import get_video_options, video_min_cost_tokens


TEXT_DETAILS: dict[str, dict[str, Any]] = {
    "deepseek-v4-flash": {
        "summary": "Быстрая и недорогая модель для повседневных текстовых задач.",
        "use_cases": ("ответы на вопросы", "идеи и черновики", "короткие тексты"),
        "limitations": "Для глубокого анализа и больших документов лучше выбрать более сильную модель.",
    },
    "deepseek-v4-pro": {
        "summary": "Усиленная версия DeepSeek для аналитики и более сложных текстов.",
        "use_cases": ("анализ информации", "документы", "бизнес-тексты"),
        "limitations": "Работает медленнее Flash, но лучше подходит для сложных запросов.",
    },
    "gpt-5.4-mini": {
        "summary": "Баланс скорости и качества для работы, бизнеса и программирования.",
        "use_cases": ("деловые задачи", "работа с кодом", "структурирование информации"),
        "limitations": "Для максимально глубокого анализа предусмотрена старшая модель.",
    },
    "gpt-5-5": {
        "summary": "Премиальная текстовая модель для сложных задач и глубокого анализа.",
        "use_cases": ("стратегия", "продажи", "сложные документы и аналитика"),
        "limitations": "Самая дорогая текстовая модель в текущем каталоге.",
    },
    "business-sales-script": {
        "summary": "Готовит структуру разговора менеджера с потенциальным клиентом.",
        "use_cases": ("холодные звонки", "входящие заявки", "продажа услуги или товара"),
    },
    "business-client-reply": {
        "summary": "Формирует вежливый и предметный ответ клиенту.",
        "use_cases": ("мессенджеры", "поддержка", "ответ на вопрос или претензию"),
    },
    "business-commercial-offer": {
        "summary": "Создаёт текст коммерческого предложения под продукт и аудиторию.",
        "use_cases": ("B2B-продажи", "предложение услуги", "письмо потенциальному клиенту"),
    },
    "business-objections": {
        "summary": "Помогает подготовить ответы на возражения покупателей.",
        "use_cases": ("дорого", "я подумаю", "сравнение с конкурентами"),
    },
    "business-chat-analysis": {
        "summary": "Разбирает переписку и указывает, где диалог можно улучшить.",
        "use_cases": ("оценка менеджера", "поиск ошибок", "следующий ответ клиенту"),
    },
    "business-marketing-post": {
        "summary": "Пишет маркетинговый пост под задачу, продукт и аудиторию.",
        "use_cases": ("Telegram", "социальные сети", "анонс или продажа"),
    },
    "business-content-plan": {
        "summary": "Составляет план публикаций по теме, продукту и цели.",
        "use_cases": ("неделя или месяц контента", "рубрики", "идеи публикаций"),
    },
    "business-audience-analysis": {
        "summary": "Помогает описать целевую аудиторию и её основные потребности.",
        "use_cases": ("сегменты аудитории", "боли и мотивы", "маркетинговые гипотезы"),
    },
    "business-email-campaign": {
        "summary": "Готовит текст одного письма или последовательность писем.",
        "use_cases": ("прогрев", "продажа", "возврат клиентов"),
    },
    "marketplace-seo": {
        "summary": "Создаёт SEO-описание товара для карточки маркетплейса.",
        "use_cases": ("название и описание", "ключевые преимущества", "поисковые запросы"),
    },
}


VIDEO_DETAILS: dict[str, dict[str, Any]] = {
    "cogvideox-5b": {
        "summary": "Бюджетная модель для создания простого видео по текстовому описанию.",
        "use_cases": ("черновик идеи", "тест промпта", "простая короткая сцена"),
        "limitations": "Работает только по тексту. Разрешение 720×480, без звука; длительность задаёт модель.",
    },
    "ltx-2-3": {
        "summary": "Универсальная модель для видео по тексту или фотографии с выбором качества.",
        "use_cases": ("анимация фото", "рекламная сцена", "короткий ролик со звуком"),
        "limitations": "Минимальное доступное разрешение — 1080p.",
    },
    "kling-o3": {
        "summary": "Гибкая видеомодель для реалистичных сцен по тексту или исходному кадру.",
        "use_cases": ("оживление фотографии", "реклама", "сцены с движением камеры"),
        "limitations": "Отдельного выбора разрешения в доступном API нет; разрешение задаёт модель.",
    },
    "kling-v3": {
        "summary": "Качественная модель Kling для видео по тексту или фотографии, в том числе со звуком.",
        "use_cases": ("ролики для соцсетей", "реклама", "динамичные сцены"),
        "limitations": "Отдельного выбора разрешения в доступном API нет; разрешение задаёт модель.",
    },
    "veo-3-1-lite": {
        "summary": "Более доступный режим Veo для видео по описанию или изображению.",
        "use_cases": ("Reels и Shorts", "реклама", "короткие ролики со звуком"),
        "limitations": "В текущем подключении подтверждена длительность 8 секунд.",
    },
    "veo-3-1": {
        "summary": "Премиальная модель Veo для детализированных коммерческих и кинематографичных сцен.",
        "use_cases": ("коммерческий ролик", "реклама", "кинематографичная сцена"),
        "limitations": "В текущем подключении подтверждена длительность 8 секунд; 4K заметно дороже.",
    },
    "luma-ray2": {
        "summary": "Модель для плавных кинематографичных видео по тексту или фотографии.",
        "use_cases": ("lifestyle-сцены", "реклама", "плавная анимация исходного кадра"),
        "limitations": "Генерация звука в доступном API не предусмотрена.",
    },
    "runway-gen4": {
        "summary": "Runway Gen-4 Turbo оживляет загруженную фотографию.",
        "use_cases": ("товарный ролик", "оживление фото", "рекламная сцена"),
        "limitations": "Исходная фотография обязательна. Подтверждён только горизонтальный формат 720p, без звука.",
    },
}


def _lines_with_bullets(title: str, items: tuple[str, ...]) -> list[str]:
    if not items:
        return []
    return [f"<b>{title}</b>", *(f"• {item}" for item in items)]


def text_model_card(model_key: str) -> str:
    model = get_model(model_key)
    if model.kind != GenerationKind.TEXT:
        raise ValueError("Это не текстовая модель")

    details = TEXT_DETAILS.get(model_key, {})
    summary = details.get("summary") or model.description or "Текстовая модель для работы с запросами пользователя."
    use_cases = tuple(details.get("use_cases") or model.use_cases)
    limitations = details.get("limitations")

    lines = [
        f"<b>🤖 {model.title}</b>",
        "",
        f"<b>Что это:</b> {summary}",
        "",
        *_lines_with_bullets("Подходит для:", use_cases),
    ]
    if limitations:
        lines.extend(("", f"<b>Важно:</b> {limitations}"))
    lines.extend(
        (
            "",
            f"Скорость: <b>{model.speed}</b>",
            f"Уровень качества: <b>{model.quality}</b>",
            f"Стоимость запроса: <b>{model.token_cost} 💎</b>",
            "",
            "Нажмите «Использовать», чтобы начать диалог с этой моделью.",
        )
    )
    return "\n".join(lines)


def image_model_card(model_key: str, mode: str) -> str:
    model = get_model(model_key)
    if model.kind != GenerationKind.IMAGE:
        raise ValueError("Это не модель изображений")
    if mode not in {"text", "photo"}:
        raise ValueError("Неизвестный режим изображения")

    profile = get_image_model_profile(model_key)
    mode_title = "по текстовому описанию" if mode == "text" else "по фотографии"
    summary = profile.get(f"{mode}_description") or model.description or "Создание изображения."
    use_cases = tuple(profile.get(f"{mode}_use_cases", ()))
    note = profile.get(f"{mode}_note", "")

    lines = [
        f"<b>🖼 {model.title}</b>",
        "",
        f"<b>Режим:</b> {mode_title}",
        f"<b>Что умеет:</b> {summary}",
        "",
        *_lines_with_bullets("Подходит для:", use_cases),
    ]
    if note:
        lines.extend(("", f"<b>Важно:</b> {note}"))
    lines.extend(
        (
            "",
            f"Скорость: <b>{model.speed}</b>",
            f"Уровень качества: <b>{model.quality}</b>",
            f"Стоимость генерации: <b>{model.token_cost} 💎</b>",
            "",
            "Нажмите «Использовать», если эта модель подходит для вашей задачи.",
        )
    )
    return "\n".join(lines)


def _choice_line(label: str, choices: tuple[Any, ...], fixed: str | None) -> str:
    if fixed:
        value = fixed
    elif choices:
        value = " / ".join(choice.label for choice in choices)
    else:
        value = "не выбирается"
    return f"{label}: <b>{value}</b>"


def video_model_card(model_key: str) -> str:
    model = get_model(model_key)
    if model.kind != GenerationKind.VIDEO:
        raise ValueError("Это не видеомодель")

    options = get_video_options(model_key)
    details = VIDEO_DETAILS.get(model_key, {})
    summary = details.get("summary") or model.description or "Создание видео."
    use_cases = tuple(details.get("use_cases") or model.use_cases)
    limitations = details.get("limitations")

    if model.requires_input_image:
        input_modes = "только фотография → видео"
    elif model.supports_input_image:
        input_modes = "текст → видео / фотография → видео"
    else:
        input_modes = "текст → видео"

    if options.fixed_duration_label:
        duration_value = options.fixed_duration_label
    elif options.durations:
        duration_value = " / ".join(f"{seconds} сек" for seconds in options.durations)
    else:
        duration_value = "задаёт модель"

    lines = [
        f"<b>🎬 {model.title}</b>",
        "",
        f"<b>Что это:</b> {summary}",
        f"<b>Исходник:</b> {input_modes}",
        "",
        *_lines_with_bullets("Подходит для:", use_cases),
        "",
        "<b>Настройки в боте:</b>",
        _choice_line("Качество", options.qualities, options.fixed_quality_label),
        _choice_line("Разрешение", options.resolutions, options.fixed_resolution_label),
        f"Длительность: <b>{duration_value}</b>",
        _choice_line("Звук", options.audio_choices, options.fixed_audio_label),
        _choice_line("Формат", options.aspects, options.fixed_aspect_label),
    ]
    if limitations:
        lines.extend(("", f"<b>Важно:</b> {limitations}"))
    lines.extend(
        (
            "",
            f"Стоимость: <b>от {video_min_cost_tokens(model_key)} 💎</b>",
            "Точная цена будет показана после выбора параметров.",
            "",
            "Нажмите «Использовать», если эта модель подходит для вашей задачи.",
        )
    )
    return "\n".join(lines)
