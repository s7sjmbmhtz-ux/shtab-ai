"""Постоянные задания медиагенерации и восстановление после рестарта."""
from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import datetime, timezone
from typing import Any

from aiogram import Bot

from database import db_manager
from model_catalog import GenerationKind, get_model
from services.billing_service import Charge
from services.genapi_client import (
    GenAPIError,
    GenAPITaskFailedError,
    GenAPITaskTimeoutError,
    genapi_client,
)
from settings import settings
from utils import logger


class EmptyGenerationResultError(GenAPITaskFailedError):
    """Задача завершилась, но провайдер не вернул файл."""


RESULT_URL_KEYS = {
    "url",
    "video",
    "image",
    "file",
    "files",
    "output",
    "result",
    "response",
    "images",
    "videos",
    "data",
    "full_response",
}


def collect_result_urls(value: Any) -> list[str]:
    """Собирает только ссылки результата, не заходя во входные параметры."""
    result: list[str] = []
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            result.append(value)
    elif isinstance(value, list):
        for item in value:
            result.extend(collect_result_urls(item))
    elif isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in RESULT_URL_KEYS:
                result.extend(collect_result_urls(item))
    return list(dict.fromkeys(result))


class GenerationJobService:
    def __init__(self) -> None:
        self._bot: Bot | None = None
        self._loop_task: asyncio.Task[None] | None = None
        self._recovery_tasks: set[asyncio.Task[None]] = set()
        self._active_job_ids: set[int] = set()
        self._stopping = False

    async def start(self, bot: Bot) -> None:
        if self._loop_task and not self._loop_task.done():
            return
        self._bot = bot
        self._stopping = False
        self._loop_task = asyncio.create_task(
            self._recovery_loop(),
            name="generation-recovery",
        )

    async def stop(self) -> None:
        self._stopping = True
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._loop_task
        tasks = list(self._recovery_tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._loop_task = None
        self._recovery_tasks.clear()
        self._active_job_ids.clear()

    async def register(
        self,
        *,
        user_id: int,
        chat_id: int,
        model_key: str,
        charge: Charge,
        provider_task: dict[str, Any],
        caption: str,
        duration: int | None = None,
        result_limit: int = 1,
    ) -> int:
        request_id = provider_task.get("request_id") or provider_task.get("id")
        urls = collect_result_urls(provider_task)
        if not request_id and not urls:
            raise GenAPIError(f"GenAPI не вернул request_id: {provider_task}")
        job_id = await db_manager.create_generation_job(
            user_id=user_id,
            chat_id=chat_id,
            model_key=model_key,
            kind=charge.kind.value,
            provider_request_id=str(request_id) if request_id is not None else None,
            economic_id=charge.ledger_id,
            token_cost=charge.amount,
            charge_source=charge.source.value,
            caption=caption,
            duration=duration,
            result_limit=result_limit,
            result_urls=urls or None,
        )
        # Добавление выполняется в той же корутине сразу после COMMIT: фоновый
        # восстановитель не начнёт параллельный опрос новой задачи.
        self._active_job_ids.add(job_id)
        return job_id

    async def wait_for_result(
        self,
        job_id: int,
        provider_task: dict[str, Any],
    ) -> list[str]:
        urls = collect_result_urls(provider_task)
        result = provider_task
        if not urls:
            request_id = provider_task.get("request_id") or provider_task.get("id")
            if not request_id:
                raise GenAPIError(f"GenAPI не вернул request_id: {provider_task}")
            result = await genapi_client.wait_for_result(
                request_id,
                timeout=settings.GENAPI_POLL_TIMEOUT,
                interval=settings.GENAPI_POLL_INTERVAL,
            )
            urls = collect_result_urls(result)
        if not urls:
            raise EmptyGenerationResultError(
                f"В результате нет ссылки на файл: {result}"
            )
        await db_manager.mark_generation_job_ready(job_id, urls)
        return urls

    async def mark_delivered(self, job_id: int) -> None:
        await db_manager.mark_generation_job_delivered(job_id)

    async def fail_and_refund(self, job_id: int, reason: str) -> bool:
        return await db_manager.refund_generation_job(job_id, reason)

    async def defer(self, job_id: int, exc: Exception) -> None:
        await db_manager.record_generation_job_attempt(
            job_id,
            f"{type(exc).__name__}: {exc}",
        )

    def release_local(self, job_id: int | None) -> None:
        if job_id is not None:
            self._active_job_ids.discard(job_id)

    async def _recovery_loop(self) -> None:
        interval = max(15, settings.GENERATION_RECOVERY_INTERVAL_SECONDS)
        while not self._stopping:
            try:
                rows = await db_manager.get_pending_generation_jobs(
                    settings.GENERATION_RECOVERY_BATCH_SIZE
                )
                tasks: list[asyncio.Task[None]] = []
                for row in rows:
                    job_id = int(row["id"])
                    if job_id in self._active_job_ids:
                        continue
                    self._active_job_ids.add(job_id)
                    task = asyncio.create_task(
                        self._recover_job(row),
                        name=f"generation-recovery-{job_id}",
                    )
                    self._recovery_tasks.add(task)
                    task.add_done_callback(self._recovery_tasks.discard)
                    tasks.append(task)
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Ошибка цикла восстановления генераций")
            await asyncio.sleep(interval)

    async def _recover_job(self, row: dict[str, Any]) -> None:
        job_id = int(row["id"])
        try:
            if self._is_expired(row):
                refunded = await self.fail_and_refund(
                    job_id,
                    "Задача не завершилась за допустимое время",
                )
                if refunded:
                    await self._notify_refund(row)
                return

            urls = self._decode_urls(row.get("result_urls"))
            if str(row.get("status")) == "processing":
                request_id = row.get("provider_request_id")
                if not request_id:
                    raise EmptyGenerationResultError(
                        "У сохранённой задачи отсутствует request_id"
                    )
                result = await genapi_client.wait_for_result(
                    str(request_id),
                    timeout=settings.GENAPI_POLL_TIMEOUT,
                    interval=settings.GENAPI_POLL_INTERVAL,
                )
                urls = collect_result_urls(result)
                if not urls:
                    raise EmptyGenerationResultError(
                        "Провайдер завершил задачу без ссылки на файл"
                    )
                await db_manager.mark_generation_job_ready(job_id, urls)

            if not urls:
                raise EmptyGenerationResultError("Сохранённый результат пуст")
            await self._deliver(row, urls)
            await self.mark_delivered(job_id)
            logger.info("Восстановленная генерация %s доставлена", job_id)
        except asyncio.CancelledError:
            raise
        except (GenAPITaskFailedError, EmptyGenerationResultError) as exc:
            refunded = await self.fail_and_refund(
                job_id,
                f"Ошибка восстановленной генерации: {exc}",
            )
            if refunded:
                await self._notify_refund(row)
        except GenAPITaskTimeoutError as exc:
            await self.defer(job_id, exc)
        except Exception as exc:
            await self.defer(job_id, exc)
            logger.warning("Не удалось восстановить генерацию %s: %s", job_id, exc)
        finally:
            self._active_job_ids.discard(job_id)

    async def _deliver(self, row: dict[str, Any], urls: list[str]) -> None:
        if self._bot is None:
            raise RuntimeError("Telegram Bot не подключён к восстановителю")
        chat_id = int(row["chat_id"])
        caption = str(row.get("caption") or "✅ Генерация готова")[:1000]
        kind = GenerationKind(str(row["kind"]))
        if kind == GenerationKind.IMAGE:
            limit = max(1, min(4, int(row.get("result_limit") or 1)))
            for url in urls[:limit]:
                await self._bot.send_photo(chat_id, url, caption=caption)
        else:
            await self._bot.send_video(
                chat_id,
                urls[0],
                caption=caption,
                supports_streaming=True,
            )

    async def _notify_refund(self, row: dict[str, Any]) -> None:
        if self._bot is None:
            return
        amount = int(row.get("token_cost") or 0)
        if str(row.get("charge_source")) == "admin":
            suffix = "Списание для администратора отсутствовало."
        elif str(row.get("charge_source")) == "free_trial":
            suffix = "Бесплатная попытка восстановлена."
        else:
            suffix = f"На баланс возвращено {amount} 💎."
        with contextlib.suppress(Exception):
            await self._bot.send_message(
                int(row["chat_id"]),
                "❌ Сохранённую генерацию не удалось завершить. " + suffix,
            )

    @staticmethod
    def _decode_urls(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if str(item).startswith(("http://", "https://"))]
        try:
            parsed = json.loads(value or "[]")
        except (TypeError, json.JSONDecodeError):
            return []
        return [
            str(item)
            for item in parsed
            if isinstance(item, str) and item.startswith(("http://", "https://"))
        ] if isinstance(parsed, list) else []

    @staticmethod
    def _is_expired(row: dict[str, Any]) -> bool:
        raw = str(row.get("created_at") or "")
        try:
            created = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        except ValueError:
            return False
        age = datetime.now(timezone.utc) - created
        return age.total_seconds() > max(1, settings.GENERATION_MAX_PENDING_HOURS) * 3600


generation_job_service = GenerationJobService()
