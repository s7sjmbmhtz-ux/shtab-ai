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


class RateLimitMiddleware(BaseMiddleware):
    """Общий постоянный лимит сообщений и нажатий пользователя."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if not user or settings.is_admin(user.id):
            return await handler(event, data)
        if isinstance(event, CallbackQuery):
            bucket = "callbacks"
            limit = settings.RATE_LIMIT_CALLBACKS_PER_MINUTE
        elif isinstance(event, Message):
            bucket = "messages"
            limit = settings.RATE_LIMIT_MESSAGES_PER_MINUTE
        else:
            return await handler(event, data)
        allowed, retry_after = await db_manager.check_rate_limit(
            user.id,
            bucket,
            limit=limit,
            window_seconds=60,
        )
        if allowed:
            return await handler(event, data)
        text = f"Слишком много действий. Попробуйте через {retry_after} сек."
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(text)
        return None
