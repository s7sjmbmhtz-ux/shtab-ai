from prompt_registry import prompt_registry
from models import PromptContext, PromptMode, BasePromptBuilder


class SalesV1PromptBuilder(BasePromptBuilder):
    NAME = "sales_v1"

    def build(self, context: PromptContext) -> str:
        data = context.data
        product = data.get("product", "")
        client = data.get("client", "")
        average_check = data.get("average_check", "")
        communication_format = data.get("communication_format", "")
        objections = data.get("objections", "")

        if context.mode == PromptMode.REFINE:
            return f"""
Исходный запрос:
{context.original_prompt}
Результат, который нужно изменить:
{context.original_response}
Пользователь просит:
{context.user_request}
Обнови результат.
"""

        return f"""
Ты — профессиональный тренер по продажам с 10-летним опытом.
Создай скрипт продаж по следующей информации:

ИНФОРМАЦИЯ:
- Продукт/услуга: {product}
- Клиент: {client}
- Средний чек: {average_check}
- Формат общения: {communication_format}
- Основные возражения: {objections}

ТРЕБОВАНИЯ:
1. Структурируй скрипт по этапам продаж
2. Дай конкретные фразы для каждого этапа
3. Отработай возражения
4. Добавь призыв к действию

Формат ответа:
---
1. ВСТУПЛЕНИЕ: ...
2. ВЫЯВЛЕНИЕ ПОТРЕБНОСТЕЙ: ...
3. ПРЕЗЕНТАЦИЯ: ...
4. РАБОТА С ВОЗРАЖЕНИЯМИ: ...
5. ЗАКРЫТИЕ СДЕЛКИ: ...
---

ТЕКСТ:
"""


class MarketingV1PromptBuilder(BasePromptBuilder):
    NAME = "marketing_v1"

    def build(self, context: PromptContext) -> str:
        data = context.data
        product = data.get("product", "")
        audience = data.get("audience", "")
        platform = data.get("platform", "")
        style = data.get("style", "")

        if context.mode == PromptMode.REFINE:
            return f"""
Исходный запрос:
{context.original_prompt}
Результат, который нужно изменить:
{context.original_response}
Пользователь просит:
{context.user_request}
Обнови результат.
"""

        return f"""
Ты — профессиональный копирайтер с 10-летним опытом.
Напиши продающий пост для социальных сетей.

ИНФОРМАЦИЯ:
- Продукт/услуга: {product}
- Целевая аудитория: {audience}
- Платформа: {platform}
- Стиль: {style}

ТРЕБОВАНИЯ:
1. Заголовок (привлекающий внимание)
2. Проблема аудитории
3. Решение (презентация продукта)
4. Социальное доказательство
5. Призыв к действию

Формат ответа:
---
TITLE: Заголовок
CONTENT: Полный текст поста
TIPS: - Совет 1 - Совет 2
FOLLOW_UP: - Вариант доработки
---

ТЕКСТ ПОСТА:
"""


class ImageV1PromptBuilder(BasePromptBuilder):
    NAME = "image_v1"

    def build(self, context: PromptContext) -> str:
        data = context.data
        description = data.get("description", "")
        purpose = data.get("purpose", "")
        style = data.get("style", "")
        size = data.get("size", "")

        if context.mode == PromptMode.REFINE:
            refine_request = data.get("refine_request", "")
            original_prompt = context.original_prompt or ""
            if original_prompt:
                return f"""
Исходный промпт:
{original_prompt}

Пользователь просит изменить:
{refine_request}

Обнови промпт с учётом изменений.
"""
            return f"""
Создай изображение.

Объект:
{description}

Назначение:
{purpose}

Стиль:
{style}

Формат:
{size}

Дополнительные изменения:
{refine_request}

Требования:
- высокое качество
- профессиональная композиция
- соответствие назначению изображения
"""

        return f"""
Создай изображение.

Объект:
{description}

Назначение:
{purpose}

Стиль:
{style}

Формат:
{size}

Требования:
- высокое качество
- профессиональная композиция
- соответствие назначению изображения
"""


