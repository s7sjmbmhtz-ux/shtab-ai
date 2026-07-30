from prompt_registry import prompt_registry
from models import PromptContext, PromptMode, BasePromptBuilder


# ============================================================
# BASE PROMPT BUILDER (уже должен быть в models.py)
# ============================================================

# Если BasePromptBuilder нет в models.py, раскомментируй:
# class BasePromptBuilder:
#     NAME: Optional[str] = None
#     def build(self, context: PromptContext) -> str:
#         raise NotImplementedError


# ============================================================
# SALES V1 BUILDER
# ============================================================

class SalesV1PromptBuilder(BasePromptBuilder):
    NAME = "sales_v1"

    def build(self, context: PromptContext) -> str:
        data = context.data
        product = data.get("product", "")
        target = data.get("target", "")
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
Ты — профессиональный копирайтер с 10-летним опытом.
Напиши продающий текст для следующего продукта.

ИНФОРМАЦИЯ:
- Продукт/услуга: {product}
- Целевая аудитория: {target}
- Цель: {goal}

ТРЕБОВАНИЯ:
1. Продающий, убедительный тон
2. Выдели ключевые преимущества
3. Учти боли целевой аудитории
4. Призыв к действию в конце

ТЕКСТ:
"""


# ============================================================
# MARKETING V1 BUILDER
# ============================================================

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


# ============================================================
# IMAGE V1 BUILDER
# ============================================================

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


# ============================================================
# ASSISTANT V1 BUILDER
# ============================================================

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


# ============================================================
# MARKETPLACE V1 BUILDER
# ============================================================

class MarketplaceV1PromptBuilder(BasePromptBuilder):
    NAME = "marketplace_v1"

    def build(self, context: PromptContext) -> str:
        data = context.data
        platform = data.get("platform", "")
        task = data.get("task", "")
        task_type = data.get("task_type", "general")
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

        task_instructions = {
            "product_card": """
СОЗДАНИЕ КАРТОЧКИ ТОВАРА:
1. Продающее название
2. Преимущества (3-5 пунктов)
3. Характеристики
4. SEO-ключи для поиска
5. Призыв к действию
""",
            "description": """
НАПИСАНИЕ ОПИСАНИЯ:
1. Вступление (проблема)
2. Решение (товар)
3. Преимущества
4. Технические детали
5. Заключение
""",
            "title_optimization": """
ОПТИМИЗАЦИЯ НАЗВАНИЯ:
1. Ключевые слова в начале
2. Основные характеристики
3. Длина до 60 символов
4. Уникальность
5. Привлекательность
""",
            "seo": """
SEO-ОПТИМИЗАЦИЯ:
1. Ключевые запросы (5-10)
2. Частотность запросов
3. Структура текста
4. Плотность ключей
5. LSI-фразы
""",
            "review_reply": """
ОТВЕТ НА ОТЗЫВ:
1. Благодарность за отзыв
2. Извинение (если негатив)
3. Решение проблемы
4. Предложение помощи
5. Приглашение вернуться
""",
            "competitor_analysis": """
КОНКУРЕНТНЫЙ АНАЛИЗ:
1. Сравнение с аналогами
2. Преимущества товара
3. Уникальное торговое предложение
4. Позиционирование
5. Рекомендации
""",
        }

        task_instruction = task_instructions.get(task_type, """
УНИВЕРСАЛЬНАЯ СТРУКТУРА:
- Продающее название
- Описание товара
- Преимущества
- Характеристики
- Призыв к действию
""")

        platform_guide = {
            "🟣 Wildberries": """
УЧИТЫВАЙ ОСОБЕННОСТИ WILDBERRIES:
- SEO-название (до 60 символов)
- Ключевые слова в описании
- Чёткие характеристики
- Конкуренция высокая — выделяй преимущества
""",
            "🔵 Ozon": """
УЧИТЫВАЙ ОСОБЕННОСТИ OZON:
- Структурированная карточка
- Преимущества товара (3-5 пунктов)
- Поисковые запросы
- Доверие покупателя
""",
            "🟠 Яндекс.Маркет": """
УЧИТЫВАЙ ОСОБЕННОСТИ ЯНДЕКС.МАРКЕТ:
- Подробное описание
- Характеристики
- Доверие покупателя
- Сравнение с аналогами
""",
            "📦 Своя площадка": """
УНИВЕРСАЛЬНАЯ СТРУКТУРА:
- Продающее название
- Описание товара
- Преимущества
- Характеристики
- Призыв к действию
""",
        }

        platform_guide_text = platform_guide.get(platform, platform_guide.get("📦 Своя площадка", ""))

        return f"""
Ты — эксперт по маркетплейсам с 5-летним опытом.

ПЛОЩАДКА:
{platform}

ЗАДАЧА:
{task}

ТИП ЗАДАЧИ:
{task_type}

КАТЕГОРИЯ ТОВАРА:
{category}

ИНФОРМАЦИЯ О ТОВАРЕ:
{product_info}

{platform_guide_text}

{task_instruction}

ТРЕБОВАНИЯ:
1. Пиши продающий текст
2. Учитывай SEO (ключевые слова)
3. Используй понятную структуру
4. Не добавляй выдуманные характеристики
5. Выделяй преимущества товара

РЕЗУЛЬТАТ:
"""


# ============================================================
# РЕГИСТРАЦИЯ
# ============================================================

prompt_registry.register(SalesV1PromptBuilder.NAME, SalesV1PromptBuilder)
prompt_registry.register(MarketingV1PromptBuilder.NAME, MarketingV1PromptBuilder)
prompt_registry.register(ImageV1PromptBuilder.NAME, ImageV1PromptBuilder)
prompt_registry.register(AssistantV1PromptBuilder.NAME, AssistantV1PromptBuilder)
prompt_registry.register(MarketplaceV1PromptBuilder.NAME, MarketplaceV1PromptBuilder)
