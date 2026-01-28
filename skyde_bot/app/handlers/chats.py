from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from skyde_bot.app.utils.utils import delete_previous_message, set_last_message_id
from skyde_bot.app.services.chat_services import ChatService
from skyde_bot.app.services.user_services import UserService
from skyde_bot.app.states.chat_states import ChatState
from skyde_bot.app.config import BOT_TOKEN

router = Router()


# --- КЛАВИАТУРЫ ---

def chats_main_menu() -> InlineKeyboardMarkup:
    """Главное меню чатов."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Поиск собеседника", callback_data="chat_search")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")]
    ])


def chats_menu_with_contacts(contacts: list) -> InlineKeyboardMarkup:
    """Меню чатов с последними контактами."""
    keyboard = [
        [InlineKeyboardButton(text="🔍 Поиск собеседника", callback_data="chat_search")]
    ]

    if contacts:
        keyboard.append([InlineKeyboardButton(text="📋 Недавние диалоги:", callback_data="ignore")])

        # Убираем дубликаты по telegram_id
        seen_users = set()

        for contact in contacts:
            user = contact['user']

            # Пропускаем, если этот пользователь уже был добавлен
            if user.telegram_id in seen_users:
                continue

            seen_users.add(user.telegram_id)

            status = "🟢" if contact['is_active'] else "⚪️"
            # Используем full_name вместо username
            button_text = f"{status} {user.full_name}"

            keyboard.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"chat_contact_{user.telegram_id}"
                )
            ])

    keyboard.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def chat_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для запроса на переписку."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"chat_accept_{request_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"chat_reject_{request_id}")
        ],
        [InlineKeyboardButton(text="🚫 Игнорировать", callback_data=f"chat_ignore_{request_id}")]
    ])


def active_chat_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура активного чата."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚪 Покинуть диалог", callback_data="chat_leave")]
    ])


def cancel_search_keyboard() -> InlineKeyboardMarkup:
    """Отмена поиска."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="chat_menu")]
    ])


# --- ХЕНДЛЕР 1: Главное меню чатов ---
@router.callback_query(F.data == "chat_menu")
async def show_chats_menu(callback: CallbackQuery, session: AsyncSession,
                          state: FSMContext, bot: Bot):
    """Показать главное меню чатов."""
    await callback.answer()

    # Удаляем предыдущее сообщение
    await delete_previous_message(state, callback.message.chat.id, bot)

    # Получаем последних собеседников (увеличиваем лимит, т.к. могут быть дубли)
    chat_service = ChatService(session)
    contacts = await chat_service.get_recent_contacts(callback.from_user.id, limit=20)

    text = "💬 <b>Чаты</b>\n\n"

    if contacts:
        text += "Выберите действие или продолжите диалог:"
    else:
        text += "Начните общение с другими пользователями бота!\n\n" \
                "💡 Найдите собеседника по @username"

    new_message = await callback.message.answer(
        text,
        reply_markup=chats_menu_with_contacts(contacts),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)

