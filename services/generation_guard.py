"""Защита от повторного запуска дорогой медиагенерации одним пользователем."""
from __future__ import annotations


class GenerationGuard:
    def __init__(self) -> None:
        self._active_users: set[int] = set()

    def try_acquire(self, user_id: int) -> bool:
        """Атомарно для одного asyncio-цикла помечает генерацию активной."""
        user_id = int(user_id)
        if user_id in self._active_users:
            return False
        self._active_users.add(user_id)
        return True

    def release(self, user_id: int) -> None:
        self._active_users.discard(int(user_id))

    def is_active(self, user_id: int) -> bool:
        return int(user_id) in self._active_users


generation_guard = GenerationGuard()
