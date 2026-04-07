from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import main_menu_keyboard
from bot.services import parser_service
from bot.states import TrackStates

router = Router(name=__name__)


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    welcome_text = parser_service.build_start_message(user_name=message.from_user.full_name)
    await message.answer(welcome_text, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "track_request")
async def track_button_handler(callback: CallbackQuery, state: FSMContext) -> None:
    instruction = parser_service.build_track_instruction_message()
    await callback.message.answer(instruction)
    await state.set_state(TrackStates.waiting_link)
    await callback.answer()
