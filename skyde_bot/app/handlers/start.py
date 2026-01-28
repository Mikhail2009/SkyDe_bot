from aiogram import Router, types, F, Bot
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from skyde_bot.app.states.registration import RegistrationState
from skyde_bot.app.services.user_services import UserService
from skyde_bot.app.keyboards.inline import main_menu_keyboard
from skyde_bot.app.config import ADMIN_ID
from skyde_bot.app.utils.utils import delete_previous_message, set_last_message_id

router = Router()

WELCOME_TEXT = """Привет, мой дорогой друг!

Рад приветствовать тебя на своем Маркетплейсе. Здесь ты можешь найти разные NFT на твой вкус. Чтобы начать пользоваться нашим ботом-Маркетплейсом, тебе необходимо пройти несложную регистрацию. Она займет всего пару минут и после этого ты получишь доступ ко всем функциям и возможностям нашего сервиса.

Мы также предоставляем возможность общения с администратором, чтобы ты мог задать все интересующие вопросы и получить качественную консультацию.

Наш бот-Маркетплейс создан для замены других NFT Маркетплейсов. Мы стремимся сделать процесс покупки максимально удобным и безопасным для тебя.

Зарегистрируйся прямо сейчас и начни пользоваться всем преимуществам нашего Маркетплейса!

Если у тебя уже есть аккаунт, нажми кнопку "Вход"
"""


@router.message(F.text == "/start")
async def cmd_start(message: types.Message, session: AsyncSession, state: FSMContext):
    await state.clear()

    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(message.from_user.id)

    if user:
        new_message = await message.answer(
            "🏠 <b>Главное меню</b>\n\nДобро пожаловать обратно! Выберите действие:",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, new_message.message_id)
    else:
        await message.answer(WELCOME_TEXT, reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="📝 Регистрация", callback_data="register"),
                 types.InlineKeyboardButton(text="🔐 Вход", callback_data="login")]
            ]
        ))


# ПРИМЕЧАНИЕ: Хендлер main_menu_return теперь в common_handlers.py


@router.callback_query(F.data == "register")
async def start_registration(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(RegistrationState.waiting_for_name)
    await callback.message.answer("Введите ваше имя и фамилию:")


@router.message(RegistrationState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await state.set_state(RegistrationState.waiting_for_birth_date)
    await message.answer("Введите вашу дату рождения (в формате ДД.ММ.ГГГГ):")


@router.message(RegistrationState.waiting_for_birth_date)
async def process_birth_date(message: types.Message, state: FSMContext):
    import re
    from datetime import datetime

    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", message.text):
        await message.answer("Неверный формат. Используйте ДД.ММ.ГГГГ")
        return

    try:
        birth_date = datetime.strptime(message.text, "%d.%m.%Y")
        today = datetime.now()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

        if age < 18:
            await message.answer("Извините, использование сервиса доступно только с 18 лет.")
            await state.clear()
            return
    except ValueError:
        await message.answer("Неверная дата. Попробуйте снова.")
        return

    await state.update_data(birth_date=message.text)
    await state.set_state(RegistrationState.waiting_for_email)
    await message.answer("Введите ваш email:")


@router.message(RegistrationState.waiting_for_email)
async def process_email(message: types.Message, state: FSMContext):
    import re
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", message.text):
        await message.answer("Неверный формат email. Попробуйте снова:")
        return

    await state.update_data(email=message.text)
    await state.set_state(RegistrationState.waiting_for_phone)
    await message.answer("Введите ваш номер телефона в формате +7XXXXXXXXXX:")


@router.message(RegistrationState.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext, session: AsyncSession):
    import re

    if not re.match(r"^\+7\d{10}$", message.text):
        await message.answer("Неверный формат. Введите в формате +7XXXXXXXXXX:")
        return

    await state.update_data(phone=message.text)
    data = await state.get_data()

    user_service = UserService(session)
    try:
        user = await user_service.create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=data["full_name"],
            phone=data["phone"],
            email=data["email"],
            birth_date=data["birth_date"]
        )

        new_message = await message.answer(
            f"✅ Регистрация успешно завершена!\n\n"
            f"📊 Ваш UID: {user.uid}\n"
            f"💰 Начальный баланс: {user.balance_g} G\n\n"
            f"Добро пожаловать в SkyDe!",
            reply_markup=main_menu_keyboard()
        )
        await set_last_message_id(state, new_message.message_id)

        # Уведомление администратору
        await message.bot.send_message(
            ADMIN_ID,
            f"🆕 Новый пользователь!\nUID: {user.uid}\nИмя: {user.full_name}"
        )

    except Exception as e:
        await message.answer(f"Ошибка при регистрации: {e}")

    await state.clear()


@router.callback_query(F.data == "login")
async def login(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await callback.answer()

    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)

    if user:
        new_message = await callback.message.answer(
            "🏠 <b>Главное меню</b>\n\nВы успешно вошли в систему!",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, new_message.message_id)
    else:
        await callback.message.answer("Аккаунт не найден. Зарегистрируйтесь.",
                                      reply_markup=types.InlineKeyboardMarkup(
                                          inline_keyboard=[
                                              [types.InlineKeyboardButton(text="📝 Регистрация",
                                                                          callback_data="register")]
                                          ]
                                      ))