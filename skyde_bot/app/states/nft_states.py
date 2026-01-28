from aiogram.fsm.state import StatesGroup, State


class NFTState(StatesGroup):
    """Состояния для работы с NFT и промокодами."""
    waiting_for_promo = State()
    waiting_for_wallet = State()  # НОВОЕ: Ожидание ввода адреса кошелька