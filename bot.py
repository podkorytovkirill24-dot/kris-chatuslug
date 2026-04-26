import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import config
from database import db
from handlers.admin import router as admin_router
from handlers.errors import router as errors_router
from handlers.user import router as user_router
from services.rate_limit import RateLimitMiddleware
from services.scheduler import run_broadcast_scheduler


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Запуск бота"),
        ]
    )


async def main() -> None:
    if not config.bot_token:
        raise RuntimeError("Не задан BOT_TOKEN в переменных окружения.")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    await db.init()

    bot = Bot(token=config.bot_token, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())

    rate_limit = RateLimitMiddleware(config.rate_limit_seconds)
    dp.message.middleware(rate_limit)
    dp.callback_query.middleware(rate_limit)

    dp.include_router(user_router)
    dp.include_router(admin_router)
    dp.include_router(errors_router)

    scheduler_task = asyncio.create_task(
        run_broadcast_scheduler(bot, tick_seconds=config.scheduler_tick_seconds)
    )

    await setup_bot_commands(bot)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await scheduler_task
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
