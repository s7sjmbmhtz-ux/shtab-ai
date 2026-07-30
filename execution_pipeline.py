import asyncio
import logging
from typing import Optional, Dict, Any

from models import (
    ToolDefinition, AISession, PipelineResult,
    GenerationStatus, ResponseType, ValidationResult
)
from database import limit_repository, request_repository, db_manager
from tools import prompt_registry
from services.usage_service import track_usage, get_user_usage_today
from services.subscription_service import get_user_limit
from model_router import get_model_for_tariff
from tariffs import get_tariff

logger = logging.getLogger(__name__)


class ExecutionPipeline:
    def __init__(self, ai_service, limit_repository, request_repository, prompt_registry):
        self.ai_service = ai_service
        self.limit_repo = limit_repository
        self.request_repo = request_repository
        self.prompt_registry = prompt_registry

    async def run(
        self,
        tool: ToolDefinition,
        user_id: int,
        input_data: Dict[str, Any],
        session: Optional[AISession] = None,
        mode: str = "initial",
        refinement_request: Optional[str] = None
    ) -> PipelineResult:
        if mode == "initial":
            validation = await self._validate(input_data, tool)
            if not validation.ok:
                return PipelineResult(
                    success=False,
                    error=validation.message,
                    status=GenerationStatus.ERROR
                )

        if mode == "refine" and session and session.result:
            prompt = self._build_refinement_prompt(session, refinement_request)
        else:
            prompt = self._build_prompt(tool, input_data)

        return await self._generate_and_save(tool, user_id, prompt, input_data)

    async def _validate(self, data: Dict[str, Any], tool: ToolDefinition) -> ValidationResult:
        for step in tool.workflow.steps:
            value = data.get(step.field, "")
            if step.required and not value:
                return ValidationResult(ok=False, message=f"Поле '{step.field}' обязательно")
            if value and len(value) < step.min_length:
                return ValidationResult(ok=False, message=f"Минимальная длина {step.field}: {step.min_length}")
            if value and len(value) > step.max_length:
                return ValidationResult(ok=False, message=f"Максимальная длина {step.field}: {step.max_length}")
            if step.regex and value:
                import re
                if not re.match(step.regex, value):
                    return ValidationResult(ok=False, message=f"Поле '{step.field}' не соответствует формату")
            if step.validator and value:
                result = step.validator.validate(value)
                if not result.ok:
                    return result
        return ValidationResult(ok=True)

    def _build_prompt(self, tool: ToolDefinition, data: Dict[str, Any]) -> str:
        builder_class = self.prompt_registry.get(tool.prompt_builder_id)
        if builder_class:
            from models import PromptContext, PromptMode
            builder = builder_class()  # <-- СОЗДАЁМ ЭКЗЕМПЛЯР!
            context = PromptContext(mode=PromptMode.INITIAL, data=data)
            return builder.build(context)
        return f"Обработай данные: {data}"

    def _build_refinement_prompt(self, session: AISession, request: str) -> str:
        return f"""
Исходный запрос:
{session.prompt or session.data}
Предыдущий результат:
{session.result}
Пользователь просит:
{request}
Обнови результат.
"""

    async def _generate_and_save(
        self,
        tool: ToolDefinition,
        user_id: int,
        prompt: str,
        input_data: Dict[str, Any]
    ) -> PipelineResult:
        start_time = asyncio.get_event_loop().time()

        # ============================================================
        # ПОЛУЧАЕМ МОДЕЛЬ ПО ТАРИФУ
        # ============================================================
        from services.subscription_service import get_user_tariff
        tariff = await get_user_tariff(user_id)
        model = get_model_for_tariff(tariff, tool.response_type)

        kwargs = {
            "model": model,
            "temperature": tool.temperature,
            **tool.provider_kwargs
        }

        # ============================================================
        # ПРОВЕРКА ЛИМИТА
        # ============================================================
        limit = await get_user_limit(user_id, tool.response_type)
        today_used = await get_user_usage_today(user_id, tool.response_type)

        if today_used >= limit:
            return PipelineResult(
                success=False,
                error=f"Лимит тарифа закончился. Лимит: {limit} в день. Выберите тариф выше.",
                status=GenerationStatus.RATE_LIMIT,
                elapsed=0
            )

        # ============================================================
        # ГЕНЕРАЦИЯ
        # ============================================================
        result = await self.ai_service.generate(
            provider_type=tool.provider_type,
            response_type=tool.response_type,
            prompt=prompt,
            **kwargs
        )

        elapsed = asyncio.get_event_loop().time() - start_time

        if result.status != GenerationStatus.SUCCESS:
            return PipelineResult(
                success=False,
                error="Ошибка генерации",
                status=result.status,
                elapsed=elapsed
            )

        # ============================================================
        # СПИСАНИЕ ЛИМИТА (атомарно)
        # ============================================================
        from services.usage_service import check_and_consume_limit
        allowed, used, remaining = await check_and_consume_limit(
            user_id, tool.response_type, limit
        )

        if not allowed:
            return PipelineResult(
                success=False,
                error=f"Лимит тарифа закончился. Лимит: {limit} в день.",
                status=GenerationStatus.RATE_LIMIT,
                elapsed=elapsed
            )

        # ============================================================
        # СОХРАНЕНИЕ ИСТОРИИ
        # ============================================================
        history_id = await self.request_repo.save_request(
            user_id=user_id,
            section=tool.section or tool.id,
            tool=tool.history_tool or tool.id,
            input_data=input_data,
            prompt=prompt,
            response=result.content,
            response_type=tool.response_type,
            provider=result.provider,
            model=model,
            elapsed=elapsed,
            status=result.status
        )

        # ============================================================
        # УЧЁТ РАСХОДОВ
        # ============================================================
        await track_usage(
            user_id=user_id,
            tool_id=tool.id,
            model=model,
            response_type=tool.response_type,
            tokens=None,  # TODO: получить из ответа
            cost=None     # TODO: рассчитать из model_prices
        )

        # ============================================================
        # ПРИМЕНЯЕМ RESPONSE_TRANSFORMER
        # ============================================================
        content = result.content
        if tool.response_transformer:
            content = tool.response_transformer(content, input_data)

        return PipelineResult(
            success=True,
            content=content,
            raw=result.content,
            prompt=prompt,
            status=GenerationStatus.SUCCESS,
            elapsed=elapsed,
            provider=result.provider,
            model=model,
            history_id=history_id,
            response_type=tool.response_type
        )
