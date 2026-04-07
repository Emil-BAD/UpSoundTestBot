import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class BaseLoggingMiddleware(BaseMiddleware):
    """Simple middleware scaffold for request-level logging."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        logging.getLogger(__name__).debug("Incoming event: %s", type(event).__name__)
        return await handler(event, data)
