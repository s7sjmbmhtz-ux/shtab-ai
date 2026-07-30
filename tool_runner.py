import logging
from typing import Optional, Dict, Any

from models import PipelineResult, AISession
from pipeline_adapter import run_tool_pipeline

logger = logging.getLogger(__name__)


async def execute_tool(
    tool_id: str,
    user_id: int,
    input_data: Dict[str, Any],
    session: Optional[AISession] = None,
    mode: str = "initial",
    refinement_request: Optional[str] = None
) -> PipelineResult:
    logger.info(f"Запуск инструмента '{tool_id}' для пользователя {user_id}")

    result = await run_tool_pipeline(
        tool_id=tool_id,
        user_id=user_id,
        input_data=input_data,
        session=session,
        mode=mode,
        refinement_request=refinement_request
    )

    if result.success:
        logger.info(f"Инструмент '{tool_id}' выполнен успешно, history_id={result.history_id}")
    else:
        logger.warning(f"Инструмент '{tool_id}' завершился с ошибкой: {result.error}")

    return result