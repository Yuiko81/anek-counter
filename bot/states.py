from aiogram.fsm.state import State, StatesGroup


class AddEventState(StatesGroup):
    waiting_for_minutes = State()
    waiting_for_rating = State()

