"""Опциональная проверка GenAPI без встроенных секретов.

По умолчанию сетевой запрос не выполняется. Для платного live-теста:
RUN_LIVE_GENAPI_TEST=1 python test_api.py
"""
from __future__ import annotations

import asyncio
import os

import httpx

from settings import settings


async def test_api() -> None:
    if os.getenv("RUN_LIVE_GENAPI_TEST", "").strip() != "1":
        print("Live-тест пропущен. Установите RUN_LIVE_GENAPI_TEST=1 для запуска.")
        return

    if not settings.GENAPI_API_KEY:
        raise RuntimeError("GENAPI_API_KEY не задан")

    payload = {
        "model": settings.FREE_TEXT_MODEL,
        "messages": [{"role": "user", "content": "Ответь одним словом: работает?"}],
        "temperature": 0,
        "max_tokens": 8,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.GENAPI_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    url = f"{settings.GENAPI_PROXY_URL.rstrip('/')}/v1/chat/completions"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    print(f"GenAPI доступен: HTTP {response.status_code}, поля ответа: {sorted(data)[:10]}")


if __name__ == "__main__":
    asyncio.run(test_api())