class AssistantV1PromptBuilder(BasePromptBuilder):
    NAME = "assistant_v1"

    def build(self, context: PromptContext) -> str:
        data = context.data
        message = data.get("message", "")
        context_text = data.get("context", "")
        history = data.get("history", [])

        if context.mode == PromptMode.REFINE:
            return f"""
Исходный запрос:
{context.original_prompt}
Результат, который нужно изменить:
{context.original_response}
Пользователь просит:
{context.user_request}
Обнови результат.
"""

        history_text = ""
        if history:
            history_text = "\n".join([
                f"Пользователь: {h.get('user', '')}\n"
                f"Ассистент: {h.get('assistant', '')}"
                for h in history[-3:]
            ])

        return f"""
Ты — умный AI-ассистент, который помогает пользователю.

ИСТОРИЯ ДИАЛОГА:
{history_text or "Нет истории"}

КОНТЕКСТ (если есть):
{context_text or "Нет контекста"}

ВОПРОС ПОЛЬЗОВАТЕЛЯ:
{message}

ПРАВИЛА:
1. Отвечай точно по вопросу
2. Будь полезным и дружелюбным
3. Если не знаешь ответа — скажи честно
4. Структурируй ответ

ОТВЕТ:
"""


class MarketplaceV1PromptBuilder(BasePromptBuilder):
    NAME = "marketplace_v1"

    def build(self, context: PromptContext) -> str:
        data = context.data
        platform = data.get("platform", "")
        task = data.get("task", "")
        category = data.get("category", "")
        product_info = data.get("product_info", "")

        if context.mode == PromptMode.REFINE:
            return f"""
Исходный запрос:
{context.original_prompt}
Результат, который нужно изменить:
{context.original_response}
Пользователь просит:
{context.user_request}
Обнови результат.
"""

        return f"""
Ты — эксперт по маркетплейсам с 5-летним опытом.

ПЛОЩАДКА:
{platform}

ЗАДАЧА:
{task}

КАТЕГОРИЯ ТОВАРА:
{category}

ИНФОРМАЦИЯ О ТОВАРЕ:
{product_info}

ТРЕБОВАНИЯ:
1. Пиши продающий текст
2. Учитывай SEO (ключевые слова)
3. Используй понятную структуру
4. Не добавляй выдуманные характеристики
5. Выделяй преимущества товара

РЕЗУЛЬТАТ:
"""


# ==================== НОВЫЕ МАРКЕТИНГОВЫЕ ПРОМПТ-БИЛДЕРЫ ====================

class ContentPlanPromptBuilder(BasePromptBuilder):
    NAME = "content_plan_v1"

    def build(self, context: PromptContext) -> str:
        data = context.data
        niche = data.get("niche", "")
        audience = data.get("audience", "")
        platform = data.get("platform", "")

        if context.mode == PromptMode.REFINE:
            return f"""
Исходный запрос:
{context.original_prompt}
Результат, который нужно изменить:
{context.original_response}
Пользователь просит:
{context.user_request}
Обнови результат.
"""

        return f"""
Ты — эксперт по контент-маркетингу. Создай контент-план для бизнеса.

ИНФОРМАЦИЯ:
- Ниша: {niche}
- Целевая аудитория: {audience}
- Платформы: {platform}

ТРЕБОВАНИЯ:
1. Составь контент-план на 30 дней
2. Укажи темы постов
3. Добавь форматы (текст, видео, карусель)
4. Укажи цели для каждой публикации

Формат ответа:
---
ДЕНЬ 1: Тема - Формат - Цель
ДЕНЬ 2: Тема - Формат - Цель
...
---
"""


class OfferPromptBuilder(BasePromptBuilder):
    NAME = "offer_v1"

    def build(self, context: PromptContext) -> str:
        data = context.data
        product = data.get("product", "")
        benefit = data.get("benefit", "")
        audience = data.get("audience", "")

        if context.mode == PromptMode.REFINE:
            return f"""
Исходный запрос:
{context.original_prompt}
Результат, который нужно изменить:
{context.original_response}
Пользователь просит:
{context.user_request}
Обнови результат.
"""

        return f"""
Ты — эксперт по рекламе. Создай продающий оффер для продукта.

ИНФОРМАЦИЯ:
- Продукт: {product}
- Главная выгода: {benefit}
- Целевая аудитория: {audience}

ТРЕБОВАНИЯ:
1. Заголовок (привлекающий внимание)
2. Описание проблемы аудитории
3. Предложение (решение)
4. Преимущества (3-5 пунктов)
5. Призыв к действию

Формат ответа:
---
ЗАГОЛОВОК: ...
ПРОБЛЕМА: ...
РЕШЕНИЕ: ...
ПРЕИМУЩЕСТВА: ...
ПРИЗЫВ: ...
---
"""


