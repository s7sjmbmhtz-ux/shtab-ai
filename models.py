from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Set, Callable, Protocol
from datetime import datetime
from pydantic import BaseModel, Field


class ResponseType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"


class GenerationStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    EMPTY_RESPONSE = "empty_response"
    NOT_IMPLEMENTED = "not_implemented"


class Category(str, Enum):
    SALES = "sales"
    MARKETING = "marketing"
    MARKETPLACE = "marketplace"
    EDITOR = "editor"
    ANALYTICS = "analytics"
    IMAGE = "image"
    ASSISTANT = "assistant"


class Feature(str, Enum):
    REFINE = "refine"
    COPY = "copy"
    FORWARD = "forward"
    FILES = "files"
    IMAGES = "images"
    HISTORY = "history"
    STREAM = "stream"


class BasePromptBuilder:
    NAME: Optional[str] = None
    def build(self, context) -> str:
        raise NotImplementedError
    def get_id(self) -> str:
        if self.NAME is None:
            raise ValueError(f"{self.__class__.__name__} должен определить NAME")
        return self.NAME


class PromptMode(str, Enum):
    INITIAL = "initial"
    CONTINUE = "continue"
    REFINE = "refine"
    RETRY = "retry"


@dataclass(slots=True)
class PromptContext:
    mode: PromptMode
    data: Dict[str, Any]
    original_response: Optional[str] = None
    original_prompt: Optional[str] = None
    user_request: Optional[str] = None
    conversation: List[Any] = field(default_factory=list)

    @classmethod
    def initial(cls, data: Dict[str, Any]) -> "PromptContext":
        return cls(mode=PromptMode.INITIAL, data=data)

    @classmethod
    def refine(cls, data: Dict[str, Any], original_prompt: str, original_response: str, user_request: str) -> "PromptContext":
        return cls(
            mode=PromptMode.REFINE,
            data=data,
            original_prompt=original_prompt,
            original_response=original_response,
            user_request=user_request
        )


class Tariff(str, Enum):
    FREE = "free"
    LITE = "lite"
    PRO = "pro"
    BUSINESS = "business"


class SalesScriptData(BaseModel):
    product: str
    client: str
    average_check: str
    communication_format: str
    objections: str


class MarketingPostData(BaseModel):
    product: str
    audience: str
    platform: str
    style: str


class ImageGenerationData(BaseModel):
    description: str
    purpose: str
    style: str
    size: str
    size_label: Optional[str] = None
    aspect_ratio: Optional[str] = None


class ImageInfo(BaseModel):
    url: Optional[str] = None
    size: str
    model: Optional[str] = None


class ImageMetadata(BaseModel):
    generated: bool = True
    created_at: datetime


class ImageResponse(BaseModel):
    version: int = 1
    image: ImageInfo
    metadata: ImageMetadata


class TextOperation(str, Enum):
    IMPROVE = "improve"
    SUMMARY = "summary"
    SHORT_SUMMARY = "short_summary"
    FIX = "fix"
    REWRITE = "rewrite"
    SHORTEN = "shorten"
    EXPAND = "expand"
    BULLETS = "bullets"
    TRANSLATE = "translate"


class EditorSession(BaseModel):
    source: str
    text: str
    operation: Optional[TextOperation] = None
    language: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[str] = None
    prompt: Optional[str] = None


class TextEditorData(BaseModel):
    text: str
    operation: TextOperation
    language: Optional[str] = None


class MarketplaceType(str, Enum):
    WILDBERRIES = "wildberries"
    OZON = "ozon"
    YANDEX = "yandex"
    MEGAMARKET = "megamarket"
    KASPI = "kaspi"
    OTHER = "other"


class MarketplaceTool(str, Enum):
    CARD = "card"
    DESIGN_TZ = "design_tz"
    SEO = "seo"
    ANALYZE = "analyze"
    REVIEWS = "reviews"
    QUESTIONS = "questions"
    RICH = "rich"
    ORDER_CARD = "order_card"


