"""
Реестр инструментов.
"""

import logging
from typing import Dict, List, Optional
from models import ToolDefinition
from tool_validator import validate_tool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Реестр AI-инструментов."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def has(self, tool_id: str) -> bool:
        return tool_id in self._tools

    def count(self) -> int:
        return len(self._tools)

    def clear(self) -> None:
        self._tools.clear()
        logger.debug("ToolRegistry cleared")

    def register(self, tool: ToolDefinition, overwrite: bool = False) -> None:
        validate_tool(tool)

        if tool.id in self._tools:
            if overwrite:
                logger.warning(f"Overwriting tool: {tool.id}")
            else:
                raise ValueError(f"Tool already registered: {tool.id}")

        self._tools[tool.id] = tool
        logger.info(f"Зарегистрирован инструмент: {tool.id} ({tool.name})")

    def get(self, tool_id: str) -> Optional[ToolDefinition]:
        return self._tools.get(tool_id)

    def require(self, tool_id: str) -> ToolDefinition:
        tool = self.get(tool_id)
        if not tool:
            raise ValueError(f"Tool '{tool_id}' not found")
        return tool

    def get_all(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def register_defaults(self) -> None:
        """Регистрация стандартных инструментов."""
        from tool_definitions import ALL_TOOLS

        for tool in ALL_TOOLS:
            if not self.has(tool.id):
                self.register(tool)
                # ============================================================
# ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР РЕЕСТРА
# ============================================================

tool_registry = ToolRegistry()
