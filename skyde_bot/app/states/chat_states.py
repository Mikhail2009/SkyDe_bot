from aiogram.fsm.state import StatesGroup, State


class ChatState(StatesGroup):
    """Состояния для модуля чатов."""
    waiting_for_username = State()  # Ожидание ввода @username для поиска
    in_active_chat = State()        # Активный диалог с собеседником