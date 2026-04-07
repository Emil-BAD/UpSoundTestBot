from .parser_service import ParserService
from .yandex_music_service import (
    TrackInfo,
    TrackLinkResult,
    YandexMusicService,
)

parser_service = ParserService()
yandex_music_service = YandexMusicService()

__all__ = (
    "ParserService",
    "YandexMusicService",
    "TrackInfo",
    "TrackLinkResult",
    "parser_service",
    "yandex_music_service",
)
