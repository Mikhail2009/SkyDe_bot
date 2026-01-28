from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from skyde_bot.app.keyboards.inline import main_menu_keyboard, cancel_keyboard
from skyde_bot.app.utils.utils import delete_previous_message, set_last_message_id
from skyde_bot.app.services.user_services import UserService
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import re

router = Router()


# --- СОСТОЯНИЯ ---
class NFTState(StatesGroup):
    waiting_for_promo = State()
    waiting_for_wallet = State()


# --- КЛАВИАТУРЫ ---

def nft_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное NFT меню (доступно только с привязанным кошельком)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Мои NFT", callback_data="show_my_nfts")],
        [InlineKeyboardButton(text="🛒 Купить NFT", callback_data="buy_nft")],
        [InlineKeyboardButton(text="💰 Продать NFT", callback_data="sell_nft")],
        [InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="🔑 Мой кошелек", callback_data="show_wallet")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")]
    ])


def wallet_required_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для привязки кошелька."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Привязать кошелек", callback_data="bind_wallet")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="main_menu_return")]
    ])


def wallet_confirm_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения кошелька."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_wallet")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_wallet")]
    ])


def back_to_nft_menu_keyboard() -> InlineKeyboardMarkup:
    """Вернуться в основное NFT меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в NFT меню", callback_data="nft_menu")]
    ])


# --- УТИЛИТЫ ---

def is_valid_wallet(address: str) -> bool:
    """Валидация адреса TON кошелька."""

    # TON кошелек (EQ... или UQ...)
    # Формат: 48 символов (EQ/UQ + 46 символов base64url)
    if re.match(r'^(EQ|UQ)[a-zA-Z0-9_-]{46}$', address):
        return True

    return False


# --- ХЕНДЛЕР 1: Вход в NFT меню (с проверкой кошелька) ---
@router.callback_query(F.data == "nft_menu")
async def show_nft_menu(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Показать меню NFT с проверкой привязки кошелька."""
    await callback.answer()
    session.expire_all()

    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)

    # Удаляем предыдущее сообщение
    await delete_previous_message(state, callback.message.chat.id, bot)

    # ПРОВЕРКА: Привязан ли кошелек?
    if not user.crypto_wallet:
        # Кошелек НЕ привязан
        new_message = await callback.message.answer(
            "🔒 <b>Доступ к разделу NFT ограничен</b>\n\n"
            "Для использования раздела NFT необходимо привязать крипто-кошелек.\n\n"
            "💡 <i>Это нужно для безопасных операций с NFT и возможности вывода средств.</i>",
            reply_markup=wallet_required_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, new_message.message_id)
        return

    # Кошелек ПРИВЯЗАН - показываем NFT меню
    new_message = await callback.message.answer(
        "✨ <b>NFT Маркетплейс</b>\n\n"
        f"🔑 Ваш кошелек: <code>{user.crypto_wallet[:6]}...{user.crypto_wallet[-4:]}</code>\n\n"
        "Добро пожаловать в мир цифровых активов!\n"
        "Выберите действие:",
        reply_markup=nft_menu_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР 2: Начало привязки кошелька ---
@router.callback_query(F.data == "bind_wallet")
async def start_bind_wallet(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Начало процесса привязки кошелька."""
    await callback.answer()

    # Удаляем предыдущее сообщение
    await delete_previous_message(state, callback.message.chat.id, bot)

    await state.set_state(NFTState.waiting_for_wallet)

    new_message = await callback.message.answer(
        "🔗 <b>Привязка TON кошелька</b>\n\n"
        "Вставьте, пожалуйста, адрес вашего TON кошелька.\n\n"
        "📝 <b>Формат адреса:</b>\n"
        "• Должен начинаться с <code>EQ</code> или <code>UQ</code>\n"
        "• Длина: 48 символов\n\n"
        "💡 <b>Пример:</b>\n"
        "<code>EQDtFpEwcFAEcRe5mLVh2N6C0x-_hJEM7W61_JLnSF74p4q2</code>\n\n"
        "⚠️ <i>Проверьте адрес внимательно!</i>",
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР 3: Обработка введенного адреса кошелька ---
@router.message(NFTState.waiting_for_wallet)
async def process_wallet_address(message: types.Message, state: FSMContext, bot: Bot):
    """Обработка введенного адреса кошелька."""

    # Удаляем предыдущее сообщение бота
    await delete_previous_message(state, message.chat.id, bot)
    # Удаляем сообщение пользователя
    await message.delete()

    wallet_address = message.text.strip()

    # Валидация адреса
    if not is_valid_wallet(wallet_address):
        error_msg = await message.answer(
            "❌ <b>Неверный формат TON адреса</b>\n\n"
            "Пожалуйста, проверьте адрес и отправьте снова.\n\n"
            "💡 Адрес должен:\n"
            "• Начинаться с <code>EQ</code> или <code>UQ</code>\n"
            "• Иметь длину 48 символов\n\n"
            "<b>Пример:</b>\n"
            "<code>EQDtFpEwcFAEcRe5mLVh2N6C0x-_hJEM7W61_JLnSF74p4q2</code>",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, error_msg.message_id)
        return

    # Сохраняем адрес во временные данные
    await state.update_data(wallet_address=wallet_address)

    # Просим подтверждения
    confirm_msg = await message.answer(
        f"🔍 <b>Подтвердите адрес кошелька</b>\n\n"
        f"<code>{wallet_address}</code>\n\n"
        f"⚠️ <i>Убедитесь, что адрес указан правильно!</i>",
        reply_markup=wallet_confirm_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, confirm_msg.message_id)


# --- ХЕНДЛЕР 4: Подтверждение привязки кошелька ---
@router.callback_query(F.data == "confirm_wallet", NFTState.waiting_for_wallet)
async def confirm_wallet_binding(callback: types.CallbackQuery, session: AsyncSession,
                                 state: FSMContext, bot: Bot):
    """Сохранение кошелька в БД."""
    await callback.answer()

    # Получаем адрес из временных данных
    data = await state.get_data()
    wallet_address = data.get('wallet_address')

    if not wallet_address:
        await callback.message.answer("❌ Ошибка: адрес не найден. Попробуйте снова.")
        await state.clear()
        return

    # Сохраняем в БД
    user_service = UserService(session)
    try:
        await user_service.update_field(
            telegram_id=callback.from_user.id,
            field_name='crypto_wallet',
            new_value=wallet_address
        )

        await state.clear()

        # Удаляем предыдущее сообщение
        await delete_previous_message(state, callback.message.chat.id, bot)
        # Успешное подтверждение
        success_msg = await callback.message.answer(
            f"✅ <b>Кошелек успешно привязан!</b>\n\n"
            f"🔑 Адрес: <code>{wallet_address}</code>\n\n"
            f"Теперь вам доступны все функции раздела NFT!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✨ Открыть NFT меню", callback_data="nft_menu")]
            ]),
            parse_mode='HTML'
        )
        await set_last_message_id(state, success_msg.message_id)

    except Exception as e:
        await state.clear()
        await callback.message.answer(
            f"❌ Ошибка при сохранении кошелька: {e}",
            reply_markup=main_menu_keyboard()
        )


# --- ХЕНДЛЕР 5: Отмена привязки кошелька ---
@router.callback_query(F.data == "cancel_wallet")
async def cancel_wallet_binding(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Отмена привязки кошелька."""
    await callback.answer("Отменено")

    await state.clear()

    # Удаляем предыдущее сообщение
    await delete_previous_message(state, callback.message.chat.id, bot)

    cancel_msg = await callback.message.answer(
        "❌ Привязка кошелька отменена.",
        reply_markup=main_menu_keyboard()
    )
    await set_last_message_id(state, cancel_msg.message_id)


# --- ХЕНДЛЕР 6: Показать информацию о кошельке ---
@router.callback_query(F.data == "show_wallet")
async def show_wallet_info(callback: types.CallbackQuery, session: AsyncSession,
                           state: FSMContext, bot: Bot):
    """Показать информацию о привязанном кошельке."""
    await callback.answer()

    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)

    # Удаляем предыдущее сообщение
    await delete_previous_message(state, callback.message.chat.id, bot)

    wallet_msg = await callback.message.answer(
        f"🔑 <b>Ваш крипто-кошелек</b>\n\n"
        f"<code>{user.crypto_wallet}</code>\n\n"
        f"⚠️ <i>Будьте внимательны при совершении транзакций!</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Изменить кошелек", callback_data="bind_wallet")],
            [InlineKeyboardButton(text="⬅️ Назад в NFT меню", callback_data="nft_menu")]
        ]),
        parse_mode='HTML'
    )
    await set_last_message_id(state, wallet_msg.message_id)


