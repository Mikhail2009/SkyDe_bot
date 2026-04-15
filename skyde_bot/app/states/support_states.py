# skyde_bot/app/states/support_states.py
from aiogram.fsm.state import StatesGroup, State

class SupportState(StatesGroup):
    waiting_for_question = State()