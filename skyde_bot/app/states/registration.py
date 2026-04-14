from aiogram.fsm.state import StatesGroup, State

class RegistrationState(StatesGroup):
    waiting_for_nickname = State() # Ввод никнейма
    waiting_for_password = State() # Ввод пароля
    waiting_for_birth_date = State() # Дата рождения
    waiting_for_email = State() # Email
    waiting_for_phone = State() # Телефон

class LoginState(StatesGroup):
    waiting_for_nickname = State() # Ввод никнейма при входе
    waiting_for_password = State() # Ввод пароля при входе
