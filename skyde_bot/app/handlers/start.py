import re
from datetime import datetime

from aiogram import Router, types, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from skyde_bot.app.states.registration import RegistrationState, LoginState
from skyde_bot.app.services.user_services import UserService
from skyde_bot.app.keyboards.inline import main_menu_keyboard
from skyde_bot.app.config import ADMIN_ID
from skyde_bot.app.utils.utils import delete_previous_message, set_last_message_id

router = Router()

# ─────────────────────────────────────────
# Текст приветствия
# ─────────────────────────────────────────
WELCOME_TEXT = (
    "👋 Привет! Добро пожаловать в <b>SkyDe Marketplace</b>.\n\n"
    "Здесь ты можешь покупать и продавать NFT, общаться с другими пользователями "
    "и испытывать удачу в играх.\n\n"
    "Чтобы начать — зарегистрируйся или войди в существующий аккаунт."
)

# ─────────────────────────────────────────
# Клавиатуры
# ─────────────────────────────────────────

def welcome_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Регистрация", callback_data="register"),
            InlineKeyboardButton(text="🔐 Вход", callback_data="login"),
        ]
    ])


def cancel_keyboard(callback_data: str = "cancel_auth") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=callback_data)]
    ])


# ─────────────────────────────────────────
# /start
# ─────────────────────────────────────────
@router.message(F.text == "/start")
async def cmd_start(message: types.Message, session: AsyncSession, state: FSMContext):
    await state.clear()

    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(message.from_user.id)

    if user:
        new_msg = await message.answer(
            f"🏠 <b>Главное меню</b>\n\nДобро пожаловать, <b>{user.nickname}</b>! Выберите действие:",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, new_msg.message_id)
    else:
        await message.answer(
            WELCOME_TEXT,
            reply_markup=welcome_keyboard(),
            parse_mode='HTML'
        )


# ─────────────────────────────────────────
# РЕГИСТРАЦИЯ — шаг 1: никнейм
# ─────────────────────────────────────────
@router.callback_query(F.data == "register")
async def start_registration(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(RegistrationState.waiting_for_nickname)

    await callback.message.edit_text(
        "📝 <b>Регистрация — шаг 1 из 5</b>\n\n"
        "Придумайте уникальный <b>никнейм</b>.\n\n"
        "📌 <b>Требования:</b>\n"
        "• Только латинские буквы (a–z, A–Z) и цифры (0–9)\n"
        "• От 3 до 20 символов\n"
        "• Не может начинаться с цифры\n\n"
        "✏️ Введите никнейм:",
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )


# ─────────────────────────────────────────
# РЕГИСТРАЦИЯ — шаг 2: пароль
# ─────────────────────────────────────────
@router.message(RegistrationState.waiting_for_nickname)
async def process_nickname(message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot):
    await delete_previous_message(state, message.chat.id, bot)
    await message.delete()

    nickname = message.text.strip()

    # Валидация формата
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9]{2,19}$', nickname):
        err = await message.answer(
            "❌ <b>Неверный формат никнейма</b>\n\n"
            "• Только латинские буквы и цифры\n"
            "• От 3 до 20 символов\n"
            "• Должен начинаться с буквы\n\n"
            "Попробуйте ещё раз:",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, err.message_id)
        return

    # Проверка уникальности
    user_service = UserService(session)
    if await user_service.is_nickname_taken(nickname):
        err = await message.answer(
            f"❌ Никнейм <b>{nickname}</b> уже занят.\n\n"
            "Придумайте другой:",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, err.message_id)
        return

    # Никнейм свободен — переходим дальше
    await state.update_data(nickname=nickname)
    await state.set_state(RegistrationState.waiting_for_password)

    ok = await message.answer(
        f"✅ Никнейм <b>{nickname}</b> свободен!\n\n"
        "📝 <b>Регистрация — шаг 2 из 5</b>\n\n"
        "Придумайте <b>пароль</b>.\n\n"
        "📌 <b>Требования:</b>\n"
        "• От 6 до 32 символов\n"
        "• Латинские буквы и цифры\n\n"
        "🔒 Введите пароль:",
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, ok.message_id)


