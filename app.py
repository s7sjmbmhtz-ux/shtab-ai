import asyncio
import signal
import sys
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from settings import settings
from handlers import router
from ai_service import ai_service
from database import db_manager, run_migrations
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

        await db_manager.initialize()
        logger.info("✅ База данных подключена")

        migration_success = await run_migrations()
        if not migration_success:
            logger.warning("⚠️ Миграции выполнены не полностью")

        from tools import prompt_registry
        from tool_registry import tool_registry
        tool_registry.register_defaults()

        startup_check()
        logger.info("✅ Startup check пройден")

        self.bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )

        self.dp = Dispatcher()
        self.dp.include_router(router)

        logger.info("✅ Бот готов к работе")

    async def shutdown(self, signame: str = "") -> None:
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        
        if signame:
            logger.info(f"🔄 Получен сигнал {signame}, завершение работы...")
        else:
            logger.info("🔄 Завершение работы...")

        # Останавливаем поллинг
        if self.dp and self._polling_task and not self._polling_task.done():
            try:
                self.dp.stop_polling()
                await asyncio.wait_for(self._polling_task, timeout=5.0)
                logger.info("✅ Поллинг остановлен")
            except asyncio.TimeoutError:
                logger.warning("⚠️ Таймаут остановки поллинга")
                self._polling_task.cancel()
            except Exception as e:
                if "Polling is not started" not in str(e):
                    logger.error(f"Ошибка остановки поллинга: {e}")

        try:
            await ai_service.close()
            logger.info("✅ AI Service закрыт")
        except Exception as e:
            logger.error(f"Ошибка закрытия AI Service: {e}")

        try:
            await db_manager.close()
            logger.info("✅ База данных закрыта")
        except Exception as e:
            logger.error(f"Ошибка закрытия БД: {e}")

        if self.bot:
            try:
                await self.bot.session.close()
                logger.info("✅ Сессия бота закрыта")
            except Exception as e:
                logger.error(f"Ошибка закрытия сессии бота: {e}")

        logger.info("👋 Работа завершена")

    async def run(self) -> None:
        try:
            await self.initialize()
            
            # Настраиваем обработчики сигналов
            loop = asyncio.get_event_loop()
            
            def signal_handler(signame: str):
                if not self._shutdown_requested:
                    logger.info(f"⚠️ Получен сигнал {signame}")
                    # Создаём задачу для завершения
                    asyncio.create_task(self.shutdown(signame))

            # Регистрируем обработчики сигналов
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, lambda s=sig.name: signal_handler(s))
                except NotImplementedError:
                    logger.warning(f"Сигнал {sig.name} не поддерживается в этой ОС")

            logger.info("✅ Бот запущен и готов к работе!")
            
            # Запускаем поллинг в отдельной задаче
            self._polling_task = asyncio.create_task(self.dp.start_polling(self.bot))
            await self._polling_task

        except asyncio.CancelledError:
            logger.info("⏹ Задача поллинга отменена")
        except KeyboardInterrupt:
            logger.info("⏹ Получен сигнал прерывания")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            raise
        finally:
            if not self._shutdown_requested:
                await self.shutdown("finally")


async def main():
    app = Application()
    await app.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Принудительная остановка")
    except Exception as e:
        logger.error(f"❌ Фатальная ошибка: {e}")
        sys.exit(1)
