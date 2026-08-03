"""Точка запуска Telegram-бота."""
from __future__ import annotations

import asyncio
import signal
import sys
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from database import db_manager, run_migrations
from business_handlers import router as business_router
from generation_handlers import router as generation_router
from handlers import router as main_router
from payment_handlers import router as payment_router
from services.genapi_client import genapi_client
from settings import settings
from token_admin_handlers import router as token_admin_router
from utils import logger


class Application:
    def __init__(self) -> None:
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self._shutdown_requested = False
        self._polling_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        logger.info("🚀 Запуск ШТАБ AI...")
        settings.validate()
        await db_manager.initialize()
        await run_migrations()

        self.bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher()

        # Более узкие роутеры подключаются раньше общего меню.
        self.dp.include_router(token_admin_router)
        self.dp.include_router(payment_router)
        self.dp.include_router(generation_router)
        self.dp.include_router(business_router)
        self.dp.include_router(main_router)
        logger.info("✅ Бот готов к работе")

    async def shutdown(self, signame: str = "") -> None:
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        logger.info("🔄 Завершение работы%s", f" ({signame})" if signame else "")

        if self.dp and self._polling_task and not self._polling_task.done():
            try:
                await self.dp.stop_polling()
                await asyncio.wait_for(self._polling_task, timeout=5)
            except asyncio.TimeoutError:
                self._polling_task.cancel()
            except RuntimeError as exc:
                if "Polling is not started" not in str(exc):
                    logger.error("Ошибка остановки polling: %s", exc)

        try:
            await genapi_client.close()
        except Exception as exc:
            logger.error("Ошибка закрытия GenAPI-клиента: %s", exc)

        try:
            await db_manager.close()
        except Exception as exc:
            logger.error("Ошибка закрытия базы данных: %s", exc)

        if self.bot:
            await self.bot.session.close()

    async def run(self) -> None:
        try:
            await self.initialize()
            loop = asyncio.get_running_loop()

            def request_shutdown(signame: str) -> None:
                if not self._shutdown_requested:
                    asyncio.create_task(self.shutdown(signame))

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, request_shutdown, sig.name)
                except NotImplementedError:
                    pass

            self._polling_task = asyncio.create_task(
                self.dp.start_polling(self.bot, allowed_updates=self.dp.resolve_used_update_types())
            )
            await self._polling_task
        except asyncio.CancelledError:
            logger.info("⏹ Polling остановлен")
        except Exception as exc:
            logger.exception("❌ Критическая ошибка: %s", exc)
            raise
        finally:
            if not self._shutdown_requested:
                await self.shutdown("finally")


async def main() -> None:
    await Application().run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Принудительная остановка")
    except Exception:
        sys.exit(1)
