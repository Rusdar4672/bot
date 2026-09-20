import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.handlers import admin, menu, orders, start
from config.settings import settings

logger = logging.getLogger(__name__)


def create_bot() -> tuple[Bot, Dispatcher]:
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(orders.router)
    dp.include_router(admin.router)
    return bot, dp


async def run_bot() -> None:
    bot, dp = create_bot()
    logger.info("Bot starting polling...")
    await dp.start_polling(bot)
