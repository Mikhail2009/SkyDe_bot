import re
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, PhotoSize, CallbackQuery
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from skyde_bot.app.services.user_services import UserService
from skyde_bot.app.keyboards.inline import profile_keyboard, settings_keyboard, games_menu_keyboard, main_menu_keyboard
from skyde_bot.app.states.profile_states import ProfileState
from skyde_bot.app.utils.utils import delete_previous_message, set_last_message_id

router = Router()


# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ВАЛИДАЦИИ КОШЕЛЬКА ---
def is_valid_wallet(address: str) -> bool:
    """Валидация адреса TON кошелька."""
    # TON кошелек (EQ... или UQ...)
    # Формат: 48 символов (EQ/UQ + 46 символов base64url)
    if re.match(r'^(EQ|UQ)[a-zA-Z0-9_-]{46}$', address):
        return True
    return False


# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ВОЗВРАТА В НАСТРОЙКИ ---
async def show_settings(input_obj: types.Message | types.CallbackQuery, state: FSMContext, bot: Bot):
    """Перенаправляет в меню настроек, удаляя предыдущее сообщение бота."""
    if isinstance(input_obj, types.CallbackQuery):
        message = input_obj.message
        await input_obj.answer()
    else:
        message = input_obj

    # Удаляем предыдущее сообщение бота (подтверждение, ошибка и т.д.)
    await delete_previous_message(state, message.chat.id, bot)

    new_message = await message.answer(
        text="""
⚙️ <b>Настройки профиля</b>

Выберите поле, которое хотите изменить.
        """,
        reply_markup=settings_keyboard(),
        parse_mode='HTML'
    )
    # Сохраняем ID нового сообщения
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР /cancel ДЛЯ ОТМЕНЫ FSM-СОСТОЯНИЙ ---
@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext, bot: Bot):
    """Обработка команды /cancel для отмены любого FSM-состояния в профиле."""
    current_state = await state.get_state()

    # Проверяем, находится ли пользователь в одном из состояний профиля
    if current_state is None:
        await message.answer(
            "❌ Нет активных действий для отмены.",
            reply_markup=main_menu_keyboard()
        )
        return

    # Удаляем команду пользователя
    await message.delete()

    # Удаляем предыдущее сообщение бота
    await delete_previous_message(state, message.chat.id, bot)

    # Сбрасываем состояние
    await state.clear()

    # Отправляем подтверждение
    confirm_msg = await message.answer(
        "✅ Действие отменено.",
        parse_mode='HTML'
    )

    # Небольшая задержка для читаемости
    import asyncio
    await asyncio.sleep(1)
    await confirm_msg.delete()

    # Возвращаем в настройки профиля
    await show_settings(message, state, bot)


# --- 1. ГЛАВНЫЙ ХЕНДЛЕР ПРОФИЛЯ (callback_data="profile") ---
@router.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Показать профиль пользователя с поддержкой аватара."""
    await callback.answer()

    user_service = UserService(session)
    session.expire_all()
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)

    if not user:
        await callback.message.answer("Пожалуйста, зарегистрируйтесь: /start")
        return

    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Удаляем предыдущее сообщение ПЕРЕД отправкой профиля
    await delete_previous_message(state, callback.message.chat.id, bot)

    # Форматирование
    birth_date = user.birth_date.strftime("%d.%m.%Y") if user.birth_date else "Не указана"

    # Форматирование кошелька
    if user.crypto_wallet:
        wallet_display = f"<code>{user.crypto_wallet[:6]}...{user.crypto_wallet[-6:]}</code>"
    else:
        wallet_display = "Не подключен"

    profile_text = (
        f"<b>Ваш профиль:</b>\n\n"
        f"✅ <b>UID:</b> <code>{user.uid}</code>\n"
        f"👤 <b>Имя:</b> <code>{user.full_name}</code>\n"
        f"📅 <b>Дата рождения:</b> <code>{birth_date}</code>\n"
        f"📞 <b>Номер:</b> <code>{user.phone}</code>\n"
        f"✉️ <b>Email:</b> <code>{user.email}</code>\n"
        f"💼 <b>Кошелёк:</b> {wallet_display}\n"
        f"⭐️ <b>Премиум Rate:</b> <code>{user.premium_rate}</code>\n"
        f"🆔 <b>Telegram ID:</b> <code>{user.telegram_id}</code>\n"
        f"💰 <b>Баллы:</b> <code>{user.balance_g}</code>\n"
    )

    # Логика вывода с аватаром или без
    if user.avatar_file_id:
        new_message = await callback.message.answer_photo(
            photo=user.avatar_file_id,
            caption=profile_text,
            reply_markup=profile_keyboard(),
            parse_mode='HTML'
        )
    else:
        new_message = await callback.message.answer(
            text=profile_text,
            reply_markup=profile_keyboard(),
            parse_mode='HTML'
        )
    # Сохраняем ID сообщения профиля (теперь оно будет удалено при возврате)
    await set_last_message_id(state, new_message.message_id)

# --- 2. ХЕНДЛЕР: Показать Настройки (callback_data="settings") ---
@router.callback_query(F.data == "settings")
async def start_show_settings(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Показать меню настроек с кнопками для изменения данных."""
    # Удаляем предыдущее сообщение (профиль)
    await delete_previous_message(state, callback.message.chat.id, bot)
    # Используем вспомогательную функцию для отправки меню настроек
    await show_settings(callback, state, bot)

