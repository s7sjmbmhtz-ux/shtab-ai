import logging
from typing import Optional, Dict, Any

from models import PipelineResult, AISession
from tool_registry import tool_registry
from ai_service import ExecutionPipeline, ai_service
from database import limit_repository, request_repository
from tools import prompt_registry

logger = logging.getLogger(__name__)


async def run_tool_pipeline(
    tool_id: str,
    user_id: int,
    input_data: Dict[str, Any],
    session: Optional[AISession] = None,
    mode: str = "initial",
    refinement_request: Optional[str] = None,
    pipeline: Optional[ExecutionPipeline] = None
) -> PipelineResult:
    try:
        tool = tool_registry.require(tool_id)
    except ValueError as e:
        logger.warning("Tool '%s' not found: %s", tool_id, e)
        return PipelineResult(
            success=False,
            error="Инструмент не найден. Пожалуйста, проверьте ID.",
            status=None
        )
    except Exception as e:
        logger.exception(f"Ошибка получения инструмента '{tool_id}': {e}")
        return PipelineResult(
            success=False,
            error="Внутренняя ошибка. Попробуйте позже.",
            status=None
        )

    # Применяем input_adapter
    if tool.input_adapter:
        try:
            input_data = tool.input_adapter(input_data)
        except Exception as e:
            logger.exception(f"Ошибка в input_adapter для '{tool_id}': {e}")
            return PipelineResult(
                success=False,
                error="Ошибка подготовки данных. Попробуйте позже.",
                status=None
            )

    # Применяем input_validator
    if tool.input_validator:
        try:
            error = tool.input_validator(input_data)
            if error:
                return PipelineResult(
                    success=False,
                    error=error,
                    status=None
                )
        except Exception as e:
            logger.exception(f"Ошибка в input_validator для '{tool_id}': {e}")
            return PipelineResult(
                success=False,
                error="Ошибка валидации данных.",
                status=None
            )

    try:
        if pipeline is None:
            pipeline = ExecutionPipeline(
                ai_service=ai_service,
                limit_repository=limit_repository,
                request_repository=request_repository,
                prompt_registry=prompt_registry
            )

        result = await pipeline.run(
            tool=tool,
            user_id=user_id,
            input_data=input_data,
            session=session,
            mode=mode,
            refinement_request=refinement_request
        )

        return result

    except Exception as e:
        logger.exception(f"Ошибка выполнения Pipeline для '{tool_id}': {e}")
        return PipelineResult(
            success=False,
            error="Внутренняя ошибка. Попробуйте позже.",
            status=None
        )