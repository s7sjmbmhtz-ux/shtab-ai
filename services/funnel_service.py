"""Безопасная запись событий продуктовой воронки."""
from __future__ import annotations

from typing import Any

from database import db_manager
from utils import logger


class FunnelService:
    async def track(
        self,
        user_id: int,
        event: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        try:
            await db_manager.record_funnel_event(user_id, event, context)
        except Exception:
            # Аналитика не должна ломать пользовательский сценарий.
            logger.exception("Не удалось записать событие воронки %s", event)


funnel_service = FunnelService()
