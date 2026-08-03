import asyncio
import signal
import sys
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from settings import settings
from generation_handlers import router as generation_router
from token_admin_handlers import router as token_admin_router
from handlers import router as legacy_router
from ai_service import ai_service
from database import db_manager, run_migrations
from services.genapi_client import genapi_client
from startup_check import startup_check
from utils import logger


class Application:
    def __init__(self):
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self._shutdown_requested = False
        self._polling_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        logger.info("🚀 Запуск ШТАБ AI...")
        settings.validate()
        await db_manager.initialize()
        logger.info("✅ База данных подключена")

        migration_success = await run_migrations()
        if not migration_success:
            logger.warning("⚠️ Миграции выполнены не полностью")

        from tool_registry import tool_registry
        tool_registry.register_defaults()
        startup_check()

        self.bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher()
        # Новый роутер подключён первым и перехватывает обновлённые разделы.
        self.dp.include_router(token_admin_router)
        self.dp.include_router(generation_router)
        self.dp.include_router(legacy_router)
        logger.info("✅ Бот готов к работе")

    async def shutdown(self, signame: str = "") -> None:
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        logger.info("🔄 Завершение работы%s", f" ({signame})" if signame else "")

        if self.dp and self._polling_task and not self._polling_task.done():
            try:
                await self.dp.stop_polling()
                await asyncio.wait_for(self._polling_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._polling_task.cancel()
            except RuntimeError as exc:
                if "Polling is not started" not in str(exc):
                    logger.error("Ошибка остановки поллинга: %s", exc)

        for closer, name in (
            (ai_service.close, "AI Service"),
            (genapi_client.close, "GenAPI client"),
            (db_manager.close, "БД"),
        ):
            try:
                await closer()
                logger.info("✅ %s закрыт", name)
            except Exception as exc:
                logger.error("Ошибка закрытия %s: %s", name, exc)

        if self.bot:
            await self.bot.session.close()

    async def run(self) -> None:
        try:
            await self.initialize()
            loop = asyncio.get_running_loop()

            def signal_handler(signame: str) -> None:
                if not self._shutdown_requested:
                    asyncio.create_task(self.shutdown(signame))

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, lambda s=sig.name: signal_handler(s))
                except NotImplementedError:
                    pass

            self._polling_task = asyncio.create_task(self.dp.start_polling(self.bot))
            await self._polling_task
        except asyncio.CancelledError:
            logger.info("⏹ Поллинг остановлен")
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