class MarketplaceSession(BaseModel):
    source: str
    marketplace: Optional[MarketplaceType] = None
    product_name: Optional[str] = None
    product_specs: Optional[str] = None
    product_advantages: Optional[str] = None
    target_audience: Optional[str] = None
    features: Optional[str] = None
    text: Optional[str] = None
    tool: Optional[MarketplaceTool] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    prompt: Optional[str] = None


class MarketplaceCardData(BaseModel):
    product_name: str
    specs: str
    advantages: str
    audience: str
    features: str
    marketplace: MarketplaceType


class MarketplaceDesignTZData(BaseModel):
    product_name: str
    specs: str
    advantages: str
    marketplace: MarketplaceType


class AIResponse(BaseModel):
    content: str
    title: Optional[str] = None
    tips: List[str] = Field(default_factory=list)
    follow_up: List[str] = Field(default_factory=list)
    provider: str = "deepseek"
    model: Optional[str] = None
    elapsed: Optional[float] = None
    status: GenerationStatus = GenerationStatus.SUCCESS
    response_type: ResponseType = ResponseType.TEXT
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConditionOperator(str, Enum):
    EQUALS = "equals"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    LENGTH_GT = "length_gt"
    LENGTH_LT = "length_lt"
    REGEX = "regex"


@dataclass(slots=True)
class Condition:
    field: str
    operator: ConditionOperator
    value: Any


@dataclass(slots=True)
class WorkflowTransition:
    condition: Condition
    next_step_id: str


@dataclass(slots=True)
class WorkflowStep:
    id: str
    field: str
    next_step_id: Optional[str] = None
    description: str = ""
    transitions: List[WorkflowTransition] = field(default_factory=list)
    required: bool = True
    min_length: int = 3
    max_length: int = 1000
    regex: Optional[str] = None
    validator: Optional['Validator'] = None


@dataclass(slots=True)
class Workflow:
    id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    _step_index: Dict[str, WorkflowStep] = field(init=False, default_factory=dict)

    def __post_init__(self):
        self._step_index = {step.id: step for step in self.steps}
        self._validate()

    def _validate(self) -> None:
        if not self.steps:
            return
        step_ids = set(self._step_index.keys())
        for step in self.steps:
            if step.next_step_id and step.next_step_id not in step_ids:
                raise ValueError(f"Шаг '{step.id}' ссылается на несуществующий шаг '{step.next_step_id}'")
            for transition in step.transitions:
                if transition.next_step_id not in step_ids:
                    raise ValueError(f"Переход из '{step.id}' ссылается на несуществующий шаг '{transition.next_step_id}'")
        visited = set()
        current = self.get_first_step()
        while current:
            if current.id in visited:
                raise ValueError(f"Цикл в Workflow: {current.id}")
            visited.add(current.id)
            current = self.get_next_step(current, {})

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        return self._step_index.get(step_id)

    def get_first_step(self) -> Optional[WorkflowStep]:
        return self.steps[0] if self.steps else None

    def get_next_step(self, step: WorkflowStep, data: Dict[str, Any]) -> Optional[WorkflowStep]:
        for transition in step.transitions:
            if self._check_condition(transition.condition, data):
                return self.get_step(transition.next_step_id)
        if step.next_step_id:
            return self.get_step(step.next_step_id)
        return None

    def _check_condition(self, condition: Condition, data: Dict[str, Any]) -> bool:
        value = data.get(condition.field, "")
        if condition.operator == ConditionOperator.EQUALS:
            return value == condition.value
        elif condition.operator == ConditionOperator.CONTAINS:
            return condition.value in value
        elif condition.operator == ConditionOperator.STARTS_WITH:
            return str(value).startswith(str(condition.value))
        elif condition.operator == ConditionOperator.LENGTH_GT:
            return len(value) > condition.value
        elif condition.operator == ConditionOperator.LENGTH_LT:
            return len(value) < condition.value
        elif condition.operator == ConditionOperator.REGEX:
            import re
            return bool(re.match(condition.value, str(value)))
        return False


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    message: Optional[str] = None
    warning: Optional[str] = None
    hint: Optional[str] = None
    code: Optional[str] = None
    severity: str = "error"


