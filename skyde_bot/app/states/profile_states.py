from aiogram.fsm.state import StatesGroup, State

class ProfileState(StatesGroup):
    waiting_for_avatar = State()
    waiting_for_new_full_name = State()
    waiting_for_new_phone = State()
    waiting_for_new_email = State()
    waiting_for_new_wallet = State()  # ← НОВОЕ СОСТОЯНИЕ
    waiting_for_question = State()