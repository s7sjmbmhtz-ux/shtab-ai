"""
Определения всех AI-инструментов.
"""

from typing import List, Optional, Dict
from models import (
    ToolDefinition, Workflow, WorkflowStep, Category, Feature,
    ResponseType, MarketplaceTaskType
)
from tool_ids import ToolNames
from tool_registry import ToolRegistry


# ============================================================
# SALES
# ============================================================

sales_workflow = Workflow(
    id="sales",
    name="Sales AI",
    description="Создание продающих текстов",
    steps=[
        WorkflowStep(
            id="product",
            field="product",
            next_step_id="target",
            description="Что вы продаёте?"
        ),
        WorkflowStep(
            id="target",
            field="target",
            next_step_id="goal",
            description="Кто ваша целевая аудитория?"
        ),
        WorkflowStep(
            id="goal",
            field="goal",
            next_step_id=None,
            description="Какую цель вы преследуете?"
        ),
    ]
)


def sales_input_adapter(data: dict) -> dict:
    return {
        "product": data.get("product", ""),
        "target": data.get("client", ""),
        "goal": "Создать продающий скрипт",
        "average_check": data.get("average_check", ""),
        "communication_format": data.get("communication_format", ""),
        "objections": data.get("objections", "")
    }


def validate_sales_input(data: dict) -> Optional[str]:
    errors = []
    if not data.get("product"):
        errors.append("продукт")
    if not data.get("target"):
        errors.append("целевая аудитория")
    if errors:
        return f"Заполните: {', '.join(errors)}"
    return None


sales_tool = ToolDefinition(
    id=ToolNames.SALES_SCRIPT.value,
    name="Sales AI",
    icon="💰",
    description="Создание продающих текстов",
    category=Category.SALES,
    version="1.0",
    workflow=sales_workflow,
    prompt_builder_id="sales_v1",
    daily_limit=3,
    section="sales",
    history_tool=ToolNames.SALES_SCRIPT.value,
    required_fields=["product", "target", "goal", "average_check", "communication_format", "objections"],
    test_input={
        "product": "CRM-система",
        "target": "Малый бизнес",
        "goal": "Увеличить продажи",
        "average_check": "50 000 ₽",
        "communication_format": "Холодный звонок",
        "objections": "Дорого, сложно внедрять"
    },
    features={Feature.REFINE, Feature.COPY, Feature.FORWARD, Feature.HISTORY},
    temperature=0.7,
    input_adapter=sales_input_adapter,
    input_validator=validate_sales_input,
)


# ============================================================
# MARKETING
# ============================================================

marketing_workflow = Workflow(
    id="marketing",
    name="Marketing AI",
    description="Создание продающих постов",
    steps=[
        WorkflowStep(
            id="product",
            field="product",
            next_step_id="audience",
            description="Что вы продаёте?"
        ),
        WorkflowStep(
            id="audience",
            field="audience",
            next_step_id="platform",
            description="Кто ваша ЦА?"
        ),
        WorkflowStep(
            id="platform",
            field="platform",
            next_step_id="style",
            description="Где публикуете?"
        ),
        WorkflowStep(
            id="style",
            field="style",
            next_step_id=None,
            description="Выберите стиль"
        ),
    ]
)


def marketing_input_adapter(data: dict) -> dict:
    return {
        "product": data.get("product", ""),
        "audience": data.get("audience", ""),
        "platform": data.get("platform", ""),
        "style": data.get("style", "")
    }


def validate_marketing_input(data: dict) -> Optional[str]:
    errors = []
    if not data.get("product"):
        errors.append("продукт")
    if not data.get("audience"):
        errors.append("аудиторию")
    if not data.get("platform"):
        errors.append("платформу")
    if not data.get("style"):
        errors.append("стиль")
    if errors:
        return f"Заполните: {', '.join(errors)}"
    return None


marketing_tool = ToolDefinition(
    id=ToolNames.MARKETING_POST.value,
    name="Marketing AI",
    icon="📝",
    description="Создание продающих постов",
    category=Category.MARKETING,
    version="1.0",
    workflow=marketing_workflow,
    prompt_builder_id="marketing_v1",
    daily_limit=3,
    section="marketing",
    history_tool=ToolNames.MARKETING_POST.value,
    required_fields=["product", "audience", "platform", "style"],
    test_input={
        "product": "CRM-система",
        "audience": "Малый бизнес",
        "platform": "Telegram",
        "style": "Экспертный"
    },
    features={Feature.REFINE, Feature.COPY, Feature.FORWARD, Feature.HISTORY},
    temperature=0.7,
    input_adapter=marketing_input_adapter,
    input_validator=validate_marketing_input,
)


