"""Резервные копии SQLite и аварийные уведомления администраторам."""
from __future__ import annotations

import asyncio
import contextlib
import html
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot

from database import db_manager
from settings import settings
from utils import logger


class OperationsService:
    def __init__(self) -> None:
        self._bot: Bot | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._last_alert: dict[str, float] = {}
        self._stopping = False

    async def start(self, bot: Bot) -> None:
        if self._tasks:
            return
        self._bot = bot
        self._stopping = False
        self._tasks.append(
            asyncio.create_task(self._monitor_loop(), name="operations-monitor")
        )
        if settings.BACKUP_ENABLED:
            self._tasks.append(
                asyncio.create_task(self._backup_loop(), name="database-backup")
            )

    async def stop(self) -> None:
        self._stopping = True
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    async def create_backup(self) -> Path:
        path = await asyncio.to_thread(self._create_backup_sync)
        logger.info("Резервная копия БД создана: %s", path)
        return path

    def latest_backup(self) -> Path | None:
        backup_dir = self._backup_dir()
        backups = sorted(backup_dir.glob("shtab-ai-*.sqlite3"), reverse=True)
        return backups[0] if backups else None

    async def _backup_loop(self) -> None:
        interval = max(600, settings.BACKUP_INTERVAL_SECONDS)
        while not self._stopping:
            try:
                await self.create_backup()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Не удалось создать резервную копию БД")
                await self._alert(
                    "backup_failed",
                    "❌ <b>Ошибка резервного копирования</b>\n"
                    + html.escape(str(exc)[:800]),
                )
            await asyncio.sleep(interval)

    async def _monitor_loop(self) -> None:
        interval = max(30, settings.MONITOR_INTERVAL_SECONDS)
        while not self._stopping:
            try:
                await self._run_checks()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Ошибка технического мониторинга")
                await self._alert(
                    "monitor_failed",
                    "🚨 <b>Технический мониторинг не выполнил проверку</b>\n"
                    + html.escape(str(exc)[:800]),
                )
            await asyncio.sleep(interval)

    async def _run_checks(self) -> None:
        async with db_manager.connection() as conn:
            generation_stats = await (await conn.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN status='refunded' THEN 1 ELSE 0 END) AS failed
                   FROM generation_economics
                   WHERE created_at >= datetime('now', '-15 minutes')
                     AND status IN ('completed','refunded')"""
            )).fetchone()
            stale_jobs = int((await (await conn.execute(
                """SELECT COUNT(*) AS c FROM generation_jobs
                   WHERE status IN ('processing','ready')
                     AND updated_at < datetime('now', '-30 minutes')"""
            )).fetchone())["c"])
            stale_payments = int((await (await conn.execute(
                """SELECT COUNT(*) AS c FROM payments
                   WHERE status IN ('pending','processing')
                     AND created_at < datetime('now', '-15 minutes')"""
            )).fetchone())["c"])
            provider_balance_errors = int((await (await conn.execute(
                """SELECT COUNT(*) AS c FROM requests
                   WHERE created_at >= datetime('now', '-15 minutes')
                     AND (error_message LIKE '%402%'
                          OR error_message LIKE '%недостаточно средств%')"""
            )).fetchone())["c"])

        total = int(generation_stats["total"] or 0)
        failed = int(generation_stats["failed"] or 0)
        if total >= settings.ALERT_MIN_GENERATIONS:
            rate = failed * 100.0 / total
            if rate >= settings.ALERT_ERROR_RATE_PERCENT:
                await self._alert(
                    "generation_error_rate",
                    "⚠️ <b>Рост ошибок генераций</b>\n"
                    f"За 15 минут: {failed}/{total} ({rate:.1f}%).",
                )
        if stale_jobs:
            await self._alert(
                "stale_generation_jobs",
                "⌛ <b>Зависшие генерации</b>\n"
                f"Старше 30 минут: {stale_jobs}.",
            )
        if stale_payments:
            await self._alert(
                "stale_payments",
                "💳 <b>Платежи долго ожидают подтверждения</b>\n"
                f"Старше 15 минут: {stale_payments}.",
            )
        if provider_balance_errors:
            await self._alert(
                "provider_balance",
                "🚨 <b>Возможна нехватка средств у GenAPI</b>\n"
                f"Ошибок за 15 минут: {provider_balance_errors}.",
            )

        db_path = self._db_path()
        free_mb = shutil.disk_usage(db_path.parent).free // (1024 * 1024)
        if free_mb < settings.ALERT_DISK_FREE_MB:
            await self._alert(
                "disk_space",
                "💾 <b>Заканчивается место на диске</b>\n"
                f"Свободно: {free_mb} МБ.",
            )

    async def _alert(self, key: str, text: str) -> None:
        if self._bot is None:
            return
        now = asyncio.get_running_loop().time()
        last = self._last_alert.get(key, 0.0)
        if now - last < max(60, settings.ALERT_THROTTLE_SECONDS):
            return
        delivered = False
        for admin_id in settings.ADMIN_IDS:
            try:
                await self._bot.send_message(admin_id, text)
                delivered = True
            except Exception:
                logger.exception("Не удалось отправить уведомление админу %s", admin_id)
        if delivered:
            self._last_alert[key] = now

    def _create_backup_sync(self) -> Path:
        source_path = self._db_path()
        if not source_path.is_file():
            raise FileNotFoundError(f"База данных не найдена: {source_path}")
        backup_dir = self._backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        target_path = backup_dir / f"shtab-ai-{stamp}.sqlite3"

        source = sqlite3.connect(str(source_path), timeout=30)
        target = sqlite3.connect(str(target_path), timeout=30)
        try:
            source.backup(target)
            check = target.execute("PRAGMA integrity_check").fetchone()
            if not check or str(check[0]).lower() != "ok":
                raise RuntimeError(f"Проверка копии не пройдена: {check}")
        finally:
            target.close()
            source.close()

        keep = max(1, settings.BACKUP_KEEP_COUNT)
        backups = sorted(backup_dir.glob("shtab-ai-*.sqlite3"), reverse=True)
        for old_path in backups[keep:]:
            with contextlib.suppress(OSError):
                old_path.unlink()
        return target_path

    @staticmethod
    def _db_path() -> Path:
        return Path(settings.DB_PATH).expanduser().resolve()

    @staticmethod
    def _backup_dir() -> Path:
        return Path(settings.BACKUP_DIR).expanduser().resolve()


operations_service = OperationsService()
