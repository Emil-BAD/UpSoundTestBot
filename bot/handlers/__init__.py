from aiogram import Router

from .start import router as start_router
from .track import router as track_router


def get_routers() -> tuple[Router, ...]:
    return (start_router, track_router)
