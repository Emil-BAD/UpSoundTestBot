from __future__ import annotations

from dataclasses import dataclass
import html
import logging
import re
from urllib.parse import urlparse

from yandex_music import ClientAsync, Track
from yandex_music.exceptions import (
    BadRequestError,
    NetworkError,
    NotFoundError,
    TimedOutError,
    UnauthorizedError,
    YandexMusicError,
)
from yandex_music.utils.request_async import Request

from bot.config import get_settings
from bot.utils.formatters import format_duration

log = logging.getLogger(__name__)


class YandexMusicServiceError(Exception):
    """Базовая ошибка сервиса Яндекс Музыки."""


class InvalidYandexMusicLinkError(YandexMusicServiceError):
    """Некорректная ссылка на трек."""


class TrackNotFoundError(YandexMusicServiceError):
    """Трек не найден в API."""


class TrackParsingError(YandexMusicServiceError):
    """Не удалось собрать метаданные из ответа API."""


@dataclass(frozen=True)
class TrackInfo:
    title: str
    artist: str
    duration_seconds: int


@dataclass(frozen=True)
class TrackLinkResult:
    """Результат обработки ссылки для отправки пользователю."""

    ok: bool
    text: str


_ALBUM_TRACK_PATH_RE = re.compile(
    r"/album/(?P<album_id>\d+)/track/(?P<track_id>\d+)",
    re.IGNORECASE,
)


