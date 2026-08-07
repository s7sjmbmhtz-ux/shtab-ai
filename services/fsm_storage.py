"""SQLite-хранилище FSM: незавершённые диалоги переживают рестарт."""
from __future__ import annotations

import json
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey

from database import db_manager
from settings import settings


class SQLiteFSMStorage(BaseStorage):
    @staticmethod
    def _key(key: StorageKey) -> str:
        return json.dumps(
            [
                key.bot_id,
                key.chat_id,
                key.user_id,
                key.thread_id,
                getattr(key, "business_connection_id", None),
                key.destiny,
            ],
            separators=(",", ":"),
            ensure_ascii=False,
        )

    async def set_state(
        self,
        key: StorageKey,
        state: StateType = None,
    ) -> None:
        value = state.state if isinstance(state, State) else state
        async with db_manager.connection() as conn:
            await conn.execute(
                """INSERT INTO fsm_storage (storage_key, state, data, updated_at)
                   VALUES (?, ?, '{}', CURRENT_TIMESTAMP)
                   ON CONFLICT(storage_key) DO UPDATE SET
                     state=excluded.state,
                     updated_at=CURRENT_TIMESTAMP""",
                (self._key(key), value),
            )
            await conn.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        async with db_manager.connection() as conn:
            row = await (await conn.execute(
                "SELECT state FROM fsm_storage WHERE storage_key=?",
                (self._key(key),),
            )).fetchone()
        return str(row["state"]) if row and row["state"] is not None else None

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise TypeError("FSM data must be a dictionary")
        encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        async with db_manager.connection() as conn:
            await conn.execute(
                """INSERT INTO fsm_storage (storage_key, state, data, updated_at)
                   VALUES (?, NULL, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(storage_key) DO UPDATE SET
                     data=excluded.data,
                     updated_at=CURRENT_TIMESTAMP""",
                (self._key(key), encoded),
            )
            await conn.commit()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        async with db_manager.connection() as conn:
            row = await (await conn.execute(
                "SELECT data FROM fsm_storage WHERE storage_key=?",
                (self._key(key),),
            )).fetchone()
        if not row:
            return {}
        try:
            value = json.loads(row["data"] or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    async def close(self) -> None:
        return None

    async def cleanup_stale(self) -> int:
        days = max(1, settings.FSM_STATE_TTL_DAYS)
        async with db_manager.connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM fsm_storage WHERE updated_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            await conn.commit()
            return max(0, int(cursor.rowcount or 0))


fsm_storage = SQLiteFSMStorage()
