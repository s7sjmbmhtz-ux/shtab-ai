"""Глобальная блокировка доступа для заблокированных пользователей."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from database import db_manager
from settings import settings


class BlockedUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if not user or settings.is_admin(user.id):
            return await handler(event, data)

        if not await db_manager.is_user_blocked(user.id):
            return await handler(event, data)

        text = "⛔ Доступ к боту ограничен администратором."
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(text)
        return None