class YandexMusicService:
    """
    Метаданные трека через библиотеку yandex-music.

    Без токена: запрос альбома GET /albums/{id}/with-tracks и поиск трека в volumes.
    С токеном (опционально): дополнительный fallback POST /tracks по составному id.
    """

    def __init__(self) -> None:
        self._client: ClientAsync | None = None

    def _get_client(self) -> ClientAsync:
        if self._client is None:
            settings = get_settings()
            # Отдельный прокси для API Яндекс Музыки.
            request = Request(proxy_url=settings.yandex_proxy_url)
            self._client = ClientAsync(
                token=settings.yandex_music_token,
                request=request,
                language="ru",
            )
        return self._client

    @staticmethod
    def _parse_album_and_track_ids(url: str) -> tuple[int, int]:
        parsed = urlparse(url.strip())

        if parsed.scheme not in {"http", "https"}:
            raise InvalidYandexMusicLinkError(
                "Ссылка должна начинаться с http:// или https://."
            )

        if not parsed.netloc.lower().startswith("music.yandex."):
            raise InvalidYandexMusicLinkError(
                "Ожидается ссылка с домена music.yandex.*."
            )

        match = _ALBUM_TRACK_PATH_RE.search(parsed.path)
        if not match:
            raise InvalidYandexMusicLinkError(
                "Ссылка должна содержать путь вида /album/<id>/track/<id>."
            )

        return int(match.group("album_id")), int(match.group("track_id"))

    @staticmethod
    def _numeric_track_id(raw: object) -> int | None:
        if raw is None:
            return None
        if isinstance(raw, int):
            return raw
        try:
            return int(str(raw).split(":", maxsplit=1)[0])
        except ValueError:
            return None

    @classmethod
    def _find_track_in_album(cls, album, wanted_track_id: int) -> Track | None:
        """Ищет трек в volumes альбома по id / real_id."""
        for volume in album.volumes or []:
            for t in volume:
                if not isinstance(t, Track):
                    continue
                for raw in (t.id, getattr(t, "real_id", None)):
                    if cls._numeric_track_id(raw) == wanted_track_id:
                        return t
        return None

    @staticmethod
    def _track_to_info(track: Track) -> TrackInfo:
        if not isinstance(track, Track):
            raise TrackParsingError("Неожиданный тип объекта трека.")

        title = (track.title or "").strip() or "—"
        artists = track.artists or []
        names: list[str] = []
        for a in artists:
            if a is not None and getattr(a, "name", None):
                names.append(str(a.name).strip())
        artist = ", ".join(names) if names else "—"

        duration_ms = track.duration_ms
        if duration_ms is None:
            raise TrackParsingError("В ответе API нет длительности трека.")
        seconds = max(int(duration_ms) // 1000, 0)

        return TrackInfo(title=title, artist=artist, duration_seconds=seconds)

    @staticmethod
    def _format_success(track: TrackInfo) -> str:
        safe_title = html.escape(track.title)
        safe_artist = html.escape(track.artist)
        return (
            "<b>Информация о треке</b>\n"
            f"Название: {safe_title}\n"
            f"Исполнитель: {safe_artist}\n"
            f"Длительность: {format_duration(track.duration_seconds)}"
        )

    async def _load_track_via_album(
        self, client: ClientAsync, album_id: int, track_id: int
    ) -> Track | None:
        album = await client.albums_with_tracks(album_id)
        if album is None:
            return None
        if getattr(album, "error", None):
            log.debug("albums_with_tracks: album error=%s id=%s", album.error, album_id)
            return None
        return self._find_track_in_album(album, track_id)

    async def _load_track_via_tracks_endpoint(
        self, client: ClientAsync, compound_id: str
    ) -> Track | None:
        tracks = await client.tracks(compound_id)
        if not tracks:
            return None
        raw = tracks[0]
        if getattr(raw, "error", None):
            log.debug("tracks(): объект с error=%s id=%s", raw.error, compound_id)
            return None
        return raw if isinstance(raw, Track) else None

    @staticmethod
    def _is_http_451_legal_block(exc: BaseException) -> bool:
        """HTTP 451 — геоблокировка / недоступность API из региона (библиотека кидает NetworkError)."""
        text = str(exc).lower()
        return "451" in text or "unavailable for legal reasons" in text

    def _api_failure_result(self, compound_id: str, exc: Exception) -> TrackLinkResult:
        """Перевод ошибок API в ответ пользователю (без Unauthorized — обрабатывается отдельно)."""
        if isinstance(exc, NotFoundError):
            log.debug("API: не найдено (404): %s detail=%s", compound_id, exc)
            return TrackLinkResult(ok=False, text="Трек не найден. Проверь ссылку.")
        if isinstance(exc, BadRequestError):
            log.debug("API: неверный запрос (400): %s detail=%s", compound_id, exc)
            return TrackLinkResult(
                ok=False,
                text="Не удалось запросить данные: неверные параметры.",
            )
        if isinstance(exc, TimedOutError):
            log.debug("API: таймаут: %s detail=%s", compound_id, exc)
            return TrackLinkResult(
                ok=False,
                text="Превышено время ожидания ответа от Яндекс Музыки. Попробуйте позже.",
            )
        if isinstance(exc, NetworkError):
            if self._is_http_451_legal_block(exc):
                log.debug("API: геоблокировка 451: %s detail=%s", compound_id, exc)
                return TrackLinkResult(
                    ok=False,
                    text=(
                        "Яндекс Музыка недоступна из вашего региона или сети (код 451 — "
                        "ограничение по закону/географии). Используйте VPN с выходом в регион, "
                        "где доступен сервис (PROXY_URL в проекте влияет только на Telegram, не на Яндекс)."
                    ),
                )
            log.debug("API: сеть: %s detail=%s", compound_id, exc)
            return TrackLinkResult(
                ok=False,
                text="Ошибка сети при обращении к Яндекс Музыке. Попробуйте позже.",
            )
        if isinstance(exc, YandexMusicError):
            log.debug("API: YandexMusicError: %s detail=%s", compound_id, exc)
            return TrackLinkResult(
                ok=False,
                text="Ошибка при получении данных трека. Попробуйте позже.",
            )
        raise exc

    async def resolve_track_link(self, url: str) -> TrackLinkResult:
        """Разобрать ссылку, получить трек, вернуть готовый текст для пользователя."""
        try:
            album_id, track_id = self._parse_album_and_track_ids(url)
        except InvalidYandexMusicLinkError as exc:
            log.debug("Невалидная ссылка: %s", exc)
            return TrackLinkResult(
                ok=False,
                text=f"Некорректная ссылка: {exc}",
            )

        compound_id = f"{track_id}:{album_id}"
        client = self._get_client()
        settings = get_settings()

        raw_track: Track | None = None

        try:
            raw_track = await self._load_track_via_album(client, album_id, track_id)
        except UnauthorizedError as exc:
            log.debug("API: 401/403 (альбом): %s detail=%s", compound_id, exc)
            if not settings.yandex_music_token:
                return TrackLinkResult(
                    ok=False,
                    text=(
                        "Яндекс Музыка отклонила запрос без авторизации. "
                        "Попробуйте другую сеть/VPN или задайте YANDEX_MUSIC_TOKEN в .env."
                    ),
                )
        except YandexMusicError as exc:
            return self._api_failure_result(compound_id, exc)

        if raw_track is None and settings.yandex_music_token:
            try:
                raw_track = await self._load_track_via_tracks_endpoint(client, compound_id)
            except UnauthorizedError as exc:
                log.debug("API: 401/403 (tracks): %s detail=%s", compound_id, exc)
                return TrackLinkResult(
                    ok=False,
                    text="Доступ к API отклонён. Проверьте YANDEX_MUSIC_TOKEN.",
                )
            except YandexMusicError as exc:
                return self._api_failure_result(compound_id, exc)

        if raw_track is None:
            log.debug("Трек не найден: album_id=%s track_id=%s", album_id, track_id)
            return TrackLinkResult(
                ok=False,
                text="Трек не найден в альбоме. Проверь ссылку.",
            )

        try:
            info = self._track_to_info(raw_track)
        except TrackParsingError as exc:
            log.debug("Не удалось разобрать поля трека: %s", exc)
            return TrackLinkResult(
                ok=False,
                text="Не удалось прочитать данные трека из ответа API.",
            )

        return TrackLinkResult(ok=True, text=self._format_success(info))
