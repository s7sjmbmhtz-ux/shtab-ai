import logging
from tool_registry import tool_registry
from tool_validator import validate_all_tools, validate_prompt_builder

logger = logging.getLogger(__name__)


def startup_check() -> bool:
    try:
        # Регистрируем все инструменты
        tool_registry.register_defaults()

        tools = tool_registry.get_all()

        logger.info("=== TOOL REGISTRY ===")
        for tool in tools:
            logger.info(
                f"  {tool.id}: provider_type={tool.provider_type}, "
                f"response_type={tool.response_type}"
            )

        validate_all_tools(tools)
        logger.info("✅ Все инструменты прошли контракт")

        for tool in tools:
            validate_prompt_builder(tool)
        logger.info("✅ Все PromptBuilders работают")

        logger.info("Startup check passed: %s tools", len(tools))
        return True

    except Exception:
        logger.exception("Startup validation failed")
        raise