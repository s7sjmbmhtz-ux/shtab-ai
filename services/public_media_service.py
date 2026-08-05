"""Временная публичная раздача входных изображений.

Некоторые сети GenAPI принимают не multipart-файл, а JSON-массив URL.
Сервис публикует уже скачанное Telegram-фото по случайной временной ссылке.
Для BotHost необходимо включить «Использовать домен».
"""
from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from aiohttp import web

from services.media_storage import LocalMedia
from settings import settings
from utils import logger


class PublicMediaError(RuntimeError):
    """Ошибка подготовки публичной ссылки на входное медиа."""


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
        self.public_base_url = (
            settings.MEDIA_PUBLIC_BASE_URL
            if public_base_url is None
            else public_base_url.rstrip("/")
        )
        self.ttl_seconds = (
            settings.MEDIA_URL_TTL_SECONDS
            if ttl_seconds is None
            else max(60, int(ttl_seconds))
        )
        self._entries: dict[str, _PublicEntry] = {}
        self._path_tokens: dict[str, str] = {}
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._lock = asyncio.Lock()

    @property
    def is_configured(self) -> bool:
        return bool(self.public_base_url)

    async def start(self) -> None:
        if self._runner is not None:
            return

        app = web.Application(client_max_size=settings.MAX_IMAGE_SIZE_MB * 1024 * 1024)
        app.router.add_get("/", self._health)
        app.router.add_get("/health", self._health)
        app.router.add_get("/media/{token}", self._serve_media)

        self._runner = web.AppRunner(app, access_log=None)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        logger.info("🌐 Медиа-сервер запущен на порту %s", self.port)
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
        self._runner = None
        self._site = None

    async def register(self, media: LocalMedia) -> str:
        if not self.public_base_url:
            raise PublicMediaError(
                "Для этой модели нужен публичный адрес фотографии. "
                "В BotHost включите «Использовать домен», дождитесь статуса Online "
                "и повторите генерацию."
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

    async def revoke_path(self, path: str | None) -> None:
        if not path:
            return
        path_key = str(Path(path).resolve())
        async with self._lock:
            token = self._path_tokens.pop(path_key, None)
            if token:
                self._entries.pop(token, None)

    def _url(self, token: str, filename: str) -> str:
        safe_name = quote(filename, safe="")
        return f"{self.public_base_url}/media/{token}?name={safe_name}"

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
        return web.json_response({"status": "ok", "service": "shtab-ai"})

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
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


public_media_service = PublicMediaService()
