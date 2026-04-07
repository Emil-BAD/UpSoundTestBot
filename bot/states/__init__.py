from aiogram.fsm.state import State, StatesGroup


class TrackStates(StatesGroup):
    """Ожидание ссылки на трек после нажатия кнопки «Трек»."""

    waiting_link = State()