# ============================================================
# IMAGE
# ============================================================

image_workflow = Workflow(
    id="image",
    name="Image AI",
    description="Генерация изображений",
    steps=[
        WorkflowStep(
            id="description",
            field="description",
            next_step_id="purpose",
            description="Что изобразить?"
        ),
        WorkflowStep(
            id="purpose",
            field="purpose",
            next_step_id="style",
            description="Для чего изображение?"
        ),
        WorkflowStep(
            id="style",
            field="style",
            next_step_id="size",
            description="Стиль изображения"
        ),
        WorkflowStep(
            id="size",
            field="size",
            next_step_id=None,
            description="Размер изображения"
        ),
    ]
)


def image_input_adapter(data: dict) -> dict:
    sizes = {
        "⬜ Квадрат": "1024x1024",
        "⬆️ Вертикальный": "1024x1536",
        "↔️ Горизонтальный": "1536x1024",
    }
    return {
        "description": data.get("description", ""),
        "purpose": data.get("purpose", ""),
        "style": data.get("style", ""),
        "size": sizes.get(data.get("size", ""), "1024x1024"),
    }


def validate_image_input(data: dict) -> Optional[str]:
    errors = []
    if not data.get("description"):
        errors.append("описание изображения")
    if not data.get("purpose"):
        errors.append("назначение")
    if not data.get("style"):
        errors.append("стиль")
    if not data.get("size"):
        errors.append("размер")
    if errors:
        return f"Заполните: {', '.join(errors)}"
    return None


def image_response_transformer(content: str, data: dict) -> str:
    return content


image_tool = ToolDefinition(
    id=ToolNames.IMAGE_CREATIVE.value,
    name="Image AI",
    icon="🖼",
    description="Генерация изображений",
    category=Category.IMAGE,
    version="1.0",
    workflow=image_workflow,
    prompt_builder_id="image_v1",
    daily_limit=3,
    section="image",
    history_tool=ToolNames.IMAGE_CREATIVE.value,
    response_type=ResponseType.IMAGE,
    provider_type="image",
    provider_kwargs={
        "default_size": "1024x1024"
    },
    required_fields=["description", "purpose", "style", "size"],
    test_input={
        "description": "Кот в космосе",
        "purpose": "реклама",
        "style": "реалистичный",
        "size": "1024x1024"
    },
    features={Feature.REFINE, Feature.COPY, Feature.FORWARD, Feature.HISTORY},
    temperature=0.7,
    input_adapter=image_input_adapter,
    input_validator=validate_image_input,
    response_transformer=image_response_transformer,
)


# ============================================================
# ASSISTANT
# ============================================================

assistant_workflow = Workflow(
    id="assistant",
    name="AI Assistant",
    description="Универсальный AI-помощник",
    steps=[
        WorkflowStep(
            id="question",
            field="message",
            next_step_id=None,
            description="Ваш вопрос",
            required=True,
            min_length=3,
            max_length=4000,
        )
    ]
)


def assistant_input_adapter(data: dict) -> dict:
    return {
        "message": data.get("message", ""),
        "context": data.get("context", ""),
        "history": data.get("history", []),
    }


def validate_assistant_input(data: dict) -> Optional[str]:
    if not data.get("message"):
        return "Напишите ваш вопрос"
    if len(data["message"]) < 3:
        return "Вопрос слишком короткий"
    return None


assistant_tool = ToolDefinition(
    id=ToolNames.ASSISTANT.value,
    name="AI Assistant",
    icon="🤖",
    description="Универсальный AI-помощник",
    category=Category.ASSISTANT,
    version="1.0",
    workflow=assistant_workflow,
    prompt_builder_id="assistant_v1",
    daily_limit=20,
    section="assistant",
    history_tool=ToolNames.ASSISTANT.value,
    required_fields=["message"],
    test_input={
        "message": "Придумай идею для бизнеса",
        "context": "",
        "history": []
    },
    features={Feature.REFINE, Feature.COPY, Feature.FORWARD, Feature.HISTORY},
    temperature=0.7,
    input_adapter=assistant_input_adapter,
    input_validator=validate_assistant_input,
)


