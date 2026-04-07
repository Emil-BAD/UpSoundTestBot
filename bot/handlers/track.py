import re

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.services import yandex_music_service
from bot.states import TrackStates

router = Router(name=__name__)

_YANDEX_TRACK_LINK_RE = re.compile(r"https?://music\.yandex\.[^\s]+", re.IGNORECASE)


@router.message(StateFilter(TrackStates.waiting_link), F.text)
async def track_link_after_button(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    match = _YANDEX_TRACK_LINK_RE.search(text)
    if not match:
        await message.answer(
            "Нужна ссылка на трек Яндекс Музыки. Пример: "
            "<code>https://music.yandex.ru/album/123/track/456</code>",
        )
        return

    link = match.group(0).rstrip(".,;)")
    result = await yandex_music_service.resolve_track_link(link)
    await message.answer(result.text)
    if result.ok:
        await state.clear()


@router.message(F.text.regexp(_YANDEX_TRACK_LINK_RE))
async def yandex_track_direct_link(message: Message) -> None:
    link = message.text.strip().split()[0].rstrip(".,;)")
    result = await yandex_music_service.resolve_track_link(link)
    await message.answer(result.text)