# ─────────────────────────────────────────
# РЕГИСТРАЦИЯ — шаг 3: дата рождения
# ─────────────────────────────────────────
@router.message(RegistrationState.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext, bot: Bot):
    await delete_previous_message(state, message.chat.id, bot)
    await message.delete()

    password = message.text.strip()

    if not re.match(r'^[a-zA-Z0-9]{6,32}$', password):
        err = await message.answer(
            "❌ <b>Неверный формат пароля</b>\n\n"
            "• От 6 до 32 символов\n"
            "• Только латинские буквы и цифры\n\n"
            "Попробуйте ещё раз:",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, err.message_id)
        return

    await state.update_data(password=password)
    await state.set_state(RegistrationState.waiting_for_birth_date)

    ok = await message.answer(
        "🔒 Пароль сохранён!\n\n"
        "📝 <b>Регистрация — шаг 3 из 5</b>\n\n"
        "Введите вашу <b>дату рождения</b> в формате ДД.ММ.ГГГГ\n\n"
        "💡 Пример: <code>15.03.1995</code>",
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, ok.message_id)


# ─────────────────────────────────────────
# РЕГИСТРАЦИЯ — шаг 4: email
# ─────────────────────────────────────────
@router.message(RegistrationState.waiting_for_birth_date)
async def process_birth_date(message: types.Message, state: FSMContext, bot: Bot):
    await delete_previous_message(state, message.chat.id, bot)
    await message.delete()

    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", message.text):
        err = await message.answer(
            "❌ Неверный формат. Используйте <code>ДД.ММ.ГГГГ</code>",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, err.message_id)
        return

    try:
        birth_date = datetime.strptime(message.text, "%d.%m.%Y")
        today = datetime.now()
        age = today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )
        if age < 18:
            err = await message.answer(
                "❌ Использование сервиса доступно только с 18 лет.",
                reply_markup=cancel_keyboard(),
                parse_mode='HTML'
            )
            await set_last_message_id(state, err.message_id)
            await state.clear()
            return
    except ValueError:
        err = await message.answer(
            "❌ Неверная дата. Попробуйте снова.",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, err.message_id)
        return

    await state.update_data(birth_date=message.text)
    await state.set_state(RegistrationState.waiting_for_email)

    ok = await message.answer(
        "📝 <b>Регистрация — шаг 4 из 5</b>\n\n"
        "Введите ваш <b>Email</b>:",
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, ok.message_id)


# ─────────────────────────────────────────
# РЕГИСТРАЦИЯ — шаг 5: телефон → создание
# ─────────────────────────────────────────
@router.message(RegistrationState.waiting_for_email)
async def process_email(message: types.Message, state: FSMContext, bot: Bot):
    await delete_previous_message(state, message.chat.id, bot)
    await message.delete()

    email = message.text.strip()
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        err = await message.answer(
            "❌ Неверный формат email. Попробуйте снова:",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, err.message_id)
        return

    await state.update_data(email=email)
    await state.set_state(RegistrationState.waiting_for_phone)

    ok = await message.answer(
        "📝 <b>Регистрация — шаг 5 из 5</b>\n\n"
        "Введите номер телефона в формате <code>+7XXXXXXXXXX</code>:",
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, ok.message_id)