# ============================================================
# MARKETPLACE
# ============================================================

marketplace_workflow = Workflow(
    id="marketplace",
    name="Marketplace AI",
    description="Помощник для маркетплейсов",
    steps=[
        WorkflowStep(
            id="platform",
            field="platform",
            next_step_id="task",
            description="Выберите площадку",
            required=True,
            min_length=2,
            max_length=50,
        ),
        WorkflowStep(
            id="task",
            field="task",
            next_step_id="category",
            description="Что нужно сделать?",
            required=True,
            min_length=3,
            max_length=200,
        ),
        WorkflowStep(
            id="category",
            field="category",
            next_step_id="product_info",
            description="Категория товара",
            required=True,
            min_length=2,
            max_length=100,
        ),
        WorkflowStep(
            id="product_info",
            field="product_info",
            next_step_id=None,
            description="Информация о товаре",
            required=True,
            min_length=5,
            max_length=2000,
        ),
    ]
)


PLATFORM_MAP = {
    "🟣 Wildberries": "wildberries",
    "🔵 Ozon": "ozon",
    "🟠 Яндекс.Маркет": "yandex_market",
    "📦 Своя площадка": "other",
}


def detect_marketplace_task_type(task: str) -> str:
    """Определяет тип задачи по тексту пользователя."""
    task_lower = task.lower()

    if any(word in task_lower for word in ["карточк", "карта товара", "товарная карточка"]):
        return "product_card"

    if any(word in task_lower for word in ["seo", "ключев", "поисков"]):
        return "seo"

    if any(word in task_lower for word in ["описани", "текст"]):
        return "description"

    if any(word in task_lower for word in ["назван", "заголовк"]):
        return "title_optimization"

    if any(word in task_lower for word in ["отзыв", "отве", "клиент", "возражени"]):
        return "review_reply"

    if any(word in task_lower for word in ["конкурент", "сравнени", "анализ"]):
        return "competitor_analysis"

    return "general"


def marketplace_input_adapter(data: dict) -> dict:
    platform = data.get("platform", "")
    platform_normalized = PLATFORM_MAP.get(platform, "other")
    task = data.get("task", "")
    task_type = detect_marketplace_task_type(task)

    return {
        "platform": platform_normalized,
        "platform_display": platform,
        "task": task,
        "task_type": task_type,
        "category": data.get("category", ""),
        "product_info": data.get("product_info", ""),
    }


def validate_marketplace_input(data: dict) -> Optional[str]:
    errors = []
    if not data.get("platform"):
        errors.append("площадка")
    if not data.get("task"):
        errors.append("задача")
    if not data.get("category"):
        errors.append("категория")
    if not data.get("product_info"):
        errors.append("информация о товаре")
    if errors:
        return f"Заполните: {', '.join(errors)}"
    return None


marketplace_tool = ToolDefinition(
    id=ToolNames.MARKETPLACE.value,
    name="Marketplace AI",
    icon="🛒",
    description="Помощник для маркетплейсов",
    category=Category.MARKETPLACE,
    version="1.0",
    workflow=marketplace_workflow,
    prompt_builder_id="marketplace_v1",
    daily_limit=5,
    section="marketplace",
    history_tool=ToolNames.MARKETPLACE.value,
    required_fields=["platform", "task", "category", "product_info"],
    test_input={
        "platform": "🟣 Wildberries",
        "task": "Создать карточку товара",
        "category": "Электроника",
        "product_info": "Беспроводные наушники с шумоподавлением"
    },
    features={Feature.REFINE, Feature.COPY, Feature.FORWARD, Feature.HISTORY},
    temperature=0.7,
    input_adapter=marketplace_input_adapter,
    input_validator=validate_marketplace_input,
)


# ============================================================
# ВСЕ ИНСТРУМЕНТЫ
# ============================================================

ALL_TOOLS = [
    sales_tool,
    marketing_tool,
    image_tool,
    assistant_tool,
    marketplace_tool,
]


# ============================================================
# РЕЕСТР
# ============================================================

tool_registry = ToolRegistry()