class Validator(Protocol):
    def validate(self, value: str) -> ValidationResult:
        ...


@dataclass(slots=True)
class ToolDefinition:
    id: str
    name: str
    icon: str
    description: str
    category: Category
    workflow: Workflow
    prompt_builder_id: str
    version: str = "1.0"
    daily_limit: int = 3
    section: str = ""
    history_tool: str = ""
    response_type: ResponseType = ResponseType.TEXT
    provider_type: str = "text"
    provider_kwargs: Dict[str, Any] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    test_input: Dict[str, Any] = field(default_factory=dict)
    preferred_model: Optional[str] = None
    temperature: float = 0.7
    features: Set[Feature] = field(default_factory=lambda: {
        Feature.REFINE, Feature.COPY, Feature.FORWARD, Feature.HISTORY
    })
    input_adapter: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    input_validator: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None
    response_transformer: Optional[Callable[[str, Dict[str, Any]], str]] = None

    def __post_init__(self):
        if not self.section:
            self.section = self.id
        if not self.history_tool:
            self.history_tool = self.id


class AISession(BaseModel):
    tool_id: str
    current_step: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    prompt: Optional[str] = None
    completed: bool = False


@dataclass(slots=True)
class PipelineResult:
    success: bool
    content: Optional[str] = None
    raw: Optional[str] = None
    prompt: Optional[str] = None
    error: Optional[str] = None
    status: Optional[GenerationStatus] = None
    elapsed: float = 0.0
    response_type: Optional[ResponseType] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    history_id: Optional[int] = None


class Subscription(BaseModel):
    id: Optional[int] = None
    user_id: int
    tariff: Tariff
    start_date: datetime
    end_date: Optional[datetime] = None
    status: str = "active"


class PaymentProvider(str, Enum):
    YOOKASSA = "yookassa"
    TELEGRAM_STARS = "telegram_stars"


class Payment(BaseModel):
    id: Optional[int] = None
    user_id: int
    provider: PaymentProvider
    amount: float
    currency: str = "RUB"
    status: str = "pending"
    payment_id: Optional[str] = None
    created_at: datetime
# ============================================================
# AUDIO FILE
# ============================================================

class AudioFile(BaseModel):
    """Модель аудиофайла для обработки"""
    filename: str
    extension: str
    duration: int
    size: int
    content: bytes
    mime_type: Optional[str] = None

    @property
    def size_mb(self) -> float:
        return self.size / (1024 * 1024)

    @property
    def duration_minutes(self) -> float:
        return self.duration / 60

    @property
    def extension_without_dot(self) -> str:
        return self.extension.lstrip(".")

    @property
    def mime_type_auto(self) -> str:
        if self.mime_type:
            return self.mime_type
        mime_map = {
            ".ogg": "audio/ogg",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".wav": "audio/wav",
            ".flac": "audio/flac",
            ".aac": "audio/aac",
            ".opus": "audio/opus",
            ".webm": "audio/webm",
        }
        return mime_map.get(self.extension, "application/octet-stream")
# ============================================================
# DATABASE MODELS
# ============================================================

class User(BaseModel):
    id: Optional[int] = None
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    tariff: str = "free"
    is_admin: bool = False
    created_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None


class RequestRecord(BaseModel):
    id: Optional[int] = None
    user_id: int
    section: str
    tool: str
    input_data: Dict[str, Any]
    prompt: str
    response: Optional[str] = None
    response_type: ResponseType = ResponseType.TEXT
    schema_version: int = 1
    provider: Optional[str] = None
    model: Optional[str] = None
    elapsed: Optional[float] = None
    status: GenerationStatus = GenerationStatus.SUCCESS
    error_message: Optional[str] = None
    saved: bool = False
    created_at: Optional[datetime] = None
