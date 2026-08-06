"""Низкоуровневый асинхронный клиент GenAPI."""
from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any

import httpx

from services.media_storage import LocalMedia
from settings import settings

logger = logging.getLogger(__name__)


class GenAPIError(RuntimeError):
    """Ошибка взаимодействия с GenAPI."""


class GenAPIHTTPError(GenAPIError):
    """HTTP-ошибка GenAPI с сохранённым кодом и телом ответа."""

    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"GenAPI HTTP {status_code}: {payload}")


class GenAPIClient:
    _RETRYABLE_STATUSES = {502, 503, 504}
    # 503 у генераторов часто длится дольше нескольких секунд. Повторы
    # выполняются только пока задача ещё не создана, поэтому дублей не будет.
    _RETRY_DELAYS = (5, 15, 30)

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
            raise GenAPIHTTPError(response.status_code, data)

        if not isinstance(data, dict):
            raise GenAPIError(f"Неожиданный ответ GenAPI: {data!r}")
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

        # ReadTimeout не повторяем: сервер мог уже создать задачу.
        for attempt in range(len(self._RETRY_DELAYS) + 1):
            try:
                if files:
                    response = await self._post_multipart(url, payload, files)
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
                delay = self._delay_with_jitter(self._RETRY_DELAYS[attempt])
                logger.warning(
                    "GenAPI connect error, retry %s/%s in %.1fs",
                    attempt + 1,
                    len(self._RETRY_DELAYS),
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            if response.status_code in self._RETRYABLE_STATUSES:
                if attempt < len(self._RETRY_DELAYS):
                    delay = self._retry_delay(response, attempt)
                    logger.warning(
                        "GenAPI HTTP %s, retry %s/%s in %.1fs",
                        response.status_code,
                        attempt + 1,
                        len(self._RETRY_DELAYS),
                        delay,
                    )
                    await asyncio.sleep(delay)
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
            for field, media in files.items():
                handle = open(media.path, "rb")
                opened.append(handle)
                multipart.append(
                    (field, (media.filename, handle, media.content_type))
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

    async def get(self, base_url: str, endpoint: str) -> dict[str, Any]:
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
                await asyncio.sleep(
                    self._delay_with_jitter(self._RETRY_DELAYS[attempt])
                )
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
                return max(1.0, min(60.0, float(retry_after)))
            except ValueError:
                pass
        return self._delay_with_jitter(self._RETRY_DELAYS[attempt])

    @staticmethod
    def _delay_with_jitter(delay: float) -> float:
        return max(1.0, delay + random.uniform(-0.75, 0.75))

    @staticmethod
    def _multipart_value(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    @staticmethod
    def _unwrap_payload(data: dict[str, Any]) -> dict[str, Any]:
        current = data
        for key in ("data", "request", "result"):
            nested = current.get(key)
            if isinstance(nested, dict):
                current = nested
        return current

    @staticmethod
    def _has_result(data: dict[str, Any]) -> bool:
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
            "success", "completed", "complete", "done", "ready",
            "finished", "generated",
        }
        failed_statuses = {
            "failed", "failure", "error", "canceled", "cancelled", "rejected",
        }
        last_data: dict[str, Any] | None = None

        while asyncio.get_running_loop().time() < deadline:
            raw = await self.get(settings.GENAPI_BASE_URL, endpoint)
            data = self._unwrap_payload(raw)
            last_data = data

            status = str(
                data.get("status") or raw.get("status") or ""
            ).strip().lower()

            if self._has_result(data) or status in success_statuses:
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
