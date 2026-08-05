"""Низкоуровневый асинхронный клиент GenAPI."""
from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from services.media_storage import LocalMedia
from settings import settings


class GenAPIError(RuntimeError):
    """Ошибка взаимодействия с GenAPI."""


class GenAPIClient:
    _RETRYABLE_STATUSES = {502, 503, 504}
    _RETRY_DELAYS = (3, 8)

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=30,
                read=300,
                write=120,
                pool=30,
            ),
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

    @staticmethod
    def _build_url(base_url: str, endpoint: str) -> str:
        return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            body = response.text[:500]
            raise GenAPIError(
                f"GenAPI вернул не-JSON, HTTP {response.status_code}: {body}"
            ) from exc

        if response.is_error:
            if response.status_code == 401:
                raise GenAPIError(
                    "GenAPI отклонил API-ключ. Проверьте GENAPI_API_KEY."
                )
            if response.status_code == 402:
                raise GenAPIError(
                    "На балансе GenAPI недостаточно средств."
                )
            raise GenAPIError(
                f"GenAPI HTTP {response.status_code}: {data}"
            )

        if not isinstance(data, dict):
            raise GenAPIError(
                f"Неожиданный ответ GenAPI: {data!r}"
            )
        return data

    async def post(
        self,
        base_url: str,
        endpoint: str,
        payload: dict[str, Any],
        *,
        files: dict[str, LocalMedia] | None = None,
    ) -> dict[str, Any]:
        url = self._build_url(base_url, endpoint)

        # Повторяем только явные временные ответы шлюза (502/503/504)
        # и ошибки подключения до отправки запроса. ReadTimeout не повторяем:
        # сервер мог уже создать задачу, а повтор породил бы дубль.
        for attempt in range(len(self._RETRY_DELAYS) + 1):
            try:
                if files:
                    response = await self._post_multipart(
                        url,
                        payload,
                        files,
                    )
                else:
                    response = await self._client.post(
                        url,
                        headers={
                            **self.auth_headers,
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                if attempt >= len(self._RETRY_DELAYS):
                    raise GenAPIError(
                        "Не удалось подключиться к GenAPI после повторных попыток."
                    ) from exc
                await asyncio.sleep(self._RETRY_DELAYS[attempt])
                continue

            if (
                response.status_code in self._RETRYABLE_STATUSES
                and attempt < len(self._RETRY_DELAYS)
            ):
                await asyncio.sleep(self._retry_delay(response, attempt))
                continue

            return self._parse_response(response)

        raise GenAPIError("GenAPI не ответил после повторных попыток.")

    async def _post_multipart(
        self,
        url: str,
        payload: dict[str, Any],
        files: dict[str, LocalMedia],
    ) -> httpx.Response:
        form_data = {
            key: self._multipart_value(value)
            for key, value in payload.items()
            if value is not None
        }
        opened: list[Any] = []
        multipart: list[tuple[str, tuple[str, Any, str]]] = []

        try:
            # Файлы открываются заново на каждую попытку. Иначе после первого
            # запроса повтор отправил бы пустой поток с курсором в конце.
            for field, media in files.items():
                handle = open(media.path, "rb")
                opened.append(handle)
                multipart.append(
                    (
                        field,
                        (
                            media.filename,
                            handle,
                            media.content_type,
                        ),
                    )
                )

            return await self._client.post(
                url,
                headers=self.auth_headers,
                data=form_data,
                files=multipart,
            )
        finally:
            for handle in opened:
                handle.close()

    async def get(
        self,
        base_url: str,
        endpoint: str,
    ) -> dict[str, Any]:
        url = self._build_url(base_url, endpoint)
        for attempt in range(len(self._RETRY_DELAYS) + 1):
            try:
                response = await self._client.get(
                    url,
                    headers=self.auth_headers,
                )
            except httpx.TransportError as exc:
                if attempt >= len(self._RETRY_DELAYS):
                    raise GenAPIError(
                        "Не удалось получить статус задачи GenAPI."
                    ) from exc
                await asyncio.sleep(self._RETRY_DELAYS[attempt])
                continue

            if (
                response.status_code in self._RETRYABLE_STATUSES
                and attempt < len(self._RETRY_DELAYS)
            ):
                await asyncio.sleep(self._retry_delay(response, attempt))
                continue

            return self._parse_response(response)

        raise GenAPIError("GenAPI не ответил после повторных попыток.")

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return max(1.0, min(30.0, float(retry_after)))
            except ValueError:
                pass
        return float(self._RETRY_DELAYS[attempt])

    @staticmethod
    def _multipart_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    @staticmethod
    def _unwrap_payload(data: dict[str, Any]) -> dict[str, Any]:
        """
        GenAPI может возвращать результат как напрямую, так и внутри
        ключей data/request/result. Разворачиваем только словари.
        """
        current = data
        for key in ("data", "request", "result"):
            nested = current.get(key)
            if isinstance(nested, dict):
                current = nested
        return current

    @staticmethod
    def _has_result(data: dict[str, Any]) -> bool:
        """
        Считаем задачу готовой, если уже появился output/response/files,
        даже если статус провайдера называется нестандартно.
        """
        for key in (
            "output",
            "response",
            "files",
            "file",
            "images",
            "image",
            "videos",
            "video",
            "url",
        ):
            value = data.get(key)
            if value not in (None, "", [], {}):
                return True
        return False

    async def wait_for_result(
        self,
        request_id: int | str,
        *,
        timeout: int = 900,
        interval: int = 5,
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        endpoint = f"/api/v1/request/get/{request_id}"

        success_statuses = {
            "success",
            "completed",
            "complete",
            "done",
            "ready",
            "finished",
            "generated",
        }
        failed_statuses = {
            "failed",
            "failure",
            "error",
            "canceled",
            "cancelled",
            "rejected",
        }

        last_data: dict[str, Any] | None = None

        while asyncio.get_running_loop().time() < deadline:
            raw = await self.get(
                settings.GENAPI_BASE_URL,
                endpoint,
            )
            data = self._unwrap_payload(raw)
            last_data = data

            status = str(
                data.get("status")
                or raw.get("status")
                or ""
            ).strip().lower()

            if self._has_result(data):
                return data

            if status in success_statuses:
                return data

            if status in failed_statuses:
                error = (
                    data.get("error")
                    or data.get("message")
                    or raw.get("error")
                    or raw.get("message")
                    or data
                )
                raise GenAPIError(str(error))

            await asyncio.sleep(interval)

        raise GenAPIError(
            "Превышено время ожидания результата GenAPI. "
            f"Последний ответ: {last_data!r}"
        )

    async def close(self) -> None:
        await self._client.aclose()


genapi_client = GenAPIClient()
