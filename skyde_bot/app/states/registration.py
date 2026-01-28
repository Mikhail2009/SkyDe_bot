from aiogram.fsm.state import StatesGroup, State

class RegistrationState(StatesGroup):
    waiting_for_name = State()
    waiting_for_birth_date = State()
    waiting_for_email = State()
    waiting_for_phone = State()

