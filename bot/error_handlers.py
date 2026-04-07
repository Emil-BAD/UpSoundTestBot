"""Глобальная регистрация логирования необработанных исключений в обработчиках aiogram."""

from __future__ import annotations

import logging

from aiogram import Dispatcher
from aiogram.types import ErrorEvent

log = logging.getLogger("bot.errors")


def register_error_handlers(dp: Dispatcher) -> None:
    @dp.errors()
    async def _log_unhandled_exception(event: ErrorEvent) -> bool:
        update_id = getattr(event.update, "update_id", None)
        log.error(
            "Необработанное исключение в обработчике обновления (update_id=%s): %s",
            update_id,
            event.exception,
            exc_info=(type(event.exception), event.exception, event.exception.__traceback__),
        )
        # Возврат не-UNHANDLED подавляет повторный raise в ErrorsMiddleware — бот продолжает polling.
        return True