# --- ХЕНДЛЕР 7: Мои NFT ---
@router.callback_query(F.data == "show_my_nfts")
async def show_my_nfts(callback: types.CallbackQuery, session: AsyncSession, bot: Bot, state: FSMContext):
    """Показать NFT пользователя."""
    await callback.answer()

    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)

    # Удаляем предыдущее сообщение
    await delete_previous_message(state, callback.message.chat.id, bot)

    new_message = await callback.message.answer(
        "💎 <b>Мои NFT</b>\n\n"
        f"👤 Владелец: {user.full_name}\n"
        f"🆔 UID: {user.uid}\n\n"
        "📦 У вас пока нет NFT.\n\n"
        "💡 Купите NFT в разделе 'Купить NFT' или получите через промокод!",
        reply_markup=back_to_nft_menu_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР 8: Купить NFT ---
@router.callback_query(F.data == "buy_nft")
async def buy_nft(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    """Раздел покупки NFT."""
    await callback.answer()

    await delete_previous_message(state, callback.message.chat.id, bot)

    new_message = await callback.message.answer(
        "🛒 <b>Покупка NFT</b>\n\n"
        "🔍 Поиск доступных NFT...\n\n"
        "😔 К сожалению, в данный момент коллекции загружаются.\n\n"
        "⏳ Пожалуйста, попробуйте позже или обратитесь в поддержку.",
        reply_markup=back_to_nft_menu_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)

    # --- ХЕНДЛЕР 9: Продать NFT ---
@router.callback_query(F.data == "sell_nft")
async def sell_nft(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    """Раздел продажи NFT."""
    await callback.answer()

    await delete_previous_message(state, callback.message.chat.id, bot)

    new_message = await callback.message.answer(
        "💰 <b>Продажа NFT</b>\n\n"
        "📊 Анализ вашей коллекции...\n\n"
        "😔 У вас пока нет NFT для продажи.\n\n"
        "💡 Купите NFT в разделе 'Купить NFT' или получите в играх.",
        reply_markup=back_to_nft_menu_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР 10: Начало ввода промокода ---
@router.callback_query(F.data == "enter_promo")
async def enter_promo(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Начало ввода промокода."""
    await callback.answer()

    await delete_previous_message(state, callback.message.chat.id, bot)

    await state.set_state(NFTState.waiting_for_promo)

    new_message = await callback.message.answer(
        "🎁 <b>Ввод промокода</b>\n\n"
        "Введите ваш промокод (6-12 символов):\n\n"
        "Пример: SKYDE2024",
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР 11: Обработка промокода ---
@router.message(NFTState.waiting_for_promo)
async def process_promo(message: types.Message, session: AsyncSession, state: FSMContext, bot: Bot):
    """Обработка введенного промокода."""

    await delete_previous_message(state, message.chat.id, bot)
    await message.delete()

    promo_code = message.text.upper().strip()

    if not promo_code.isalnum() or len(promo_code) < 6 or len(promo_code) > 12:
        error_msg = await message.answer(
            "❌ Неверный формат промокода!\n\n"
            "Промокод должен содержать 6-12 букв/цифр.",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, error_msg.message_id)
        return

    valid_promos = {
        "SKYDE2024": 100.0,
        "WELCOME": 50.0,
        "VIP": 200.0,
        "START": 25.0
    }

    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(message.from_user.id)

    if not user:
        await state.clear()
        await message.answer("❌ Пользователь не найден. Используйте /start")
        return

    if promo_code in valid_promos:
        amount = valid_promos[promo_code]

        try:
            new_balance = await user_service.update_balance(message.from_user.id, amount)

            await state.clear()

            success_msg = await message.answer(
                f"✅ <b>Промокод активирован!</b>\n\n"
                f"🎁 Промокод: <code>{promo_code}</code>\n"
                f"💰 Начислено: <b>+{amount}</b> G-монет\n"
                f"💼 Новый баланс: <b>{new_balance:.2f}</b> G-монет",
                reply_markup=main_menu_keyboard(),
                parse_mode='HTML'
            )
            await set_last_message_id(state, success_msg.message_id)

        except Exception as e:
            await state.clear()
            await message.answer(
                f"❌ Ошибка при активации промокода: {e}",
                reply_markup=nft_menu_keyboard()
            )
    else:
        await state.clear()

        error_msg = await message.answer(
            f"❌ <b>Промокод не найден</b>\n\n"
            f"Промокод <code>{promo_code}</code> недействителен или уже использован.\n\n"
            f"💡 Проверьте правильность ввода.",
            reply_markup=nft_menu_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, error_msg.message_id)