# --- ХЕНДЛЕР 2: Начало поиска собеседника ---
@router.callback_query(F.data == "chat_search")
async def start_chat_search(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Начало поиска собеседника."""
    await callback.answer()

    # Удаляем предыдущее сообщение
    await delete_previous_message(state, callback.message.chat.id, bot)

    await state.set_state(ChatState.waiting_for_username)

    new_message = await callback.message.answer(
        "🔍 <b>Поиск собеседника</b>\n\n"
        "Введите @username пользователя, с которым хотите начать переписку:\n\n"
        "💡 <i>Например: @username</i>",
        reply_markup=cancel_search_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)

# --- ХЕНДЛЕР 3: Обработка введенного username ---
@router.message(ChatState.waiting_for_username)
async def process_username_search(message: Message, session: AsyncSession,
                                  state: FSMContext, bot: Bot):
    """Поиск пользователя по username."""

    # Удаляем предыдущее сообщение бота
    await delete_previous_message(state, message.chat.id, bot)
    # Удаляем сообщение пользователя
    await message.delete()

    username = message.text.strip()

    # Проверка на самого себя
    if username.lstrip('@') == message.from_user.username:
        error_msg = await message.answer(
            "❌ Вы не можете начать диалог с самим собой!",
            reply_markup=cancel_search_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, error_msg.message_id)
        return

    chat_service = ChatService(session)
    user_service = UserService(session)

    # Ищем пользователя
    target_user = await chat_service.find_user_by_username(username)

    if not target_user:
        # Пользователь не найден в боте
        await state.clear()

        # Создаем инвайт-ссылку
        bot_username = (await bot.get_me()).username
        invite_link = f"https://t.me/{bot_username}?start=invite_{message.from_user.id}"

        not_found_msg = await message.answer(
            f"❌ <b>Пользователь не найден</b>\n\n"
            f"Пользователь <code>{username}</code> еще не зарегистрирован в боте.\n\n"
            f"🎁 <b>Вы можете отправить ему приглашение:</b>\n"
            f"<code>{invite_link}</code>\n\n"
            f"💡 Скопируйте ссылку и отправьте собеседнику!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к чатам", callback_data="chat_menu")]
            ]),
            parse_mode='HTML'
        )
        await set_last_message_id(state, not_found_msg.message_id)
        return

    # Пользователь найден - создаем запрос
    request = await chat_service.create_chat_request(
        from_user_id=message.from_user.id,
        to_user_id=target_user.telegram_id
    )

    if not request:
        # Запрос уже существует
        await state.clear()

        existing_msg = await message.answer(
            f"⏳ <b>Запрос уже отправлен</b>\n\n"
            f"Вы уже отправили запрос пользователю <code>{username}</code>.\n"
            f"Ожидайте ответа.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к чатам", callback_data="chat_menu")]
            ]),
            parse_mode='HTML'
        )
        await set_last_message_id(state, existing_msg.message_id)
        return

    # Запрос создан успешно
    await state.clear()

    # Уведомляем отправителя
    sender_msg = await message.answer(
        f"✅ <b>Запрос отправлен!</b>\n\n"
        f"Запрос на переписку отправлен пользователю <code>{username}</code>.\n"
        f"Ожидайте ответа.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к чатам", callback_data="chat_menu")]
        ]),
        parse_mode='HTML'
    )
    await set_last_message_id(state, sender_msg.message_id)

    # Отправляем уведомление получателю
    current_user = await user_service.get_user_by_telegram_id(message.from_user.id)

    try:
        await bot.send_message(
            target_user.telegram_id,
            f"💬 <b>Новый запрос на переписку</b>\n\n"
            f"Пользователь <b>{current_user.full_name}</b> "
            f"(@{current_user.username or 'без username'}) "
            f"хочет начать с вами переписку.",
            reply_markup=chat_request_keyboard(request.id),
            parse_mode='HTML'
        )
    except Exception as e:
        # Не удалось отправить уведомление (пользователь заблокировал бота и т.д.)
        pass

# --- ХЕНДЛЕР 4: Принятие запроса ---
@router.callback_query(F.data.startswith("chat_accept_"))
async def accept_chat_request(callback: CallbackQuery, session: AsyncSession,
                              state: FSMContext, bot: Bot):
    """Принять запрос на переписку."""
    await callback.answer("Запрос принят!")

    request_id = int(callback.data.split('_')[2])

    chat_service = ChatService(session)
    user_service = UserService(session)

    # Создаем сессию чата
    chat_session = await chat_service.accept_chat_request(request_id)

    if not chat_session:
        await callback.message.edit_text(
            "❌ Ошибка: запрос не найден или уже обработан.",
            reply_markup=None
        )
        return

    # Удаляем сообщение с запросом
    await callback.message.delete()

    # Переводим принявшего в режим чата
    await state.set_state(ChatState.in_active_chat)
    await state.update_data(session_id=chat_session.id)

    # Получаем данные собеседника
    other_user = await chat_service.get_other_user_in_session(
        chat_session.id,
        callback.from_user.id
    )

    acceptor_msg = await callback.message.answer(
        f"✅ <b>Диалог начат!</b>\n\n"
        f"Вы начали переписку с <b>{other_user.full_name}</b> "
        f"(@{other_user.username or 'без username'})\n\n"
        f"💬 Отправьте сообщение:",
        reply_markup=active_chat_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, acceptor_msg.message_id)

    # ========== ИСПРАВЛЕНИЕ: правильное создание FSMContext ==========
    # Уведомляем инициатора И ПЕРЕВОДИМ ЕГО В СОСТОЯНИЕ ЧАТА
    try:
        current_user = await user_service.get_user_by_telegram_id(callback.from_user.id)

        # ПРАВИЛЬНЫЙ способ создания FSMContext для другого пользователя
        from aiogram.fsm.storage.base import StorageKey

        initiator_state_key = StorageKey(
            bot_id=bot.id,
            chat_id=other_user.telegram_id,
            user_id=other_user.telegram_id
        )

        initiator_state = FSMContext(
            storage=state.storage,
            key=initiator_state_key
        )

        # Устанавливаем состояние для инициатора
        await initiator_state.set_state(ChatState.in_active_chat)
        await initiator_state.update_data(session_id=chat_session.id)

        # Отправляем уведомление инициатору
        initiator_msg = await bot.send_message(
            other_user.telegram_id,
            f"✅ <b>Запрос принят!</b>\n\n"
            f"<b>{current_user.full_name}</b> принял(а) ваш запрос на переписку.\n\n"
            f"💬 Отправьте сообщение:",
            reply_markup=active_chat_keyboard(),
            parse_mode='HTML'
        )

        # Сохраняем ID сообщения для инициатора
        await initiator_state.update_data(last_message_id=initiator_msg.message_id)

    except Exception as e:
        print(f"Ошибка при уведомлении инициатора: {e}")
        import traceback
        traceback.print_exc()

# --- ХЕНДЛЕР 5: Отклонение запроса ---
@router.callback_query(F.data.startswith("chat_reject_"))
async def reject_chat_request(callback: CallbackQuery, session: AsyncSession, bot: Bot):
    """Отклонить запрос на переписку."""
    await callback.answer("Запрос отклонен")

    request_id = int(callback.data.split('_')[2])

    chat_service = ChatService(session)
    await chat_service.reject_chat_request(request_id)

    await callback.message.edit_text(
        "❌ Вы отклонили запрос на переписку.",
        reply_markup=None
    )

# --- ХЕНДЛЕР 6: Игнорирование запроса ---
@router.callback_query(F.data.startswith("chat_ignore_"))
async def ignore_chat_request(callback: CallbackQuery, session: AsyncSession):
    """Игнорировать запрос на переписку."""
    await callback.answer("Запрос проигнорирован")

    request_id = int(callback.data.split('_')[2])

    chat_service = ChatService(session)
    await chat_service.ignore_chat_request(request_id)

    await callback.message.delete()

# --- ХЕНДЛЕР 7: Повторный запрос к старому собеседнику ---
@router.callback_query(F.data.startswith("chat_contact_"))
async def reconnect_with_contact(callback: CallbackQuery, session: AsyncSession,
                                 state: FSMContext, bot: Bot):
    """Повторный запрос на переписку со старым собеседником."""
    await callback.answer()

    target_user_id = int(callback.data.split('_')[2])

    chat_service = ChatService(session)
    user_service = UserService(session)

    # Создаем новый запрос
    request = await chat_service.create_chat_request(
        from_user_id=callback.from_user.id,
        to_user_id=target_user_id
    )

    target_user = await user_service.get_user_by_telegram_id(target_user_id)

    if not request:
        await callback.message.answer(
            f"⏳ Запрос уже отправлен пользователю <b>{target_user.full_name}</b>.",
            parse_mode='HTML'
        )
        return

    # Удаляем предыдущее сообщение
    await delete_previous_message(state, callback.message.chat.id, bot)

    # Уведомляем отправителя
    sender_msg = await callback.message.answer(
        f"✅ <b>Запрос отправлен!</b>\n\n"
        f"Запрос на переписку отправлен пользователю <b>{target_user.full_name}</b>.\n"
        f"Ожидайте ответа.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к чатам", callback_data="chat_menu")]
        ]),
        parse_mode='HTML'
    )
    await set_last_message_id(state, sender_msg.message_id)

    # Отправляем уведомление получателю
    current_user = await user_service.get_user_by_telegram_id(callback.from_user.id)

    try:
        await bot.send_message(
            target_user.telegram_id,
            f"💬 <b>Новый запрос на переписку</b>\n\n"
            f"Пользователь <b>{current_user.full_name}</b> "
            f"(@{current_user.username or 'без username'}) "
            f"хочет начать с вами переписку.",
            reply_markup=chat_request_keyboard(request.id),
            parse_mode='HTML'
        )
    except Exception:
        pass

# --- ХЕНДЛЕР 8: Обработка сообщений в активном чате ---
@router.message(ChatState.in_active_chat)
async def handle_chat_message(message: Message, session: AsyncSession,
                              state: FSMContext, bot: Bot):
    """Обработка сообщений в активном диалоге."""

    data = await state.get_data()
    session_id = data.get('session_id')

    if not session_id:
        await message.answer("❌ Ошибка: активная сессия не найдена.")
        await state.clear()
        return

    chat_service = ChatService(session)

    # Сохраняем сообщение
    await chat_service.send_message(
        session_id=session_id,
        sender_id=message.from_user.id,
        text=message.text
    )

    # Получаем собеседника
    other_user = await chat_service.get_other_user_in_session(
        session_id,
        message.from_user.id
    )

    if not other_user:
        await message.answer("❌ Ошибка: собеседник не найден.")
        return

    # Пересылаем сообщение собеседнику (анонимно через бота)
    try:
        await bot.send_message(
            other_user.telegram_id,
            f"💬 <b>Сообщение от собеседника:</b>\n\n{message.text}",
            parse_mode='HTML'
        )
    except Exception:
        await message.answer(
            "⚠️ Не удалось доставить сообщение. "
            "Возможно, собеседник покинул чат или заблокировал бота."
        )

# --- ХЕНДЛЕР 9: Покинуть диалог ---
@router.callback_query(F.data == "chat_leave")
async def leave_chat(callback: CallbackQuery, session: AsyncSession,
                     state: FSMContext, bot: Bot):
    """Покинуть активный диалог."""

    await callback.answer("Вы покинули диалог")

    data = await state.get_data()
    session_id = data.get('session_id')

    if session_id:
        chat_service = ChatService(session)

        # Получаем собеседника перед завершением сессии
        other_user = await chat_service.get_other_user_in_session(
            session_id,
            callback.from_user.id
        )

        # Завершаем сессию
        await chat_service.end_chat_session(session_id)

        # Уведомляем собеседника И ОЧИЩАЕМ ЕГО СОСТОЯНИЕ
        if other_user:
            try:
                # ПРАВИЛЬНЫЙ способ создания FSMContext для другого пользователя
                from aiogram.fsm.storage.base import StorageKey

                other_state_key = StorageKey(
                    bot_id=bot.id,
                    chat_id=other_user.telegram_id,
                    user_id=other_user.telegram_id
                )

                other_state = FSMContext(
                    storage=state.storage,
                    key=other_state_key
                )

                # Очищаем состояние собеседника
                await other_state.clear()

                await bot.send_message(
                    other_user.telegram_id,
                    "💔 <b>Собеседник покинул чат</b>\n\n"
                    "Диалог завершен.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ К чатам", callback_data="chat_menu")]
                    ]),
                    parse_mode='HTML'
                )
            except Exception as e:
                print(f"Ошибка при уведомлении собеседника: {e}")
                import traceback
                traceback.print_exc()

    await state.clear()

    # Удаляем предыдущее сообщение
    await delete_previous_message(state, callback.message.chat.id, bot)

    # Возвращаем в меню чатов
    leave_msg = await callback.message.answer(
        "🚪 <b>Вы покинули диалог</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К чатам", callback_data="chat_menu")]
        ]),
        parse_mode='HTML'
    )
    await set_last_message_id(state, leave_msg.message_id)