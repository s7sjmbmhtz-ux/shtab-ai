"""Низкоуровневый асинхронный клиент GenAPI."""
from __future__ import annotations

import asyncio
from typing import Any

import httpx

from settings import settings


class GenAPIError(RuntimeError):
    pass


class GenAPIClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=30, read=180, write=60, pool=30),
            follow_redirects=True,
        )

    @property
    def headers(self) -> dict[str, str]:
        if not settings.GENAPI_API_KEY:
            raise GenAPIError("GENAPI_API_KEY не настроен")
        return {
            "Authorization": f"Bearer {settings.GENAPI_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def post(self, base_url: str, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        response = await self._client.post(url, headers=self.headers, json=payload)
        try:
            data = response.json()
        except ValueError as exc:
            raise GenAPIError(f"GenAPI вернул не-JSON, HTTP {response.status_code}") from exc
        if response.is_error:
            raise GenAPIError(f"GenAPI HTTP {response.status_code}: {data}")
        return data

    async def wait_for_result(self, request_id: int | str, *, timeout: int = 900, interval: int = 5) -> dict[str, Any]:
        # GenAPI long-polling endpoint, используемый текущим проектом.
        deadline = asyncio.get_running_loop().time() + timeout
        endpoint = f"/api/v1/request/get/{request_id}"
        while asyncio.get_running_loop().time() < deadline:
            data = await self.post(settings.GENAPI_BASE_URL, endpoint, {})
            status = str(data.get("status", "")).lower()
            if status in {"success", "completed", "done"}:
                return data
            if status in {"failed", "error", "canceled", "cancelled"}:
                raise GenAPIError(str(data.get("error") or data))
            await asyncio.sleep(interval)
        raise GenAPIError("Превышено время ожидания результата GenAPI")

    async def close(self) -> None:
        await self._client.aclose()


genapi_client = GenAPIClient()
