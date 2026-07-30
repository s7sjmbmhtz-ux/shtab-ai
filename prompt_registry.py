"""
Реестр построителей промптов.
"""

from typing import Dict, Optional, Type
from models import BasePromptBuilder


class PromptRegistry:
    """Реестр построителей промптов"""

    def __init__(self):
        self._builders: Dict[str, Type[BasePromptBuilder]] = {}

    def register(self, name: str, builder_class: Type[BasePromptBuilder]) -> None:
        self._builders[name] = builder_class

    def get(self, name: str) -> Optional[Type[BasePromptBuilder]]:
        return self._builders.get(name)

    def create(self, name: str, context) -> str:
        builder_class = self.get(name)
        if not builder_class:
            raise ValueError(f"Builder '{name}' not found")
        builder = builder_class()
        return builder.build(context)


# Глобальный экземпляр
prompt_registry = PromptRegistry()