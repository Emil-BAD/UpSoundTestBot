import logging

from bot.config import get_settings


def setup_logging() -> None:
    settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