class EmailPromptBuilder(BasePromptBuilder):
    NAME = "email_v1"

    def build(self, context: PromptContext) -> str:
        data = context.data
        topic = data.get("topic", "")
        audience = data.get("audience", "")
        goal = data.get("goal", "")

        if context.mode == PromptMode.REFINE:
            return f"""
Исходный запрос:
{context.original_prompt}
Результат, который нужно изменить:
{context.original_response}
Пользователь просит:
{context.user_request}
Обнови результат.
"""

        return f"""
Ты — эксперт по email-маркетингу. Создай письмо для рассылки.

ИНФОРМАЦИЯ:
- Тема письма: {topic}
- Получатели: {audience}
- Цель: {goal}

ТРЕБОВАНИЯ:
1. Привлекающая тема письма
2. Персонализированное обращение
3. Основной текст (продающий/информационный)
4. Призыв к действию
5. Подпись

Формат ответа:
---
ТЕМА: ...
ПРИВЕТСТВИЕ: ...
ОСНОВНОЙ ТЕКСТ: ...
ПРИЗЫВ: ...
ПОДПИСЬ: ...
---
"""


class UTPPromptBuilder(BasePromptBuilder):
    NAME = "utp_v1"

    def build(self, context: PromptContext) -> str:
        data = context.data
        product = data.get("product", "")
        competitors = data.get("competitors", "")
        benefit = data.get("benefit", "")

        if context.mode == PromptMode.REFINE:
            return f"""
Исходный запрос:
{context.original_prompt}
Результат, который нужно изменить:
{context.original_response}
Пользователь просит:
{context.user_request}
Обнови результат.
"""

        return f"""
Ты — эксперт по позиционированию. Создай УТП (уникальное торговое предложение).

ИНФОРМАЦИЯ:
- Продукт: {product}
- Конкуренты: {competitors}
- Главное преимущество: {benefit}

ТРЕБОВАНИЯ:
1. Сформулируй УТП (одно предложение)
2. Объясни, чем ты отличаешься от конкурентов
3. Покажи ценность для клиента
4. Дай примеры использования

Формат ответа:
---
УТП: ...
ОТЛИЧИЯ: ...
ЦЕННОСТЬ: ...
ПРИМЕРЫ: ...
---
"""


class AudienceAnalysisPromptBuilder(BasePromptBuilder):
    NAME = "audience_analysis_v1"

    def build(self, context: PromptContext) -> str:
        data = context.data
        product = data.get("product", "")
        details = data.get("details", "")

        if context.mode == PromptMode.REFINE:
            return f"""
Исходный запрос:
{context.original_prompt}
Результат, который нужно изменить:
{context.original_response}
Пользователь просит:
{context.user_request}
Обнови результат.
"""

        return f"""
Ты — эксперт по маркетингу. Проанализируй целевую аудиторию.

ИНФОРМАЦИЯ:
- Продукт: {product}
- Дополнительная информация: {details}

ТРЕБОВАНИЯ:
1. Кто твои клиенты? (портрет)
2. Их боли и проблемы
3. Что они хотят?
4. Где их найти?
5. Как с ними общаться?

Формат ответа:
---
ПОРТРЕТ: ...
БОЛИ: ...
ЖЕЛАНИЯ: ...
КАНАЛЫ: ...
СТРАТЕГИЯ: ...
---
"""


# ==================== РЕГИСТРАЦИЯ ВСЕХ БИЛДЕРОВ ====================

prompt_registry.register(SalesV1PromptBuilder.NAME, SalesV1PromptBuilder)
prompt_registry.register(MarketingV1PromptBuilder.NAME, MarketingV1PromptBuilder)
prompt_registry.register(ImageV1PromptBuilder.NAME, ImageV1PromptBuilder)
prompt_registry.register(AssistantV1PromptBuilder.NAME, AssistantV1PromptBuilder)
prompt_registry.register(MarketplaceV1PromptBuilder.NAME, MarketplaceV1PromptBuilder)

# Регистрация новых маркетинговых билдеров
prompt_registry.register(ContentPlanPromptBuilder.NAME, ContentPlanPromptBuilder)
prompt_registry.register(OfferPromptBuilder.NAME, OfferPromptBuilder)
prompt_registry.register(EmailPromptBuilder.NAME, EmailPromptBuilder)
prompt_registry.register(UTPPromptBuilder.NAME, UTPPromptBuilder)
prompt_registry.register(AudienceAnalysisPromptBuilder.NAME, AudienceAnalysisPromptBuilder)
