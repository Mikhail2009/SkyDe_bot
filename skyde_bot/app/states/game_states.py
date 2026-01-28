from aiogram.fsm.state import StatesGroup, State

class SlotsState(StatesGroup):
    waiting_for_bet = State()  # Единственное состояние - ожидание ставки