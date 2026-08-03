"""Низкоуровневый асинхронный клиент GenAPI."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from services.media_storage import LocalMedia
from settings import settings


class GenAPIError(RuntimeError):
    pass


class GenAPIClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=30, read=300, write=120, pool=30),
            follow_redirects=True,
        )

    @property
    def auth_headers(self) -> dict[str, str]:
        if not settings.GENAPI_API_KEY:
            raise GenAPIError("GENAPI_API_KEY не настроен")
        return {
            "Authorization": f"Bearer {settings.GENAPI_API_KEY}",
            "Accept": "application/json",
        }

    async def post(
        self,
        base_url: str,
        endpoint: str,
        payload: dict[str, Any],
        *,
        files: dict[str, LocalMedia] | None = None,
    ) -> dict[str, Any]:
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        if files:
            data = {key: self._multipart_value(value) for key, value in payload.items() if value is not None}
            opened: list[Any] = []
            multipart: dict[str, tuple[str, Any, str]] = {}
            try:
                for field, media in files.items():
                    handle = open(media.path, "rb")
                    opened.append(handle)
                    multipart[field] = (media.filename, handle, media.content_type)
                response = await self._client.post(url, headers=self.auth_headers, data=data, files=multipart)
            finally:
                for handle in opened:
                    handle.close()
        else:
            headers = {**self.auth_headers, "Content-Type": "application/json"}
            response = await self._client.post(url, headers=headers, json=payload)

        try:
            data = response.json()
        except ValueError as exc:
            body = response.text[:500]
            raise GenAPIError(f"GenAPI вернул не-JSON, HTTP {response.status_code}: {body}") from exc
        if response.is_error:
            raise GenAPIError(f"GenAPI HTTP {response.status_code}: {data}")
        if not isinstance(data, dict):
            raise GenAPIError(f"Неожиданный ответ GenAPI: {data!r}")
        return data

    @staticmethod
    def _multipart_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    async def wait_for_result(self, request_id: int | str, *, timeout: int = 900, interval: int = 5) -> dict[str, Any]:
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