@router.message(RegistrationState.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot):
    await delete_previous_message(state, message.chat.id, bot)
    await message.delete()

    phone = message.text.strip()
    if not re.match(r"^\+7\d{10}$", phone):
        err = await message.answer(
            "❌ Неверный формат. Введите в формате <code>+7XXXXXXXXXX</code>:",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, err.message_id)
        return

    data = await state.get_data()
    user_service = UserService(session)

    try:
        user = await user_service.create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            nickname=data["nickname"],
            password=data["password"],
            phone=phone,
            email=data["email"],
            birth_date=data["birth_date"]
        )

        await state.clear()

        new_msg = await message.answer(
            f"🎉 <b>Регистрация завершена!</b>\n\n"
            f"👤 Ваш никнейм: <b>{user.nickname}</b>\n"
            f"🆔 UID: <code>{user.uid}</code>\n"
            f"💰 Начальный баланс: <b>{user.balance_g} G</b>\n\n"
            f"Добро пожаловать в SkyDe!",
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, new_msg.message_id)

        # Уведомление администратору
        try:
            await message.bot.send_message(
                ADMIN_ID,
                f"🆕 Новый пользователь!\n"
                f"Никнейм: {user.nickname}\n"
                f"UID: {user.uid}"
            )
        except Exception:
            pass

    except Exception as e:
        await state.clear()
        await message.answer(f"❌ Ошибка при регистрации: {e}")


# ─────────────────────────────────────────
# ВХОД — шаг 1: никнейм
# ─────────────────────────────────────────
@router.callback_query(F.data == "login")
async def start_login(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(LoginState.waiting_for_nickname)

    await callback.message.edit_text(
        "🔐 <b>Вход в аккаунт</b>\n\n"
        "Введите ваш <b>никнейм</b>:",
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )


# ─────────────────────────────────────────
# ВХОД — шаг 2: пароль
# ─────────────────────────────────────────
@router.message(LoginState.waiting_for_nickname)
async def login_process_nickname(message: types.Message, state: FSMContext,
                                 session: AsyncSession, bot: Bot):
    await delete_previous_message(state, message.chat.id, bot)
    await message.delete()

    nickname = message.text.strip()
    user_service = UserService(session)

    # Проверяем, существует ли такой никнейм
    if not await user_service.is_nickname_taken(nickname):
        err = await message.answer(
            f"❌ Пользователь с никнеймом <b>{nickname}</b> не найден.\n\n"
            "Проверьте правильность ввода или зарегистрируйтесь:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Регистрация", callback_data="register")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_auth")],
            ]),
            parse_mode='HTML'
        )
        await set_last_message_id(state, err.message_id)
        await state.clear()
        return

    await state.update_data(login_nickname=nickname)
    await state.set_state(LoginState.waiting_for_password)

    ok = await message.answer(
        f"👤 Никнейм <b>{nickname}</b> найден!\n\n"
        "🔒 Введите <b>пароль</b>:",
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, ok.message_id)


# ─────────────────────────────────────────
# ВХОД — финал: проверка пароля
# ─────────────────────────────────────────
@router.message(LoginState.waiting_for_password)
async def login_process_password(message: types.Message, state: FSMContext,
                                 session: AsyncSession, bot: Bot):
    await delete_previous_message(state, message.chat.id, bot)
    await message.delete()

    data = await state.get_data()
    nickname = data.get("login_nickname", "")
    password = message.text.strip()

    user_service = UserService(session)
    user = await user_service.verify_login(nickname, password)

    if not user:
        err = await message.answer(
            "❌ <b>Неверный пароль.</b>\n\n"
            "Попробуйте ещё раз или вернитесь на главную:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔁 Попробовать снова", callback_data="login")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_auth")],
            ]),
            parse_mode='HTML'
        )
        await set_last_message_id(state, err.message_id)
        await state.clear()
        return

    # Привязываем текущий Telegram-аккаунт к найденному пользователю
    # (на случай если пользователь сменил устройство)
    await user_service.update_field(
        telegram_id=user.telegram_id,
        field_name='telegram_id',
        new_value=str(message.from_user.id)
    )

    await state.clear()

    new_msg = await message.answer(
        f"✅ <b>Добро пожаловать, {user.nickname}!</b>\n\n"
        f"💰 Баланс: <b>{user.balance_g} G</b>",
        reply_markup=main_menu_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_msg.message_id)


# ─────────────────────────────────────────
# Отмена авторизации
# ─────────────────────────────────────────
@router.callback_query(F.data == "cancel_auth")
async def cancel_auth(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()

    await callback.message.edit_text(
        WELCOME_TEXT,
        reply_markup=welcome_keyboard(),
        parse_mode='HTML'
    )
