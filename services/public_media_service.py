"""Временная публичная раздача входных изображений.

Некоторые сети GenAPI принимают не multipart-файл, а JSON-массив URL.
Сервис публикует уже скачанное Telegram-фото по случайной временной ссылке
и проверяет эту ссылку через внешний HTTPS-домен до отправки в GenAPI.
"""
from __future__ import annotations

import asyncio
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote, urlparse

import httpx
from aiohttp import web

from services.media_storage import LocalMedia
from settings import settings
from utils import logger


class PublicMediaError(RuntimeError):
    """Ошибка подготовки или внешней проверки публичного медиа."""


@dataclass(slots=True)
class _PublicEntry:
    path: Path
    filename: str
    content_type: str
    expires_at: float


class PublicMediaService:
    def __init__(
        self,
        *,
        host: str = "0.0.0.0",
        port: int | None = None,
        public_base_url: str | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        self.host = host
        self.port = settings.PORT if port is None else int(port)
        configured_url = (
            settings.MEDIA_PUBLIC_BASE_URL
            if public_base_url is None
            else public_base_url
        )
        self.public_base_url = configured_url.rstrip("/")
        self.ttl_seconds = (
            settings.MEDIA_URL_TTL_SECONDS
            if ttl_seconds is None
            else max(60, int(ttl_seconds))
        )
        self._entries: dict[str, _PublicEntry] = {}
        self._path_tokens: dict[str, str] = {}
        self._runner: web.AppRunner | None = None
        self._sites: list[web.TCPSite] = []
        self._bound_ports: list[int] = []
        self._lock = asyncio.Lock()
        self._payment_notifier: Callable[[Any], Awaitable[None]] | None = None
        self._verify_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15, read=20, write=15, pool=15),
            follow_redirects=True,
            headers={"User-Agent": "ShtabAI-Media-Check/1.0"},
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.public_base_url)

    def set_payment_notifier(
        self,
        notifier: Callable[[Any], Awaitable[None]] | None,
    ) -> None:
        self._payment_notifier = notifier

    async def start(self) -> None:
        if self._runner is not None:
            return

        app = web.Application(
            client_max_size=settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
        )
        app.router.add_get("/", self._health)
        app.router.add_get("/health", self._health)
        # Новый URL содержит имя файла с расширением. Это важно для части
        # внешних загрузчиков моделей. Старый маршрут оставлен совместимым.
        app.router.add_get("/media/{token}/{filename}", self._serve_media)
        app.router.add_get("/media/{token}", self._serve_media)
        app.router.add_post(settings.YOOKASSA_WEBHOOK_PATH, self._yookassa_webhook)

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()

        # BotHost по умолчанию использует 3000, но в старых инструкциях
        # проект мог быть создан с портом 8000. Слушаем оба варианта, а также
        # явно переданный PORT, чтобы домен не отдавал 404/502 из-за рассинхрона.
        candidate_ports = list(dict.fromkeys((self.port, 3000, 8000)))
        for index, candidate_port in enumerate(candidate_ports):
            site = web.TCPSite(self._runner, self.host, candidate_port)
            try:
                await site.start()
            except OSError:
                if index == 0:
                    raise
                logger.warning(
                    "Не удалось открыть дополнительный HTTP-порт %s",
                    candidate_port,
                )
                continue
            self._sites.append(site)
            self._bound_ports.append(candidate_port)

        logger.info(
            "🌐 Медиа-сервер запущен на портах %s",
            ", ".join(map(str, self._bound_ports)),
        )
        if self.public_base_url:
            logger.info("🔗 Публичная база медиа: %s", self.public_base_url)
        else:
            logger.warning(
                "DOMAIN/MEDIA_PUBLIC_BASE_URL не задан: модели с image_urls/images "
                "будут недоступны до включения домена BotHost"
            )

    async def close(self) -> None:
        async with self._lock:
            self._entries.clear()
            self._path_tokens.clear()
        if self._runner is not None:
            await self._runner.cleanup()
        await self._verify_client.aclose()
        self._runner = None
        self._sites.clear()
        self._bound_ports.clear()

    async def register(self, media: LocalMedia) -> str:
        """Регистрирует локальный файл и возвращает временный HTTPS URL."""
        if not self.public_base_url:
            raise PublicMediaError(
                "Не задан MEDIA_PUBLIC_BASE_URL. Для моделей по фотографии "
                "включите домен BotHost и укажите его публичный HTTPS-адрес."
            )

        parsed = urlparse(self.public_base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise PublicMediaError(
                "MEDIA_PUBLIC_BASE_URL должен быть реальным HTTPS-адресом "
                "вида https://bot1234.bothost.tech"
            )

        path = Path(media.path).resolve()
        if not path.is_file() or path.stat().st_size <= 0:
            raise PublicMediaError("Входное изображение не найдено или пустое")

        now = time.time()
        async with self._lock:
            self._prune_locked(now)
            path_key = str(path)
            existing_token = self._path_tokens.get(path_key)
            if existing_token:
                existing = self._entries.get(existing_token)
                if existing and existing.expires_at > now:
                    return self._url(existing_token, existing.filename)

            token = secrets.token_urlsafe(32)
            entry = _PublicEntry(
                path=path,
                filename=media.filename,
                content_type=media.content_type,
                expires_at=now + self.ttl_seconds,
            )
            self._entries[token] = entry
            self._path_tokens[path_key] = token
            return self._url(token, entry.filename)

    async def register_verified(self, media: LocalMedia) -> str:
        """Создаёт ссылку и убеждается, что она доступна через внешний домен.

        Проверка выполняется до запроса к GenAPI. Поэтому неверный домен,
        неправильный порт BotHost или 404 больше не маскируются под HTTP 503
        от сервиса генерации.
        """
        url = await self.register(media)
        await self.verify_url(url)
        return url

    async def verify_url(self, url: str) -> None:
        last_error = "неизвестная ошибка"
        for attempt in range(3):
            try:
                async with self._verify_client.stream(
                    "GET",
                    url,
                    headers={"Range": "bytes=0-2047"},
                ) as response:
                    content_type = response.headers.get("Content-Type", "").lower()
                    if response.status_code not in {200, 206}:
                        last_error = f"HTTP {response.status_code}"
                    elif not content_type.startswith("image/"):
                        last_error = (
                            "сервер вернул не изображение "
                            f"({content_type or 'Content-Type не указан'})"
                        )
                    else:
                        first_chunk = b""
                        async for chunk in response.aiter_bytes():
                            first_chunk += chunk
                            if len(first_chunk) >= 16:
                                break
                        if first_chunk:
                            return
                        last_error = "сервер вернул пустой файл"
            except (httpx.HTTPError, OSError) as exc:
                last_error = str(exc)

            if attempt < 2:
                await asyncio.sleep(2 * (attempt + 1))

        host = urlparse(url).netloc or "публичный домен"
        raise PublicMediaError(
            "Публичная ссылка на фото недоступна извне: "
            f"{host} ({last_error}). Проверьте в BotHost: «Использовать домен», "
            "порт веб-приложения 3000 или 8000 и MEDIA_PUBLIC_BASE_URL."
        )

    async def revoke_path(self, path: str | None) -> None:
        if not path:
            return
        path_key = str(Path(path).resolve())
        async with self._lock:
            token = self._path_tokens.pop(path_key, None)
            if token:
                self._entries.pop(token, None)

    def _url(self, token: str, filename: str) -> str:
        # Имя в пути даёт внешним загрузчикам расширение .jpg/.png/.webp.
        safe_name = quote(Path(filename).name or "image.jpg", safe="._-")
        return f"{self.public_base_url}/media/{token}/{safe_name}"

    def _prune_locked(self, now: float) -> None:
        expired = [
            token
            for token, entry in self._entries.items()
            if entry.expires_at <= now or not entry.path.exists()
        ]
        for token in expired:
            entry = self._entries.pop(token, None)
            if entry:
                self._path_tokens.pop(str(entry.path), None)

    async def _health(self, _: web.Request) -> web.Response:
        return web.json_response(
            {
                "status": "ok",
                "service": "shtab-ai",
                "media_public_url": bool(self.public_base_url),
            }
        )

    async def _serve_media(self, request: web.Request) -> web.StreamResponse:
        token = request.match_info["token"]
        now = time.time()
        async with self._lock:
            self._prune_locked(now)
            entry = self._entries.get(token)

        if entry is None or entry.expires_at <= now or not entry.path.is_file():
            raise web.HTTPNotFound(text="Media link expired")

        response = web.FileResponse(entry.path)
        response.content_type = entry.content_type
        response.headers["Content-Disposition"] = (
            f'inline; filename="{Path(entry.filename).name}"'
        )
        response.headers["Cache-Control"] = "public, max-age=300"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    async def _yookassa_webhook(self, request: web.Request) -> web.Response:
        """Повторно проверяет объект через API и не доверяет телу webhook."""
        if request.content_length and request.content_length > 256 * 1024:
            raise web.HTTPRequestEntityTooLarge(
                max_size=256 * 1024,
                actual_size=request.content_length,
            )
        try:
            payload = await request.json()
        except (ValueError, json.JSONDecodeError):
            raise web.HTTPBadRequest(text="Invalid JSON")
        if not isinstance(payload, dict):
            raise web.HTTPBadRequest(text="Invalid payload")

        from services.payment_service import PaymentError, payment_service

        try:
            order, credited_now = await payment_service.process_webhook(payload)
        except PaymentError as exc:
            logger.warning("Webhook ЮKassa не обработан: %s", exc)
            raise web.HTTPServiceUnavailable(text="Payment verification failed")
        except Exception:
            logger.exception("Ошибка webhook ЮKassa")
            raise web.HTTPInternalServerError(text="Webhook processing failed")

        if credited_now and order is not None and self._payment_notifier:
            try:
                await self._payment_notifier(order)
            except Exception:
                # Деньги уже зачислены: сбой Telegram не должен повторять
                # финансовую операцию при следующем webhook.
                logger.exception("Не удалось уведомить пользователя об оплате")
        return web.json_response({"status": "ok"})


public_media_service = PublicMediaService()
