from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv
import os


load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    log_level: str = "INFO"
    # Только для aiogram → Telegram Bot API.
    telegram_proxy_url: str | None = None
    # Только для запросов к API Яндекс Музыки.
    yandex_proxy_url: str | None = None
    # Опционально: OAuth-токен для fallback POST /tracks, если GET альбома недоступен.
    yandex_music_token: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    telegram_proxy_url = os.getenv("PROXY_URL", "").strip() or None
    yandex_proxy_url = os.getenv("YANDEX_PROXY_URL", "").strip() or None
    yandex_music_token = os.getenv("YANDEX_MUSIC_TOKEN", "").strip() or None

    if not bot_token:
        raise ValueError("BOT_TOKEN is not set. Check your .env file.")

    return Settings(
        bot_token=bot_token,
        log_level=log_level,
        telegram_proxy_url=telegram_proxy_url,
        yandex_proxy_url=yandex_proxy_url,
        yandex_music_token=yandex_music_token,
    )
