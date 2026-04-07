import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError

from bot.config import get_settings
from bot.error_handlers import register_error_handlers
from bot.handlers import get_routers
from bot.middlewares import BaseLoggingMiddleware
from bot.utils import setup_logging


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(BaseLoggingMiddleware())
    register_error_handlers(dp)

    for router in get_routers():
        dp.include_router(router)

    return dp


async def start() -> None:
    setup_logging()
    settings = get_settings()

    session = (
        AiohttpSession(proxy=settings.telegram_proxy_url)
        if settings.telegram_proxy_url
        else AiohttpSession()
    )
    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = create_dispatcher()

    logging.getLogger(__name__).info("Bot is starting...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except TelegramNetworkError:
        logging.getLogger(__name__).exception(
            "Telegram API is unreachable. Check internet/proxy/firewall settings."
        )
        raise


def run() -> None:
    asyncio.run(start())
