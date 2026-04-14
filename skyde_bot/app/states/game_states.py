# skyde_bot/app/states/game_states.py
from aiogram.fsm.state import StatesGroup, State

class SlotsState(StatesGroup):
    waiting_for_bet = State()

class DiceState(StatesGroup):
    waiting_for_bet = State()          # Ожидание ставки (базовый режим)
    waiting_for_bet_amount = State()   # Ожидание суммы ставки (для угадывания)
    waiting_for_exact_number = State() # Ожидание точного числа для угадывания