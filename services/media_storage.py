"""Безопасное временное хранение пользовательских медиа."""
from __future__ import annotations

import asyncio
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot

from settings import settings


_UPLOAD_DIR = Path(tempfile.gettempdir()) / "shtab-ai" / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class LocalMedia:
    path: str
    filename: str
    content_type: str


class MediaStorage:
    async def download_photo(self, bot: Bot, file_id: str) -> LocalMedia:
        telegram_file = await bot.get_file(file_id)
        suffix = Path(telegram_file.file_path or "image.jpg").suffix.lower() or ".jpg"
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            suffix = ".jpg"
        filename = f"{uuid.uuid4().hex}{suffix}"
        path = _UPLOAD_DIR / filename
        await bot.download(telegram_file, destination=path)
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError("Не удалось скачать изображение из Telegram")
        if path.stat().st_size > settings.MAX_IMAGE_SIZE_MB * 1024 * 1024:
            await asyncio.to_thread(path.unlink, missing_ok=True)
            raise ValueError(
                f"Изображение больше допустимых {settings.MAX_IMAGE_SIZE_MB} МБ"
            )
        content_type = {
            ".png": "image/png",
            ".webp": "image/webp",
            ".jpeg": "image/jpeg",
            ".jpg": "image/jpeg",
        }.get(suffix, "application/octet-stream")
        return LocalMedia(str(path), filename, content_type)

    async def remove(self, media: LocalMedia | str | None) -> None:
        if not media:
            return
        path = Path(media.path if isinstance(media, LocalMedia) else media)
        try:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except OSError:
            pass

    async def cleanup_stale(self, max_age_seconds: int = 86400) -> None:
        # mtime использует Unix-время, поэтому здесь также нужно wall clock,
        # а не монотонное время event loop.
        now = time.time()
        for path in _UPLOAD_DIR.glob("*"):
            try:
                age = now - path.stat().st_mtime
                if age > max_age_seconds:
                    await asyncio.to_thread(path.unlink, missing_ok=True)
            except OSError:
                continue


media_storage = MediaStorage()