# --- 3. ИЗМЕНЕНИЕ АВАТАРА (Начало) ---
@router.callback_query(F.data == "change_icon")
async def start_avatar_change(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()

    # 1. Удаляем предыдущее общение (меню настроек)
    await delete_previous_message(state, callback.message.chat.id, bot)

    await state.set_state(ProfileState.waiting_for_avatar)

    # 2. Отправляем новое сообщение и сохраняем его ID
    new_message = await callback.message.answer(
        text="📸 <b>Изменение аватара</b>\n\n"
             "Отправьте мне фотографию, которую вы хотите использовать как иконку профиля.\n\n"
             "💡 Для отмены отправьте команду /cancel",
        reply_markup=None,
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)

# --- 4. ИЗМЕНЕНИЕ АВАТАРА (Прием и сохранение) ---
@router.message(ProfileState.waiting_for_avatar, F.photo)
async def upload_avatar(message: Message, session: AsyncSession, state: FSMContext, bot: Bot):
    # 1. Удаляем предыдущее сообщение бота (запрос аватара)
    await delete_previous_message(state, message.chat.id, bot)
    # 2. Удаляем сообщение пользователя (фото)
    await message.delete()

    user_service = UserService(session)
    photo: PhotoSize = message.photo[-1]
    file_id = photo.file_id

    try:
        await user_service.update_field(
            telegram_id=message.from_user.id,
            field_name='avatar_file_id',
            new_value=file_id
        )

        await state.clear()

        # 3. Отправляем подтверждение
        confirm_msg = await message.answer("✅ Аватар успешно обновлён!")

        # Небольшая задержка для читаемости
        import asyncio
        await asyncio.sleep(1.5)
        await confirm_msg.delete()

        # Возвращаем в настройки
        await show_settings(message, state, bot)

    except SQLAlchemyError:
        await state.clear()
        await message.answer(f"❌ Ошибка БД при обновлении аватара. Попробуйте снова.")
        await show_settings(message, state, bot)
    except Exception:
        await state.clear()
        await message.answer(f"❌ Произошла неизвестная ошибка.")
        await show_settings(message, state, bot)

# --- 5. ИЗМЕНЕНИЕ ИМЕНИ (Начало) ---
@router.callback_query(F.data == "set_full_name")
async def start_name_change(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()

    # 1. Удаляем предыдущее сообщение (меню настроек)
    await delete_previous_message(state, callback.message.chat.id, bot)

    await state.set_state(ProfileState.waiting_for_new_full_name)

    # 2. Отправляем новое сообщение и сохраняем его ID
    new_message = await callback.message.answer(
        text="✍️ <b>Изменение имени</b>\n\n"
             "Введите новое имя и фамилию:\n\n"
             "💡 Для отмены отправьте команду /cancel",
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)

# --- 6. ИЗМЕНЕНИЕ ИМЕНИ (Сохранение) ---
@router.message(ProfileState.waiting_for_new_full_name)
async def process_new_name(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    # 1. Удаляем предыдущее сообщение бота (запрос имени)
    await delete_previous_message(state, message.chat.id, bot)
    # 2. Удаляем сообщение пользователя (введенное имя)
    await message.delete()

    new_name = message.text.strip()
    user_service = UserService(session)

    try:
        await user_service.update_field(
            telegram_id=message.from_user.id,
            field_name='full_name',
            new_value=new_name
        )
        await state.clear()

        # 3. Отправляем подтверждение
        confirm_msg = await message.answer("✅ Имя успешно обновлено!")

        import asyncio
        await asyncio.sleep(1.5)
        await confirm_msg.delete()

        await show_settings(message, state, bot)

    except SQLAlchemyError:
        await message.answer("❌ Ошибка при сохранении данных. Попробуйте снова.")
        await show_settings(message, state, bot)

# --- 7. ИЗМЕНЕНИЕ ТЕЛЕФОНА (Начало) ---
@router.callback_query(F.data == "set_phone")
async def start_phone_change(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    # 1. Удаляем предыдущее сообщение (меню настроек)
    await delete_previous_message(state, callback.message.chat.id, bot)

    await state.set_state(ProfileState.waiting_for_new_phone)

    # 2. Отправляем новое сообщение и сохраняем его ID
    new_message = await callback.message.answer(
        text="📞 <b>Изменение телефона</b>\n\n"
             "Введите новый номер телефона в формате <code>+7ХХХХХХХХХХ</code>:\n\n"
             "💡 Для отмены отправьте команду /cancel",
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)

# --- 8. ИЗМЕНЕНИЕ ТЕЛЕФОНА (Сохранение) ---
@router.message(ProfileState.waiting_for_new_phone)
async def process_new_phone(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    # 1. Удаляем предыдущее сообщение бота (запрос телефона)
    await delete_previous_message(state, message.chat.id, bot)
    # 2. Удаляем сообщение пользователя (введенный телефон)
    await message.delete()

    new_phone = message.text.strip()

    # Валидация номера телефона
    if not re.match(r"^\+7\d{10}$", new_phone):
        new_error_message = await message.answer(
            "❌ Неверный формат. Используйте <code>+7ХХХХХХХХХХ</code>.\n\n"
            "💡 Для отмены отправьте команду /cancel",
            parse_mode='HTML'
        )
        await set_last_message_id(state, new_error_message.message_id)
        return

    user_service = UserService(session)
    try:
        await user_service.update_field(
            telegram_id=message.from_user.id,
            field_name='phone',
            new_value=new_phone
        )
        await state.clear()

        # 3. Отправляем подтверждение
        confirm_msg = await message.answer("✅ Телефон успешно обновлен!")

        import asyncio
        await asyncio.sleep(1.5)
        await confirm_msg.delete()

        await show_settings(message, state, bot)

    except SQLAlchemyError:
        await message.answer("❌ Ошибка при сохранении данных. Попробуйте снова.")
        await show_settings(message, state, bot)

# --- 9. ИЗМЕНЕНИЕ EMAIL (Начало) ---
@router.callback_query(F.data == "set_email")
async def start_email_change(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()

    # 1. Удаляем предыдущее сообщение (меню настроек)
    await delete_previous_message(state, callback.message.chat.id, bot)

    await state.set_state(ProfileState.waiting_for_new_email)

    # 2. Отправляем новое сообщение и сохраняем его ID
    new_message = await callback.message.answer(
        text="✉️ <b>Изменение Email</b>\n\n"
             "Введите новый Email:\n\n"
             "💡 Для отмены отправьте команду /cancel",
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)

# --- 10. ИЗМЕНЕНИЕ EMAIL (Сохранение) ---
@router.message(ProfileState.waiting_for_new_email)
async def process_new_email(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    # 1. Удаляем предыдущее сообщение бота (запрос Email)
    await delete_previous_message(state, message.chat.id, bot)
    # 2. Удаляем сообщение пользователя (введенный Email)
    await message.delete()

    new_email = message.text.strip()

    # Валидация Email
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, new_email):
        new_error_message = await message.answer(
            "❌ Неверный формат Email. Попробуйте снова.\n\n"
            "💡 Для отмены отправьте команду /cancel",
            parse_mode='HTML'
        )
        await set_last_message_id(state, new_error_message.message_id)
        return

    user_service = UserService(session)
    try:
        await user_service.update_field(
            telegram_id=message.from_user.id,
            field_name='email',
            new_value=new_email
        )
        await state.clear()

        # 3. Отправляем подтверждение
        confirm_msg = await message.answer("✅ Email успешно обновлен!")

        import asyncio
        await asyncio.sleep(1.5)
        await confirm_msg.delete()

        await show_settings(message, state, bot)

    except SQLAlchemyError:
        await message.answer("❌ Ошибка при сохранении данных. Попробуйте снова.")
        await show_settings(message, state, bot)

# --- 11. ИЗМЕНЕНИЕ КОШЕЛЬКА (Начало) ---
@router.callback_query(F.data == "set_wallet")
async def start_wallet_change(callback: CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession):
    await callback.answer()

    # Удаляем предыдущее сообщение (меню настроек)
    await delete_previous_message(state, callback.message.chat.id, bot)

    # Получаем текущий кошелек пользователя
    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)

    current_wallet_text = ""
    if user.crypto_wallet:
        current_wallet_text = f"\n\n🔑 <b>Текущий кошелек:</b>\n<code>{user.crypto_wallet}</code>"

    await state.set_state(ProfileState.waiting_for_new_wallet)

    new_message = await callback.message.answer(
        text=f"💼 <b>Изменение кошелька</b>{current_wallet_text}\n\n"
             "Введите адрес вашего TON кошелька.\n\n"
             "📝 <b>Формат адреса:</b>\n"
             "• Должен начинаться с <code>EQ</code> или <code>UQ</code>\n"
             "• Длина: 48 символов\n\n"
             "💡 <b>Пример:</b>\n"
             "<code>EQDtFpEwcFAEcRe5mLVh2N6C0x-_hJEM7W61_JLnSF74p4q2</code>\n\n"
             "⚠️ <i>Проверьте адрес внимательно!</i>\n\n"
             "💡 Для отмены отправьте команду /cancel",
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)

# --- 12. ИЗМЕНЕНИЕ КОШЕЛЬКА (Сохранение) ---
@router.message(ProfileState.waiting_for_new_wallet)
async def process_new_wallet(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    # 1. Удаляем предыдущее сообщение бота (запрос кошелька)
    await delete_previous_message(state, message.chat.id, bot)
    # 2. Удаляем сообщение пользователя (введенный адрес)
    await message.delete()

    new_wallet = message.text.strip()

    # Валидация адреса кошелька
    if not is_valid_wallet(new_wallet):
        new_error_message = await message.answer(
            "❌ <b>Неверный формат TON адреса</b>\n\n"
            "Пожалуйста, проверьте адрес и отправьте снова.\n\n"
            "💡 Адрес должен:\n"
            "• Начинаться с <code>EQ</code> или <code>UQ</code>\n"
            "• Иметь длину 48 символов\n\n"
            "<b>Пример:</b>\n"
            "<code>EQDtFpEwcFAEcRe5mLVh2N6C0x-_hJEM7W61_JLnSF74p4q2</code>\n\n"
            "💡 Для отмены отправьте команду /cancel",
            parse_mode='HTML'
        )
        await set_last_message_id(state, new_error_message.message_id)
        return

    user_service = UserService(session)
    try:
        await user_service.update_field(
            telegram_id=message.from_user.id,
            field_name='crypto_wallet',
            new_value=new_wallet
        )
        await state.clear()

        # 3. Отправляем подтверждение
        confirm_msg = await message.answer(
            f"✅ <b>Кошелек успешно обновлен!</b>\n\n"
            f"🔑 Новый адрес:\n<code>{new_wallet}</code>",
            parse_mode='HTML'
        )

        import asyncio
        await asyncio.sleep(2)
        await confirm_msg.delete()

        await show_settings(message, state, bot)

    except SQLAlchemyError:
        await message.answer("❌ Ошибка при сохранении данных. Попробуйте снова.")
        await show_settings(message, state, bot)

# Хендлер main_menu_return теперь в start.py
# Хендлер show_games теперь в games.py