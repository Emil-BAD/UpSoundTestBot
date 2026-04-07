import asyncio
import logging
from urllib.parse import urlparse

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


def create_telegram_session(proxy_url: str | None) -> AiohttpSession:
    """Create Telegram session with safe fallback to direct mode."""
    if not proxy_url:
        return AiohttpSession()

    parsed = urlparse(proxy_url)
    if parsed.scheme not in {"http", "https", "socks5", "socks5h"}:
        logging.getLogger(__name__).warning(
            "Invalid PROXY_URL scheme '%s'. Telegram will run without proxy.",
            parsed.scheme or "empty",
        )
        return AiohttpSession()

    return AiohttpSession(proxy=proxy_url)


async def start() -> None:
    setup_logging()
    settings = get_settings()

    session = create_telegram_session(settings.telegram_proxy_url)
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
