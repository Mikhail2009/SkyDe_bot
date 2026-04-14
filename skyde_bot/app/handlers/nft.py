from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, ReplyKeyboardMarkup, \
    KeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from skyde_bot.app.keyboards.inline import main_menu_keyboard, cancel_keyboard
from skyde_bot.app.utils.utils import delete_previous_message, set_last_message_id
from skyde_bot.app.services.user_services import UserService
from skyde_bot.app.services.nft_services import NFTService
from skyde_bot.app.states.nft_states import NFTState
from skyde_bot.app.states.chat_states import ChatState
from skyde_bot.watermark import add_watermark
from skyde_bot.app.database.models import NFTPurchase, NFTDispute, NFTUploadRequest, ChatSession
from skyde_bot.app.services.chat_services import ChatService
from decimal import Decimal, ROUND_DOWN
from skyde_bot.app.config import ADMIN_ID, ADMIN_WALLET
import random
import re

router = Router()

# --- КОНФИГУРАЦИЯ ЦЕН ---
PRICE_DECIMAL_PLACES = 9  # Сколько знаков после запятой хранить
PRICE_DISPLAY_PLACES = 6  # Сколько знаков показывать пользователю
MIN_PRICE = 0.000001  # Минимальная цена в TON (0.000001 = 1 микротон)
MAX_PRICE = 1000000  # Максимальная цена в TON


def format_price(price, max_decimals=PRICE_DISPLAY_PLACES):
    """Форматирует цену для отображения."""
    price_float = float(price)

    # Определяем сколько знаков после запятой показывать
    # Если число целое - показываем без дробной части
    if price_float.is_integer():
        return f"{int(price_float):,}"

    # Ищем ненулевые знаки после запятой
    price_str = f"{price_float:.{max_decimals}f}"

    # Убираем лишние нули в конце
    if '.' in price_str:
        price_str = price_str.rstrip('0').rstrip('.')

    # Добавляем разделители тысяч
    parts = price_str.split('.')
    if len(parts) == 2:
        int_part = int(parts[0]) if parts[0] else 0
        formatted_int = f"{int_part:,}"
        return f"{formatted_int}.{parts[1]}"
    else:
        return f"{int(price_str):,}"


def format_price_short(price):
    """Короткое форматирование цены (для кнопок)."""
    price_float = float(price)

    if price_float >= 1000:
        return f"{price_float:,.0f}"
    elif price_float >= 1:
        return f"{price_float:,.2f}"
    elif price_float >= 0.01:
        return f"{price_float:,.4f}"
    else:
        return f"{price_float:.{PRICE_DISPLAY_PLACES}f}"


# --- КЛАВИАТУРЫ ---

def nft_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное NFT меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Мои NFT", callback_data="show_my_nfts")],
        [InlineKeyboardButton(text="🛒 Купить NFT", callback_data="buy_nft_marketplace")],
        [InlineKeyboardButton(text="⭐️ Избранное", callback_data="show_favorites")],
        [InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")]
    ])


def my_nft_navigation_keyboard(current_index: int, total_count: int, nft_id: int,
                               is_on_sale: bool) -> InlineKeyboardMarkup:
    """Клавиатура навигации по своим NFT (БЕЗ кнопки выставить/снять)."""
    buttons = []

    # Навигация
    nav_row = []
    if current_index > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Предыдущее", callback_data=f"my_nft_prev_{current_index}"))
    if current_index < total_count - 1:
        nav_row.append(InlineKeyboardButton(text="Следующее ▶️", callback_data=f"my_nft_next_{current_index}"))

    if nav_row:
        buttons.append(nav_row)

    # Загрузить новое NFT
    buttons.append([InlineKeyboardButton(text="📤 Загрузить новое NFT", callback_data="upload_new_nft")])

    # Удалить NFT
    buttons.append([InlineKeyboardButton(text="🗑 Удалить NFT", callback_data=f"delete_nft_{nft_id}")])

    # Вернуться в главное меню
    buttons.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def upload_nft_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для загрузки NFT."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Загрузить NFT", callback_data="upload_new_nft")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="nft_menu")]
    ])


def marketplace_navigation_keyboard(current_index: int, total_count: int, nft_id: int,
                                    is_favorite: bool) -> InlineKeyboardMarkup:
    """Клавиатура навигации по маркетплейсу."""
    buttons = []

    # Навигация
    nav_row = []
    if current_index > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Предыдущее", callback_data=f"market_prev_{current_index}"))
    if current_index < total_count - 1:
        nav_row.append(InlineKeyboardButton(text="Следующее ▶️", callback_data=f"market_next_{current_index}"))

    if nav_row:
        buttons.append(nav_row)

    # Кнопка купить
    buttons.append([InlineKeyboardButton(text="💰 Купить", callback_data=f"buy_nft_{nft_id}")])

    # Кнопка избранное
    if is_favorite:
        fav_button = InlineKeyboardButton(text="💔 Удалить из избранного", callback_data=f"unfav_nft_{nft_id}")
    else:
        fav_button = InlineKeyboardButton(text="⭐️ Добавить в избранное", callback_data=f"fav_nft_{nft_id}")

    buttons.append([fav_button])

    # Вернуться
    buttons.append([InlineKeyboardButton(text="⬅️ Назад в NFT меню", callback_data="nft_menu")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def purchase_confirmation_keyboard(purchase_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения покупки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатил", callback_data=f"confirm_payment_{purchase_id}")],
        [InlineKeyboardButton(text="❌ Отменить покупку", callback_data=f"cancel_purchase_{purchase_id}")]
    ])


# --- НОВЫЕ КЛАВИАТУРЫ ДЛЯ СПОРОВ ---

def dispute_seller_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура продавца во время спора (нижнее меню Telegram)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✅ Подтвердить оплату"),
                KeyboardButton(text="⚠️ Жалоба на покупателя")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def dispute_buyer_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура покупателя во время спора (нижнее меню Telegram)."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔍 Проверить оплату"),
                KeyboardButton(text="⚠️ Жалоба на продавца")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def remove_keyboard() -> types.ReplyKeyboardRemove:
    """Убрать клавиатуру."""
    return types.ReplyKeyboardRemove()


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def is_valid_wallet(address: str) -> bool:
    """Валидация адреса TON кошелька."""
    if re.match(r'^(EQ|UQ)[a-zA-Z0-9_-]{46}$', address):
        return True
    return False


# --- ХЕНДЛЕР 1: Главное меню NFT ---
@router.callback_query(F.data == "nft_menu")
async def show_nft_menu(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Показать меню NFT."""
    await callback.answer()
    session.expire_all()

    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)

    # ПРОВЕРКА КОШЕЛЬКА
    if not user.crypto_wallet:
        await delete_previous_message(state, callback.message.chat.id, bot)

        new_message = await callback.message.answer(
            "⚠️ <b>Кошелек не подключен</b>\n\n"
            "Для использования NFT маркетплейса необходимо подключить TON кошелек.\n\n"
            "📝 <b>Как подключить:</b>\n"
            "1. Зайдите в 'Профиль' → 'Настройки'\n"
            "2. Выберите 'Изменить кошелёк'\n"
            "3. Введите адрес вашего TON кошелька\n\n"
            "💡 Формат адреса: <code>EQ...</code> или <code>UQ...</code> (48 символов)",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚙️ Настройки профиля", callback_data="settings")],
                [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")]
            ]),
            parse_mode='HTML'
        )
        await set_last_message_id(state, new_message.message_id)
        return

    await delete_previous_message(state, callback.message.chat.id, bot)

    # Проверка кошелька (опционально, можно убрать)
    wallet_info = ""
    if user.crypto_wallet:
        wallet_info = f"\n🔑 Кошелек: <code>{user.crypto_wallet[:6]}...{user.crypto_wallet[-4:]}</code>"

    new_message = await callback.message.answer(
        f"✨ <b>NFT Маркетплейс</b>{wallet_info}\n\n"
        "Добро пожаловать в мир цифровых активов!\n"
        "Выберите действие:",
        reply_markup=nft_main_menu_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР 2: Мои NFT ---
@router.callback_query(F.data == "show_my_nfts")
async def show_my_nfts(callback: types.CallbackQuery, session: AsyncSession, bot: Bot, state: FSMContext):
    """Показать NFT пользователя."""
    await callback.answer()

    nft_service = NFTService(session)
    user_nfts = await nft_service.get_user_nfts(callback.from_user.id)

    await delete_previous_message(state, callback.message.chat.id, bot)

    # Если NFT нет - предложить загрузить
    if not user_nfts:
        new_message = await callback.message.answer(
            "💎 <b>Мои NFT</b>\n\n"
            "📦 У вас пока нет NFT.\n\n"
            "💡 Загрузите свою первую NFT или купите на маркетплейсе!",
            reply_markup=upload_nft_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, new_message.message_id)
        return

    # Показываем первый NFT
    await state.set_state(NFTState.browsing_my_nfts)
    await state.update_data(my_nfts_index=0, my_nfts_list=[nft.id for nft in user_nfts])

    await show_nft_by_index(callback.message, session, state, bot, 0, user_nfts)


async def show_nft_by_index(message, session, state, bot, index: int, nfts_list):
    """Отобразить NFT по индексу."""
    if index < 0 or index >= len(nfts_list):
        return

    nft = nfts_list[index]
    user_service = UserService(session)
    owner = await user_service.get_user_by_telegram_id(nft.owner_id)

    caption = (
        f"💎 <b>{nft.title}</b>\n\n"
        f"👤 Владелец: {owner.full_name} (UID: {owner.uid})\n"
        f"📝 Описание: {nft.description}\n"
        f"💰 Цена: <b>{nft.price}</b> TON\n"
        f"\n🆔 NFT ID: <code>{nft.id}</code>\n"
        f"📍 NFT {index + 1} из {len(nfts_list)}"
    )

    # ВСЕГДА показываем оригинал (БЕЗ водяного знака) владельцу
    photo_id = nft.photo_file_id

    await delete_previous_message(state, message.chat.id, bot)

    new_message = await message.answer_photo(
        photo=photo_id,
        caption=caption,
        reply_markup=my_nft_navigation_keyboard(index, len(nfts_list), nft.id, nft.is_on_sale),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР 3: Навигация по своим NFT ---
@router.callback_query(F.data.startswith("my_nft_next_"))
@router.callback_query(F.data.startswith("my_nft_prev_"))
async def navigate_my_nfts(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Навигация между своими NFT."""
    await callback.answer()

    data = await state.get_data()
    nft_ids = data.get('my_nfts_list', [])

    if callback.data.startswith("my_nft_next_"):
        new_index = data.get('my_nfts_index', 0) + 1
    else:
        new_index = data.get('my_nfts_index', 0) - 1

    await state.update_data(my_nfts_index=new_index)

    nft_service = NFTService(session)
    nfts = []
    for nft_id in nft_ids:
        nft = await nft_service.get_nft_by_id(nft_id)
        if nft:
            nfts.append(nft)

    await show_nft_by_index(callback.message, session, state, bot, new_index, nfts)


# --- ХЕНДЛЕР 5: Начать загрузку NFT ---
@router.callback_query(F.data == "upload_new_nft")
async def start_upload_nft(callback: types.CallbackQuery, state: FSMContext, bot: Bot, session: AsyncSession):
    """Начать процесс загрузки NFT."""
    await callback.answer()

    # ПРОВЕРКА КОШЕЛЬКА
    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)

    if not user.crypto_wallet:
        await delete_previous_message(state, callback.message.chat.id, bot)

        new_message = await callback.message.answer(
            "⚠️ <b>Кошелек не подключен</b>\n\n"
            "Для загрузки NFT необходимо подключить TON кошелек.\n\n"
            "📝 <b>Как подключить:</b>\n"
            "1. Зайдите в 'Профиль' → 'Настройки'\n"
            "2. Выберите 'Изменить кошелёк'\n"
            "3. Введите адрес вашего TON кошелька\n\n"
            "💡 Формат адреса: <code>EQ...</code> или <code>UQ...</code> (48 символов)",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚙️ Настройки профиля", callback_data="settings")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="nft_menu")]
            ]),
            parse_mode='HTML'
        )
        await set_last_message_id(state, new_message.message_id)
        return

    await delete_previous_message(state, callback.message.chat.id, bot)

    await state.set_state(NFTState.waiting_for_nft_photo)

    new_message = await callback.message.answer(
        "📤 <b>Загрузка NFT</b>\n\n"
        "📸 Отправьте изображение вашего NFT:\n\n"
        "💡 Поддерживаются форматы: JPG, PNG\n"
        "⚠️ Максимальный размер: 10 МБ",
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР 6: Получение фото NFT ---
@router.message(NFTState.waiting_for_nft_photo, F.photo)
async def receive_nft_photo(message: types.Message, state: FSMContext, bot: Bot):
    """Получить фото NFT."""
    await delete_previous_message(state, message.chat.id, bot)
    await message.delete()

    photo = message.photo[-1]
    photo_file_id = photo.file_id

    await state.update_data(nft_photo_file_id=photo_file_id)
    await state.set_state(NFTState.waiting_for_nft_title)

    new_message = await message.answer(
        "✏️ <b>Название NFT</b>\n\n"
        "Введите название для вашего NFT:\n\n"
        "💡 Максимум 100 символов",
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР 7: Получение названия NFT ---
@router.message(NFTState.waiting_for_nft_title)
async def receive_nft_title(message: types.Message, state: FSMContext, bot: Bot):
    """Получить название NFT."""
    await delete_previous_message(state, message.chat.id, bot)
    await message.delete()

    title = message.text.strip()

    if len(title) > 100:
        error_msg = await message.answer(
            "❌ Название слишком длинное (максимум 100 символов).\n\n"
            "Попробуйте снова:",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, error_msg.message_id)
        return

    await state.update_data(nft_title=title)
    await state.set_state(NFTState.waiting_for_nft_description)

    new_message = await message.answer(
        f"📝 <b>Описание NFT</b>\n\n"
        f"Название: <i>{title}</i>\n\n"
        f"Введите описание для вашего NFT:\n\n"
        f"💡 Максимум 500 символов",
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР 8: Получение описания NFT ---
@router.message(NFTState.waiting_for_nft_description)
async def receive_nft_description(message: types.Message, state: FSMContext, bot: Bot):
    """Получить описание NFT."""
    await delete_previous_message(state, message.chat.id, bot)
    await message.delete()

    description = message.text.strip()

    if len(description) > 500:
        error_msg = await message.answer(
            "❌ Описание слишком длинное (максимум 500 символов).\n\n"
            "Попробуйте снова:",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, error_msg.message_id)
        return

    await state.update_data(nft_description=description)
    await state.set_state(NFTState.waiting_for_nft_price)

    data = await state.get_data()

    new_message = await message.answer(
        f"💰 <b>Цена NFT</b>\n\n"
        f"Название: <i>{data['nft_title']}</i>\n"
        f"Описание: <i>{description}</i>\n\n"
        f"Введите цену в TON:\n\n"
        f"💡 Только целые числа (например: 100)",
        reply_markup=cancel_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР 9: Получение цены и запрос оплаты комиссии ---
@router.message(NFTState.waiting_for_nft_price)
async def receive_nft_price(message: types.Message, session: AsyncSession, state: FSMContext, bot: Bot):
    """Получить цену и запросить оплату комиссии за загрузку."""
    await delete_previous_message(state, message.chat.id, bot)
    await message.delete()

    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        error_msg = await message.answer(
            "❌ Неверный формат цены. Введите положительное число:\n\n"
            "Пример: 100",
            reply_markup=cancel_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, error_msg.message_id)
        return

    # Получаем все данные
    data = await state.get_data()

    # Рассчитываем комиссию (10% от цены NFT)
    commission = price * 0.10

    # Сохраняем цену
    await state.update_data(nft_price=price, commission=commission)

    # Формируем TON ссылку для оплаты комиссии
    commission_payment_link = f"https://app.tonkeeper.com/transfer/{ADMIN_WALLET}?amount={int(commission * 1_000_000_000)}&text=Upload_NFT_Commission"

    # Отправляем запрос на оплату комиссии
    commission_msg = await message.answer(
        f"💰 <b>Оплата комиссии за размещение</b>\n\n"
        f"💎 Название: <i>{data['nft_title']}</i>\n"
        f"📝 Описание: <i>{data['nft_description']}</i>\n"
        f"💵 Цена NFT: <b>{price}</b> TON\n\n"
        f"🏦 <b>Комиссия площадки (10%):</b> <b>{commission:.2f}</b> TON\n\n"
        f"📋 <b>Для загрузки NFT:</b>\n"
        f"1️⃣ Оплатите комиссию по кнопке ниже\n"
        f"2️⃣ Нажмите \"✅ Подтвердить оплату\"\n\n"
        f"💡 После подтверждения ваш NFT будет опубликован!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💸 Оплатить комиссию ({commission:.2f} TON)", url=commission_payment_link)],
            [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data="confirm_nft_upload")],
            [InlineKeyboardButton(text="❌ Отменить загрузку", callback_data="cancel_nft_upload")]
        ]),
        parse_mode='HTML'
    )
    await set_last_message_id(state, commission_msg.message_id)


# --- ХЕНДЛЕР: Подтверждение оплаты комиссии (отправка запроса админу) ---
@router.callback_query(F.data == "confirm_nft_upload")
async def confirm_nft_upload(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Отправка запроса администратору на проверку оплаты комиссии."""
    await callback.answer()

    # Получаем все данные
    data = await state.get_data()

    # Создаем запрос на загрузку
    nft_service = NFTService(session)
    upload_request = await nft_service.create_upload_request(
        user_id=callback.from_user.id,
        photo_file_id=data['nft_photo_file_id'],
        title=data['nft_title'],
        description=data['nft_description'],
        price=data['nft_price'],
        commission=data['commission']
    )

    await state.clear()

    await delete_previous_message(state, callback.message.chat.id, bot)

    # Уведомляем пользователя
    waiting_msg = await callback.message.answer(
        f"⏳ <b>Запрос отправлен на проверку</b>\n\n"
        f"💎 NFT: <b>{data['nft_title']}</b>\n"
        f"💰 Цена: <b>{data['nft_price']}</b> TON\n"
        f"🏦 Комиссия: <b>{data['commission']:.2f}</b> TON\n\n"
        f"📋 Ваш запрос отправлен администратору для подтверждения оплаты.\n\n"
        f"⏰ Обычно проверка занимает до 10 минут.\n"
        f"Вы получите уведомление, как только запрос будет обработан.",
        reply_markup=nft_main_menu_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, waiting_msg.message_id)

    # Отправляем запрос администратору
    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(callback.from_user.id)

    try:
        await bot.send_photo(
            ADMIN_ID,
            photo=data['nft_photo_file_id'],
            caption=f"🆕 <b>Новый запрос на загрузку NFT</b>\n\n"
                    f"👤 <b>Пользователь:</b>\n"
                    f" {user.full_name} (@{user.username or 'нет'})\n"
                    f" ID: <code>{user.telegram_id}</code>\n"
                    f" UID: <code>{user.uid}</code>\n\n"
                    f"💎 <b>Название NFT:</b> {data['nft_title']}\n"
                    f"📝 <b>Описание:</b> {data['nft_description']}\n"
                    f"💰 <b>Цена:</b> {data['nft_price']} TON\n"
                    f"🏦 <b>Комиссия (10%):</b> {data['commission']:.2f} TON\n\n"
                    f"🆔 <b>ID запроса:</b> <code>{upload_request.id}</code>\n\n"
                    f"❓ Проверьте оплату комиссии и подтвердите или отклоните запрос:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_approve_nft_{upload_request.id}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_nft_{upload_request.id}")
                ]
            ]),
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Ошибка отправки запроса администратору: {e}")


# --- ХЕНДЛЕР: Отмена загрузки NFT ---
@router.callback_query(F.data == "cancel_nft_upload")
async def cancel_nft_upload(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Отмена загрузки NFT."""
    await callback.answer("Загрузка отменена")

    await state.clear()

    await delete_previous_message(state, callback.message.chat.id, bot)

    cancel_msg = await callback.message.answer(
        "❌ <b>Загрузка NFT отменена</b>\n\n"
        "Данные не сохранены. Комиссия не списана.",
        reply_markup=nft_main_menu_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, cancel_msg.message_id)


# --- ХЕНДЛЕР 10: Маркетплейс - купить NFT ---
@router.callback_query(F.data == "buy_nft_marketplace")
async def show_marketplace(callback: types.CallbackQuery, session: AsyncSession, bot: Bot, state: FSMContext):
    """Показать маркетплейс NFT."""
    await callback.answer()

    nft_service = NFTService(session)

    # Удаляем просроченные сделки
    await nft_service.expire_old_purchases()

    # Получаем NFT на продаже (кроме своих)
    marketplace_nfts = await nft_service.get_marketplace_nfts(exclude_user_id=callback.from_user.id)

    await delete_previous_message(state, callback.message.chat.id, bot)

    if not marketplace_nfts:
        new_message = await callback.message.answer(
            "🛒 <b>Маркетплейс NFT</b>\n\n"
            "📦 Сейчас нет NFT на продаже.\n\n"
            "💡 Загрузите свой NFT и выставьте на продажу!",
            reply_markup=nft_main_menu_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, new_message.message_id)
        return

    # Показываем первый NFT
    await state.set_state(NFTState.browsing_marketplace)
    await state.update_data(marketplace_index=0, marketplace_list=[nft.id for nft in marketplace_nfts])

    await show_marketplace_nft_by_index(callback.message, session, state, bot, 0, marketplace_nfts,
                                        callback.from_user.id)


async def show_marketplace_nft_by_index(message, session, state, bot, index: int, nfts_list, user_id: int):
    """Отобразить NFT из маркетплейса по индексу."""
    if index < 0 or index >= len(nfts_list):
        return

    nft = nfts_list[index]
    user_service = UserService(session)
    nft_service = NFTService(session)

    owner = await user_service.get_user_by_telegram_id(nft.owner_id)

    # Проверяем, есть ли в избранном
    is_favorite = await nft_service.is_in_favorites(user_id, nft.id)

    # Проверяем, есть ли активная сделка
    active_purchase = await nft_service.get_active_purchase(nft.id)

    status_info = ""
    if active_purchase:
        buyer = await user_service.get_user_by_telegram_id(active_purchase.buyer_id)
        time_left = (active_purchase.expires_at - datetime.now()).total_seconds() / 60
        status_info = f"\n\n⏳ <b>Резерв:</b> {buyer.full_name} ({int(time_left)} мин.)"

    caption = (
        f"🛒 <b>Маркетплейс NFT</b>\n\n"
        f"💎 <b>{nft.title}</b>\n\n"
        f"👤 Продавец: {owner.full_name} (UID: {owner.uid})\n"
        f"📝 Описание: {nft.description}\n"
        f"💰 Цена: <b>{nft.price}</b> TON{status_info}\n\n"
        f"🆔 NFT ID: <code>{nft.id}</code>\n"
        f"📍 NFT {index + 1} из {len(nfts_list)}"
    )

    # Используем фото С ВОДЯНЫМ ЗНАКОМ для маркетплейса
    photo_id = nft.photo_file_id_watermarked if nft.photo_file_id_watermarked else nft.photo_file_id

    await delete_previous_message(state, message.chat.id, bot)

    new_message = await message.answer_photo(
        photo=photo_id,
        caption=caption,
        reply_markup=marketplace_navigation_keyboard(index, len(nfts_list), nft.id, is_favorite),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР 11: Навигация по маркетплейсу ---
@router.callback_query(F.data.startswith("market_next_"))
@router.callback_query(F.data.startswith("market_prev_"))
async def navigate_marketplace(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Навигация по маркетплейсу."""
    await callback.answer()

    data = await state.get_data()
    nft_ids = data.get('marketplace_list', [])

    if callback.data.startswith("market_next_"):
        new_index = data.get('marketplace_index', 0) + 1
    else:
        new_index = data.get('marketplace_index', 0) - 1

    await state.update_data(marketplace_index=new_index)

    nft_service = NFTService(session)
    nfts = []
    for nft_id in nft_ids:
        nft = await nft_service.get_nft_by_id(nft_id)
        if nft and nft.is_on_sale:
            nfts.append(nft)

    await show_marketplace_nft_by_index(callback.message, session, state, bot, new_index, nfts, callback.from_user.id)


# --- ХЕНДЛЕР 12: Добавить/удалить из избранного ---
@router.callback_query(F.data.startswith("fav_nft_"))
async def add_to_favorites(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Добавить NFT в избранное."""
    await callback.answer()

    nft_id = int(callback.data.split('_')[2])

    nft_service = NFTService(session)
    success = await nft_service.add_to_favorites(callback.from_user.id, nft_id)

    if success:
        await callback.answer("⭐️ Добавлено в избранное!", show_alert=True)
    else:
        await callback.answer("ℹ️ Уже в избранном", show_alert=True)

    # Обновляем отображение
    data = await state.get_data()
    nft_ids = data.get('marketplace_list', [])
    current_index = data.get('marketplace_index', 0)

    nfts = []
    for id in nft_ids:
        nft = await nft_service.get_nft_by_id(id)
        if nft and nft.is_on_sale:
            nfts.append(nft)

    await show_marketplace_nft_by_index(callback.message, session, state, bot, current_index, nfts,
                                        callback.from_user.id)


@router.callback_query(F.data.startswith("unfav_nft_"))
async def remove_from_favorites(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Удалить NFT из избранного."""
    await callback.answer()

    nft_id = int(callback.data.split('_')[2])

    nft_service = NFTService(session)
    await nft_service.remove_from_favorites(callback.from_user.id, nft_id)

    await callback.answer("💔 Удалено из избранного", show_alert=True)

    # Обновляем отображение
    data = await state.get_data()
    nft_ids = data.get('marketplace_list', [])
    current_index = data.get('marketplace_index', 0)

    nfts = []
    for id in nft_ids:
        nft = await nft_service.get_nft_by_id(id)
        if nft and nft.is_on_sale:
            nfts.append(nft)

    await show_marketplace_nft_by_index(callback.message, session, state, bot, current_index, nfts,
                                        callback.from_user.id)


# --- ХЕНДЛЕР 13: Показать избранное ---
@router.callback_query(F.data == "show_favorites")
async def show_favorites(callback: types.CallbackQuery, session: AsyncSession, bot: Bot, state: FSMContext):
    """Показать избранные NFT."""
    await callback.answer()

    nft_service = NFTService(session)
    favorite_nfts = await nft_service.get_user_favorites(callback.from_user.id)

    await delete_previous_message(state, callback.message.chat.id, bot)

    if not favorite_nfts:
        new_message = await callback.message.answer(
            "⭐️ <b>Избранное</b>\n\n"
            "📦 У вас нет избранных NFT.\n\n"
            "💡 Добавляйте понравившиеся NFT из маркетплейса!",
            reply_markup=nft_main_menu_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, new_message.message_id)
        return

    # Показываем как обычный маркетплейс
    await state.set_state(NFTState.browsing_marketplace)
    await state.update_data(marketplace_index=0, marketplace_list=[nft.id for nft in favorite_nfts])

    await show_marketplace_nft_by_index(callback.message, session, state, bot, 0, favorite_nfts, callback.from_user.id)


# --- ХЕНДЛЕР 14: Начать покупку NFT (БЕЗ КОМИССИИ) ---
@router.callback_query(F.data.startswith("buy_nft_"))
async def start_purchase(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Начать процесс покупки NFT."""
    await callback.answer()

    nft_id = int(callback.data.split('_')[2])

    nft_service = NFTService(session)
    user_service = UserService(session)

    nft = await nft_service.get_nft_by_id(nft_id)

    if not nft:
        await callback.answer("❌ NFT не найден", show_alert=True)
        return

    # Проверяем, не покупает ли пользователь свой собственный NFT
    if nft.owner_id == callback.from_user.id:
        await callback.answer("❌ Вы не можете купить собственный NFT", show_alert=True)
        return

    # Проверяем, нет ли активной сделки
    active_purchase = await nft_service.get_active_purchase(nft_id)

    if active_purchase:
        time_left = (active_purchase.expires_at - datetime.now()).total_seconds() / 60
        await callback.answer(
            f"⏳ NFT уже зарезервирован!\n\n"
            f"Подождите {int(time_left)} минут или пока сделка не будет отменена.",
            show_alert=True
        )
        return

    # Создаем сделку
    purchase = await nft_service.create_purchase(nft_id, callback.from_user.id)

    if not purchase:
        await callback.answer("❌ Не удалось создать сделку. Попробуйте позже.", show_alert=True)
        return

    # Получаем данные продавца
    seller = await user_service.get_user_by_telegram_id(nft.owner_id)

    await delete_previous_message(state, callback.message.chat.id, bot)

    # Формируем TON ссылку для оплаты продавцу (БЕЗ КОМИССИИ!)
    seller_payment_link = f"https://app.tonkeeper.com/transfer/{seller.crypto_wallet}?amount={int(nft.price * 1_000_000_000)}&text=NFT_{nft.id}"

    # Отправляем инструкции по оплате
    purchase_msg = await callback.message.answer(
        f"💰 <b>Покупка NFT</b>\n\n"
        f"💎 Название: <b>{nft.title}</b>\n"
        f"💵 Цена: <b>{nft.price}</b> TON\n\n"
        f"⏰ <b>ВАЖНО!</b> У вас есть <b>10 минут</b> на оплату.\n\n"
        f"📋 <b>Инструкция:</b>\n"
        f"1️⃣ Оплатите NFT продавцу (кнопка ниже)\n"
        f"2️⃣ Нажмите \"✅ Проверить оплату\"\n\n"
        f"💡 Комиссия уже оплачена продавцом при загрузке!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💸 Оплатить ({nft.price} TON)", url=seller_payment_link)],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_payment_{purchase.id}")],
            [InlineKeyboardButton(text="❌ Отменить покупку", callback_data=f"cancel_purchase_{purchase.id}")]
        ]),
        parse_mode='HTML'
    )
    await set_last_message_id(state, purchase_msg.message_id)


# --- ХЕНДЛЕР: Проверка оплаты (запрос подтверждения у продавца) ---
@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Покупатель нажал 'Проверить оплату' - запрашиваем подтверждение у продавца."""
    await callback.answer("Запрос отправлен продавцу...")

    purchase_id = int(callback.data.split('_')[2])

    nft_service = NFTService(session)
    user_service = UserService(session)

    # Получаем сделку
    result = await session.execute(
        select(NFTPurchase).where(NFTPurchase.id == purchase_id)
    )
    purchase = result.scalar_one_or_none()

    if not purchase or purchase.status != "pending":
        await callback.answer("❌ Сделка не найдена или уже завершена", show_alert=True)
        return

    # Проверяем срок
    if purchase.expires_at <= datetime.now():
        await nft_service.cancel_purchase(purchase_id)
        await callback.answer("⏰ Время истекло. Сделка отменена.", show_alert=True)
        return

    nft = await nft_service.get_nft_by_id(purchase.nft_id)
    buyer = await user_service.get_user_by_telegram_id(purchase.buyer_id)
    seller = await user_service.get_user_by_telegram_id(nft.owner_id)

    await delete_previous_message(state, callback.message.chat.id, bot)

    # Уведомляем покупателя
    buyer_msg = await callback.message.answer(
        f"⏳ <b>Ожидание подтверждения продавца</b>\n\n"
        f"Запрос отправлен продавцу.\n"
        f"Ожидайте подтверждения получения оплаты...",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Повторно проверить", callback_data=f"check_payment_{purchase_id}")],
            [InlineKeyboardButton(text="⚠️ Не получил подтверждения", callback_data=f"dispute_purchase_{purchase_id}")]
        ]),
        parse_mode='HTML'
    )
    await set_last_message_id(state, buyer_msg.message_id)

    # Отправляем запрос продавцу
    try:
        await bot.send_message(
            seller.telegram_id,
            f"💰 <b>Запрос подтверждения оплаты</b>\n\n"
            f"👤 Покупатель: <b>{buyer.full_name}</b> (@{buyer.username or 'нет'})\n"
            f"💎 NFT: <b>{nft.title}</b>\n"
            f"💵 Сумма: <b>{nft.price}</b> TON\n\n"
            f"🔑 Проверьте ваш кошелек:\n"
            f"<code>{seller.crypto_wallet}</code>\n\n"
            f"❓ Вы получили оплату <b>{nft.price} TON</b>?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, получил", callback_data=f"seller_confirm_{purchase_id}"),
                    InlineKeyboardButton(text="❌ Нет, не получил", callback_data=f"seller_deny_{purchase_id}")
                ]
            ]),
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Ошибка отправки продавцу: {e}")


# --- ХЕНДЛЕР: Продавец подтвердил оплату ---
@router.callback_query(F.data.startswith("seller_confirm_"))
async def seller_confirm_payment(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Продавец подтвердил получение оплаты - завершаем сделку."""
    await callback.answer("Оплата подтверждена!")

    purchase_id = int(callback.data.split('_')[2])

    nft_service = NFTService(session)
    user_service = UserService(session)

    # Получаем сделку
    result = await session.execute(
        select(NFTPurchase).where(NFTPurchase.id == purchase_id)
    )
    purchase = result.scalar_one_or_none()

    if not purchase or purchase.status != "pending":
        await callback.answer("❌ Сделка не найдена или уже завершена", show_alert=True)
        return

    # Получаем NFT
    nft = await nft_service.get_nft_by_id(purchase.nft_id)

    if not nft:
        await callback.answer("❌ NFT не найден", show_alert=True)
        return

    # Получаем покупателя и продавца
    buyer = await user_service.get_user_by_telegram_id(purchase.buyer_id)
    seller = await user_service.get_user_by_telegram_id(nft.owner_id)

    # ЗАВЕРШАЕМ СДЕЛКУ
    try:
        # Переводим NFT покупателю
        await nft_service.complete_purchase(purchase_id, buyer.telegram_id)

        # Удаляем сообщение продавца с запросом
        await callback.message.delete()

        # Уведомляем продавца об успешной продаже
        await bot.send_message(
            seller.telegram_id,
            f"✅ <b>NFT успешно продан!</b>\n\n"
            f"💎 <b>{nft.title}</b>\n"
            f"👤 Покупатель: {buyer.full_name}\n"
            f"💰 Получено: <b>{nft.price}</b> TON\n\n"
            f"📦 NFT передан покупателю.",
            parse_mode='HTML'
        )

        # Уведомляем покупателя - отправляем оригинал без водяного знака
        try:
            await bot.send_photo(
                buyer.telegram_id,
                photo=nft.photo_file_id,  # Оригинал без водяного знака
                caption=f"✅ <b>Покупка завершена!</b>\n\n"
                        f"💎 <b>{nft.title}</b>\n\n"
                        f"Поздравляем с приобретением NFT!\n"
                        f"NFT добавлен в раздел \"Мои NFT\".\n\n"
                        f"💰 Оплачено: <b>{nft.price}</b> TON\n"
                        f"✨ Вы получили оригинал без водяного знака!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💎 Мои NFT", callback_data="show_my_nfts")],
                    [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")]
                ]),
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Ошибка уведомления покупателя: {e}")

    except Exception as e:
        print(f"Ошибка при завершении покупки: {e}")
        await callback.answer("❌ Ошибка при обработке транзакции", show_alert=True)


# ============================================================================
# НОВАЯ СИСТЕМА СПОРОВ - АВТОМАТИЧЕСКИЙ ДИАЛОГ
# ============================================================================

# --- ХЕНДЛЕР: Продавец НЕ получил оплату (открывает спор) ---
@router.callback_query(F.data.startswith("seller_deny_"))
async def seller_denies_payment(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """
    Продавец нажал 'Нет, не получил' - АВТОМАТИЧЕСКИ создаем диалог.
    Это тот же процесс, что и когда покупатель открывает спор.
    """
    await callback.answer("Открываем диалог с покупателем...")

    purchase_id = int(callback.data.split('_')[2])

    nft_service = NFTService(session)
    user_service = UserService(session)
    chat_service = ChatService(session)

    # Получаем сделку
    result = await session.execute(
        select(NFTPurchase).where(NFTPurchase.id == purchase_id)
    )
    purchase = result.scalar_one_or_none()

    if not purchase or purchase.status != "pending":
        await callback.answer("❌ Сделка не найдена или уже завершена", show_alert=True)
        return

    nft = await nft_service.get_nft_by_id(purchase.nft_id)
    buyer = await user_service.get_user_by_telegram_id(purchase.buyer_id)
    seller = await user_service.get_user_by_telegram_id(nft.owner_id)

    # Проверяем, нет ли уже активного спора
    existing_dispute = await nft_service.get_dispute_by_purchase(purchase_id)

    if existing_dispute:
        await callback.answer("⚠️ Спор уже открыт", show_alert=True)
        return

    # 1. СОЗДАЕМ СПОР
    dispute = await nft_service.create_dispute(
        purchase_id=purchase_id,
        nft_id=nft.id,
        buyer_id=buyer.telegram_id,
        seller_id=seller.telegram_id
    )

    # 2. СОЗДАЕМ ЧАТ-СЕССИЮ между покупателем и продавцом
    chat_session = ChatSession(
        user1_id=buyer.telegram_id,
        user2_id=seller.telegram_id,
        is_active=True
    )
    session.add(chat_session)
    await session.commit()
    await session.refresh(chat_session)

    # 3. ПРИВЯЗЫВАЕМ ЧАТ К СПОРУ
    await nft_service.link_dispute_to_chat(dispute.id, chat_session.id)

    # 4. ПЕРЕВОДИМ ОБОИХ В СОСТОЯНИЕ ДИАЛОГА СПОРА
    from aiogram.fsm.storage.base import StorageKey

    # Создаем FSMContext для покупателя
    buyer_state_key = StorageKey(
        bot_id=bot.id,
        chat_id=buyer.telegram_id,
        user_id=buyer.telegram_id
    )
    buyer_state = FSMContext(
        storage=state.storage,
        key=buyer_state_key
    )

    # Создаем FSMContext для продавца
    seller_state_key = StorageKey(
        bot_id=bot.id,
        chat_id=seller.telegram_id,
        user_id=seller.telegram_id
    )
    seller_state = FSMContext(
        storage=state.storage,
        key=seller_state_key
    )

    # Устанавливаем СПЕЦИАЛЬНОЕ состояние спора
    await buyer_state.set_state(ChatState.in_active_chat)
    await buyer_state.update_data(
        session_id=chat_session.id,
        dispute_id=dispute.id,
        in_dispute=True,
        user_role="buyer"
    )

    await seller_state.set_state(ChatState.in_active_chat)
    await seller_state.update_data(
        session_id=chat_session.id,
        dispute_id=dispute.id,
        in_dispute=True,
        user_role="seller"
    )

    # 5. УДАЛЯЕМ ПРЕДЫДУЩИЕ СООБЩЕНИЯ И ОТКРЫВАЕМ ДИАЛОГ

    # Продавцу
    try:
        await callback.message.delete()
    except:
        pass

    seller_msg = await bot.send_message(
        seller.telegram_id,
        f"💬 <b>Диалог с покупателем открыт</b>\n\n"
        f"💎 NFT: <b>{nft.title}</b>\n"
        f"💰 Сумма: <b>{nft.price}</b> TON\n\n"
        f"👤 Собеседник: <b>{buyer.full_name}</b>\n\n"
        f"📝 <b>Вы находитесь в диалоге с покупателем.</b>\n\n"
        f"Вы не получили оплату на кошелек.\n"
        f"Обсудите ситуацию в этом диалоге.\n\n"
        f"⚠️ <b>ВАЖНО:</b> Во время спора вы не можете покинуть диалог.\n"
        f"Используйте кнопки внизу для действий:",
        reply_markup=dispute_seller_keyboard(),
        parse_mode='HTML'
    )

    # Покупателю
    buyer_msg = await bot.send_message(
        buyer.telegram_id,
        f"💬 <b>Диалог с продавцом открыт</b>\n\n"
        f"💎 NFT: <b>{nft.title}</b>\n"
        f"💰 Сумма: <b>{nft.price}</b> TON\n\n"
        f"👤 Собеседник: <b>{seller.full_name}</b>\n\n"
        f"📝 <b>Продавец открыл спор.</b>\n\n"
        f"Продавец утверждает, что не получил оплату.\n"
        f"Обсудите ситуацию в этом диалоге.\n\n"
        f"⚠️ <b>ВАЖНО:</b> Во время спора вы не можете покинуть диалог.\n"
        f"Используйте кнопки внизу для действий:",
        reply_markup=dispute_buyer_keyboard(),
        parse_mode='HTML'
    )

    # 6. УВЕДОМЛЯЕМ АДМИНИСТРАТОРА
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🚨 <b>ОТКРЫТ СПОР ПО NFT</b>\n\n"
            f"💎 NFT: <b>{nft.title}</b> (ID: {nft.id})\n"
            f"💰 Сумма: <b>{nft.price}</b> TON\n\n"
            f"👤 <b>Покупатель:</b> {buyer.full_name} (@{buyer.username or 'нет'})\n"
            f"👤 <b>Продавец:</b> {seller.full_name} (@{seller.username or 'нет'})\n\n"
            f"📋 <b>Ситуация:</b> Продавец не получил оплату\n\n"
            f"💬 Диалог между сторонами открыт.\n"
            f"Они пытаются решить проблему самостоятельно.\n\n"
            f"📊 ID спора: <code>{dispute.id}</code>\n"
            f"📊 ID чата: <code>{chat_session.id}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👀 Посмотреть детали", callback_data=f"admin_view_dispute_{dispute.id}")]
            ]),
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Ошибка уведомления администратора: {e}")


# --- ХЕНДЛЕР: Покупатель открывает спор (НЕ ПОЛУЧИЛ ПОДТВЕРЖДЕНИЯ) ---
@router.callback_query(F.data.startswith("dispute_purchase_"))
async def buyer_starts_dispute(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """
    Покупатель нажал 'Не получил подтверждения' - АВТОМАТИЧЕСКИ создаем диалог.
    БЕЗ участия администратора на начальном этапе.
    """
    await callback.answer("Открываем диалог с продавцом...")

    purchase_id = int(callback.data.split('_')[2])

    nft_service = NFTService(session)
    user_service = UserService(session)
    chat_service = ChatService(session)

    # Получаем сделку
    result = await session.execute(
        select(NFTPurchase).where(NFTPurchase.id == purchase_id)
    )
    purchase = result.scalar_one_or_none()

    if not purchase or purchase.status != "pending":
        await callback.answer("❌ Сделка не найдена или уже завершена", show_alert=True)
        return

    nft = await nft_service.get_nft_by_id(purchase.nft_id)
    buyer = await user_service.get_user_by_telegram_id(purchase.buyer_id)
    seller = await user_service.get_user_by_telegram_id(nft.owner_id)

    # Проверяем, нет ли уже активного спора
    existing_dispute = await nft_service.get_dispute_by_purchase(purchase_id)

    if existing_dispute:
        await callback.answer("⚠️ Спор уже открыт", show_alert=True)
        return

    # 1. СОЗДАЕМ СПОР
    dispute = await nft_service.create_dispute(
        purchase_id=purchase_id,
        nft_id=nft.id,
        buyer_id=buyer.telegram_id,
        seller_id=seller.telegram_id
    )

    # 2. СОЗДАЕМ ЧАТ-СЕССИЮ между покупателем и продавцом
    chat_session = ChatSession(
        user1_id=buyer.telegram_id,
        user2_id=seller.telegram_id,
        is_active=True
    )
    session.add(chat_session)
    await session.commit()
    await session.refresh(chat_session)

    # 3. ПРИВЯЗЫВАЕМ ЧАТ К СПОРУ
    await nft_service.link_dispute_to_chat(dispute.id, chat_session.id)

    # 4. ПЕРЕВОДИМ ОБОИХ В СОСТОЯНИЕ ДИАЛОГА СПОРА
    from aiogram.fsm.storage.base import StorageKey

    # Создаем FSMContext для покупателя
    buyer_state_key = StorageKey(
        bot_id=bot.id,
        chat_id=buyer.telegram_id,
        user_id=buyer.telegram_id
    )
    buyer_state = FSMContext(
        storage=state.storage,
        key=buyer_state_key
    )

    # Создаем FSMContext для продавца
    seller_state_key = StorageKey(
        bot_id=bot.id,
        chat_id=seller.telegram_id,
        user_id=seller.telegram_id
    )
    seller_state = FSMContext(
        storage=state.storage,
        key=seller_state_key
    )

    # Устанавливаем СПЕЦИАЛЬНОЕ состояние спора
    await buyer_state.set_state(ChatState.in_active_chat)
    await buyer_state.update_data(
        session_id=chat_session.id,
        dispute_id=dispute.id,
        in_dispute=True,  # ФЛАГ что это спор
        user_role="buyer"
    )

    await seller_state.set_state(ChatState.in_active_chat)
    await seller_state.update_data(
        session_id=chat_session.id,
        dispute_id=dispute.id,
        in_dispute=True,  # ФЛАГ что это спор
        user_role="seller"
    )

    # 5. УДАЛЯЕМ ПРЕДЫДУЩИЕ СООБЩЕНИЯ И ОТКРЫВАЕМ ДИАЛОГ

    # Покупателю
    try:
        await callback.message.delete()
    except:
        pass

    buyer_msg = await bot.send_message(
        buyer.telegram_id,
        f"💬 <b>Диалог со продавцом открыт</b>\n\n"
        f"💎 NFT: <b>{nft.title}</b>\n"
        f"💰 Сумма: <b>{nft.price}</b> TON\n\n"
        f"👤 Собеседник: <b>{seller.full_name}</b>\n\n"
        f"📝 <b>Вы находитесь в диалоге со продавцом.</b>\n\n"
        f"Обсудите ситуацию с оплатой.\n"
        f"Все сообщения видит только продавец.\n\n"
        f"⚠️ <b>ВАЖНО:</b> Во время спора вы не можете покинуть диалог.\n"
        f"Используйте кнопки внизу для действий:",
        reply_markup=dispute_buyer_keyboard(),
        parse_mode='HTML'
    )

    # Продавцу
    seller_msg = await bot.send_message(
        seller.telegram_id,
        f"💬 <b>Диалог с покупателем открыт</b>\n\n"
        f"💎 NFT: <b>{nft.title}</b>\n"
        f"💰 Сумма: <b>{nft.price}</b> TON\n\n"
        f"👤 Собеседник: <b>{buyer.full_name}</b>\n\n"
        f"📝 <b>Покупатель открыл спор по оплате.</b>\n\n"
        f"Покупатель утверждает, что оплатил, но вы не получили средства.\n"
        f"Обсудите ситуацию в этом диалоге.\n\n"
        f"⚠️ <b>ВАЖНО:</b> Во время спора вы не можете покинуть диалог.\n"
        f"Используйте кнопки внизу для действий:",
        reply_markup=dispute_seller_keyboard(),
        parse_mode='HTML'
    )

    # 6. УВЕДОМЛЯЕМ АДМИНИСТРАТОРА (но не включаем в диалог)
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🚨 <b>ОТКРЫТ СПОР ПО NFT</b>\n\n"
            f"💎 NFT: <b>{nft.title}</b> (ID: {nft.id})\n"
            f"💰 Сумма: <b>{nft.price}</b> TON\n\n"
            f"👤 <b>Покупатель:</b> {buyer.full_name} (@{buyer.username or 'нет'})\n"
            f"👤 <b>Продавец:</b> {seller.full_name} (@{seller.username or 'нет'})\n\n"
            f"📋 <b>Ситуация:</b> Покупатель не получил подтверждения оплаты\n\n"
            f"💬 Диалог между сторонами открыт.\n"
            f"Они пытаются решить проблему самостоятельно.\n\n"
            f"📊 ID спора: <code>{dispute.id}</code>\n"
            f"📊 ID чата: <code>{chat_session.id}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👀 Посмотреть детали", callback_data=f"admin_view_dispute_{dispute.id}")]
            ]),
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Ошибка уведомления администратора: {e}")


# --- ХЕНДЛЕР: Продавец подтверждает оплату (КНОПКА ИЗ МЕНЮ) ---
# ВАЖНО: Этот хендлер должен быть ПЕРЕД общим хендлером сообщений!
@router.message(ChatState.in_active_chat, F.text == "✅ Подтвердить оплату")
async def seller_confirms_payment_button(message: types.Message, session: AsyncSession, state: FSMContext, bot: Bot):
    """Продавец подтвердил получение оплаты через кнопку меню."""

    data = await state.get_data()
    dispute_id = data.get('dispute_id')
    user_role = data.get('user_role')

    # Проверяем, что это продавец
    if user_role != "seller":
        await message.answer("❌ Эта кнопка доступна только продавцу")
        return

    if not dispute_id:
        await message.answer("❌ Ошибка: спор не найден")
        return

    # Получаем спор
    result = await session.execute(
        select(NFTDispute).where(NFTDispute.id == dispute_id)
    )
    dispute = result.scalar_one_or_none()

    if not dispute:
        await message.answer("❌ Спор не найден")
        return

    nft_service = NFTService(session)
    user_service = UserService(session)

    nft = await nft_service.get_nft_by_id(dispute.nft_id)
    buyer = await user_service.get_user_by_telegram_id(dispute.buyer_id)
    seller = await user_service.get_user_by_telegram_id(dispute.seller_id)

    # ЗАВЕРШАЕМ СДЕЛКУ
    try:
        await nft_service.complete_purchase(dispute.purchase_id, buyer.telegram_id)
        await nft_service.resolve_dispute(dispute.id)

        # Очищаем состояния обоих
        from aiogram.fsm.storage.base import StorageKey

        buyer_state_key = StorageKey(bot_id=bot.id, chat_id=buyer.telegram_id, user_id=buyer.telegram_id)
        buyer_state = FSMContext(storage=state.storage, key=buyer_state_key)
        await buyer_state.clear()

        seller_state_key = StorageKey(bot_id=bot.id, chat_id=seller.telegram_id, user_id=seller.telegram_id)
        seller_state = FSMContext(storage=state.storage, key=seller_state_key)
        await seller_state.clear()

        # Уведомляем продавца
        await message.answer(
            f"✅ <b>Оплата подтверждена!</b>\n\n"
            f"Сделка завершена.\n"
            f"NFT передан покупателю.",
            reply_markup=remove_keyboard(),
            parse_mode='HTML'
        )

        # Уведомляем покупателя и отправляем оригинал NFT
        await bot.send_photo(
            buyer.telegram_id,
            photo=nft.photo_file_id,
            caption=f"✅ <b>Покупка завершена!</b>\n\n"
                    f"💎 <b>{nft.title}</b>\n\n"
                    f"Продавец подтвердил получение оплаты.\n"
                    f"NFT добавлен в раздел \"Мои NFT\".\n\n"
                    f"💰 Оплачено: <b>{nft.price}</b> TON",
            reply_markup=remove_keyboard(),
            parse_mode='HTML'
        )

        # Уведомляем администратора
        await bot.send_message(
            ADMIN_ID,
            f"✅ <b>Спор разрешен</b>\n\n"
            f"💎 NFT: {nft.title}\n"
            f"👤 Продавец подтвердил оплату\n"
            f"✅ Сделка завершена успешно",
            parse_mode='HTML'
        )

    except Exception as e:
        print(f"Ошибка при завершении сделки: {e}")
        await message.answer("❌ Ошибка при обработке транзакции")


# --- ХЕНДЛЕР: Покупатель запрашивает проверку (КНОПКА ИЗ МЕНЮ) ---
@router.message(ChatState.in_active_chat, F.text == "🔍 Проверить оплату")
async def buyer_requests_check_button(message: types.Message, session: AsyncSession, state: FSMContext, bot: Bot):
    """Покупатель запрашивает проверку оплаты через кнопку меню."""

    data = await state.get_data()
    dispute_id = data.get('dispute_id')
    user_role = data.get('user_role')

    # Проверяем, что это покупатель
    if user_role != "buyer":
        await message.answer("❌ Эта кнопка доступна только покупателю")
        return

    if not dispute_id:
        await message.answer("❌ Ошибка: спор не найден")
        return

    # Получаем спор
    result = await session.execute(
        select(NFTDispute).where(NFTDispute.id == dispute_id)
    )
    dispute = result.scalar_one_or_none()

    if not dispute:
        await message.answer("❌ Спор не найден")
        return

    nft_service = NFTService(session)
    user_service = UserService(session)

    nft = await nft_service.get_nft_by_id(dispute.nft_id)
    buyer = await user_service.get_user_by_telegram_id(dispute.buyer_id)
    seller = await user_service.get_user_by_telegram_id(dispute.seller_id)

    # Отправляем запрос продавцу
    await bot.send_message(
        seller.telegram_id,
        f"🔔 <b>Покупатель запрашивает проверку оплаты</b>\n\n"
        f"💰 Проверьте ваш кошелек:\n"
        f"<code>{seller.crypto_wallet}</code>\n\n"
        f"❓ Вы получили <b>{nft.price} TON</b>?\n\n"
        f"Если да - нажмите \"✅ Подтвердить оплату\"",
        parse_mode='HTML'
    )

    # Подтверждаем покупателю
    await message.answer(
        "📤 <b>Запрос отправлен продавцу</b>\n\n"
        "Ожидайте ответа...",
        parse_mode='HTML'
    )


# --- ХЕНДЛЕР: Жалоба на покупателя (ПРОДАВЕЦ) ---
@router.message(ChatState.in_active_chat, F.text == "⚠️ Жалоба на покупателя")
async def seller_complaint_button(message: types.Message, session: AsyncSession, state: FSMContext, bot: Bot):
    """Продавец отправляет жалобу администратору."""

    data = await state.get_data()
    dispute_id = data.get('dispute_id')
    user_role = data.get('user_role')

    if user_role != "seller":
        await message.answer("❌ Эта кнопка доступна только продавцу")
        return

    if not dispute_id:
        await message.answer("❌ Ошибка: спор не найден")
        return

    # Получаем спор
    result = await session.execute(
        select(NFTDispute).where(NFTDispute.id == dispute_id)
    )
    dispute = result.scalar_one_or_none()

    nft_service = NFTService(session)
    user_service = UserService(session)

    nft = await nft_service.get_nft_by_id(dispute.nft_id)
    buyer = await user_service.get_user_by_telegram_id(dispute.buyer_id)
    seller = await user_service.get_user_by_telegram_id(dispute.seller_id)

    # Отправляем жалобу администратору
    await bot.send_message(
        ADMIN_ID,
        f"🚨 <b>ЖАЛОБА ОТ ПРОДАВЦА</b>\n\n"
        f"💎 NFT: <b>{nft.title}</b>\n"
        f"💰 Сумма: <b>{nft.price}</b> TON\n\n"
        f"👤 <b>Продавец:</b> {seller.full_name} (@{seller.username or 'нет'})\n"
        f" ID: <code>{seller.telegram_id}</code>\n\n"
        f"👤 <b>Покупатель:</b> {buyer.full_name} (@{buyer.username or 'нет'})\n"
        f" ID: <code>{buyer.telegram_id}</code>\n\n"
        f"📋 <b>Жалоба:</b> Продавец сообщает о проблеме с покупателем\n\n"
        f"💬 ID спора: <code>{dispute.id}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Завершить сделку",
                                     callback_data=f"admin_force_complete_{dispute.purchase_id}"),
                InlineKeyboardButton(text="❌ Отменить сделку",
                                     callback_data=f"admin_force_cancel_{dispute.purchase_id}")
            ]
        ]),
        parse_mode='HTML'
    )

    await message.answer(
        "✅ <b>Жалоба отправлена администратору</b>\n\n"
        "Ожидайте решения...",
        parse_mode='HTML'
    )


# --- ХЕНДЛЕР: Жалоба на продавца (ПОКУПАТЕЛЬ) ---
@router.message(ChatState.in_active_chat, F.text == "⚠️ Жалоба на продавца")
async def buyer_complaint_button(message: types.Message, session: AsyncSession, state: FSMContext, bot: Bot):
    """Покупатель отправляет жалобу администратору."""

    data = await state.get_data()
    dispute_id = data.get('dispute_id')
    user_role = data.get('user_role')

    if user_role != "buyer":
        await message.answer("❌ Эта кнопка доступна только покупателю")
        return

    if not dispute_id:
        await message.answer("❌ Ошибка: спор не найден")
        return

    # Получаем спор
    result = await session.execute(
        select(NFTDispute).where(NFTDispute.id == dispute_id)
    )
    dispute = result.scalar_one_or_none()

    nft_service = NFTService(session)
    user_service = UserService(session)

    nft = await nft_service.get_nft_by_id(dispute.nft_id)
    buyer = await user_service.get_user_by_telegram_id(dispute.buyer_id)
    seller = await user_service.get_user_by_telegram_id(dispute.seller_id)

    # Отправляем жалобу администратору
    await bot.send_message(
        ADMIN_ID,
        f"🚨 <b>ЖАЛОБА ОТ ПОКУПАТЕЛЯ</b>\n\n"
        f"💎 NFT: <b>{nft.title}</b>\n"
        f"💰 Сумма: <b>{nft.price}</b> TON\n\n"
        f"👤 <b>Покупатель:</b> {buyer.full_name} (@{buyer.username or 'нет'})\n"
        f" ID: <code>{buyer.telegram_id}</code>\n\n"
        f"👤 <b>Продавец:</b> {seller.full_name} (@{seller.username or 'нет'})\n"
        f" ID: <code>{seller.telegram_id}</code>\n\n"
        f"📋 <b>Жалоба:</b> Покупатель сообщает о проблеме с продавцом\n\n"
        f"💬 ID спора: <code>{dispute.id}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Завершить сделку",
                                     callback_data=f"admin_force_complete_{dispute.purchase_id}"),
                InlineKeyboardButton(text="❌ Отменить сделку",
                                     callback_data=f"admin_force_cancel_{dispute.purchase_id}")
            ]
        ]),
        parse_mode='HTML'
    )

    await message.answer(
        "✅ <b>Жалоба отправлена администратору</b>\n\n"
        "Ожидайте решения...",
        parse_mode='HTML'
    )


# --- ХЕНДЛЕР: Администратор принудительно завершает сделку ---
@router.callback_query(F.data.startswith("admin_force_complete_"))
async def admin_force_complete(callback: types.CallbackQuery, session: AsyncSession, bot: Bot, state: FSMContext):
    """Администратор принудительно завершает сделку и закрывает спор."""
    await callback.answer("Завершаем сделку...")

    purchase_id = int(callback.data.split('_')[3])

    nft_service = NFTService(session)
    user_service = UserService(session)

    # Получаем сделку
    result = await session.execute(
        select(NFTPurchase).where(NFTPurchase.id == purchase_id)
    )
    purchase = result.scalar_one_or_none()

    if not purchase:
        await callback.answer("❌ Сделка не найдена", show_alert=True)
        return

    # Получаем спор
    dispute = await nft_service.get_dispute_by_purchase(purchase_id)

    nft = await nft_service.get_nft_by_id(purchase.nft_id)
    buyer = await user_service.get_user_by_telegram_id(purchase.buyer_id)
    seller = await user_service.get_user_by_telegram_id(nft.owner_id)

    # Завершаем сделку
    await nft_service.complete_purchase(purchase_id, buyer.telegram_id)

    if dispute:
        await nft_service.resolve_dispute(dispute.id)

    # Очищаем состояния
    from aiogram.fsm.storage.base import StorageKey

    buyer_state_key = StorageKey(bot_id=bot.id, chat_id=buyer.telegram_id, user_id=buyer.telegram_id)
    buyer_state = FSMContext(storage=state.storage, key=buyer_state_key)
    await buyer_state.clear()

    seller_state_key = StorageKey(bot_id=bot.id, chat_id=seller.telegram_id, user_id=seller.telegram_id)
    seller_state = FSMContext(storage=state.storage, key=seller_state_key)
    await seller_state.clear()

    # Уведомляем участников
    await bot.send_photo(
        buyer.telegram_id,
        photo=nft.photo_file_id,
        caption=f"✅ <b>Сделка завершена администратором</b>\n\n"
                f"💎 <b>{nft.title}</b>\n\n"
                f"Администратор подтвердил сделку.\n"
                f"NFT добавлен в \"Мои NFT\".",
        reply_markup=remove_keyboard(),
        parse_mode='HTML'
    )

    await bot.send_message(
        seller.telegram_id,
        f"✅ <b>Сделка завершена администратором</b>\n\n"
        f"💎 NFT: {nft.title}\n"
        f"💰 Сумма: {nft.price} TON\n\n"
        f"Администратор подтвердил сделку.",
        reply_markup=remove_keyboard(),
        parse_mode='HTML'
    )

    await callback.message.edit_text(
        f"✅ <b>Сделка завершена</b>\n\n"
        f"NFT передан покупателю.\n"
        f"Спор закрыт.",
        parse_mode='HTML'
    )


# --- ХЕНДЛЕР: Администратор отменяет сделку ---
@router.callback_query(F.data.startswith("admin_force_cancel_"))
async def admin_force_cancel(callback: types.CallbackQuery, session: AsyncSession, bot: Bot, state: FSMContext):
    """Администратор отменяет сделку и закрывает спор."""
    await callback.answer("Отменяем сделку...")

    purchase_id = int(callback.data.split('_')[3])

    nft_service = NFTService(session)
    user_service = UserService(session)

    result = await session.execute(
        select(NFTPurchase).where(NFTPurchase.id == purchase_id)
    )
    purchase = result.scalar_one_or_none()

    if not purchase:
        await callback.answer("❌ Сделка не найдена", show_alert=True)
        return

    dispute = await nft_service.get_dispute_by_purchase(purchase_id)

    nft = await nft_service.get_nft_by_id(purchase.nft_id)
    buyer = await user_service.get_user_by_telegram_id(purchase.buyer_id)
    seller = await user_service.get_user_by_telegram_id(nft.owner_id)

    # Отменяем сделку
    await nft_service.cancel_purchase(purchase_id)

    if dispute:
        await nft_service.resolve_dispute(dispute.id)

    # Очищаем состояния
    from aiogram.fsm.storage.base import StorageKey

    buyer_state_key = StorageKey(bot_id=bot.id, chat_id=buyer.telegram_id, user_id=buyer.telegram_id)
    buyer_state = FSMContext(storage=state.storage, key=buyer_state_key)
    await buyer_state.clear()

    seller_state_key = StorageKey(bot_id=bot.id, chat_id=seller.telegram_id, user_id=seller.telegram_id)
    seller_state = FSMContext(storage=state.storage, key=seller_state_key)
    await seller_state.clear()

    # Уведомляем участников
    await bot.send_message(
        buyer.telegram_id,
        f"❌ <b>Сделка отменена администратором</b>\n\n"
        f"💎 NFT: {nft.title}\n\n"
        f"Средства не были списаны.",
        reply_markup=remove_keyboard(),
        parse_mode='HTML'
    )

    await bot.send_message(
        seller.telegram_id,
        f"❌ <b>Сделка отменена администратором</b>\n\n"
        f"💎 NFT: {nft.title}\n\n"
        f"NFT остается у вас.",
        reply_markup=remove_keyboard(),
        parse_mode='HTML'
    )

    await callback.message.edit_text(
        f"❌ <b>Сделка отменена</b>\n\n"
        f"Спор закрыт.",
        parse_mode='HTML'
    )


# --- ХЕНДЛЕР: Обработка ОБЫЧНЫХ сообщений в споре (ПОСЛЕДНИЙ, после всех кнопок) ---
# ВАЖНО: Этот хендлер должен быть ПОСЛЕДНИМ среди хендлеров ChatState.in_active_chat!
@router.message(ChatState.in_active_chat, F.text, ~F.text.startswith('/'))
async def handle_dispute_chat_message(message: types.Message, session: AsyncSession, state: FSMContext, bot: Bot):
    """
    Обработка обычных текстовых сообщений в диалоге спора.
    Этот хендлер срабатывает ТОЛЬКО если сообщение не совпало ни с одной кнопкой выше.
    """

    data = await state.get_data()
    session_id = data.get('session_id')
    in_dispute = data.get('in_dispute', False)

    if not session_id:
        await message.answer("❌ Ошибка: активная сессия не найдена.")
        await state.clear()
        return

    # ПРОВЕРКА: Если это НЕ спор, обрабатываем как обычный чат
    if not in_dispute:
        # Здесь код обычного чата (уже есть в chats.py)
        chat_service = ChatService(session)

        await chat_service.send_message(
            session_id=session_id,
            sender_id=message.from_user.id,
            text=message.text
        )

        other_user = await chat_service.get_other_user_in_session(
            session_id,
            message.from_user.id
        )

        if other_user:
            try:
                await bot.send_message(
                    other_user.telegram_id,
                    f"💬 <b>Сообщение от собеседника:</b>\n\n{message.text}",
                    parse_mode='HTML'
                )
            except:
                pass
        return

    # ЭТО СПОР - ОБРАБОТКА СООБЩЕНИЙ В СПОРЕ

    # БЛОКИРУЕМ КОМАНДЫ ВЫХОДА
    blocked_commands = [
        "⬅️ назад", "главное меню", "выход", "покинуть",
        "отмена", "cancel", "в главное меню"
    ]

    if any(cmd in message.text.lower() for cmd in blocked_commands):
        await message.answer(
            "⚠️ <b>Во время спора вы не можете покинуть диалог!</b>\n\n"
            "Используйте кнопки внизу для действий или ожидайте решения.",
            parse_mode='HTML'
        )
        return

    # Сохраняем сообщение в БД
    chat_service = ChatService(session)
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

    # Пересылаем сообщение собеседнику
    try:
        user_service = UserService(session)
        sender = await user_service.get_user_by_telegram_id(message.from_user.id)

        await bot.send_message(
            other_user.telegram_id,
            f"💬 <b>{sender.full_name}:</b>\n\n{message.text}",
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Ошибка пересылки сообщения: {e}")
        await message.answer(
            "⚠️ Не удалось доставить сообщение. "
            "Возможно, собеседник заблокировал бота."
        )


# ============================================================================
# ОСТАЛЬНЫЕ ХЕНДЛЕРЫ (Продолжение...)
# ============================================================================

# --- ХЕНДЛЕР 16: Отмена покупки ---
@router.callback_query(F.data.startswith("cancel_purchase_"))
async def cancel_purchase_handler(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Отменить покупку."""
    await callback.answer()

    purchase_id = int(callback.data.split('_')[2])

    nft_service = NFTService(session)
    await nft_service.cancel_purchase(purchase_id)

    await delete_previous_message(state, callback.message.chat.id, bot)

    cancel_msg = await callback.message.answer(
        "❌ <b>Покупка отменена</b>\n\n"
        "Вы можете вернуться к просмотру маркетплейса.",
        reply_markup=nft_main_menu_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, cancel_msg.message_id)


# --- ХЕНДЛЕР 17: Ввод промокода ---
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
                reply_markup=nft_main_menu_keyboard()
            )
    else:
        await state.clear()

        error_msg = await message.answer(
            f"❌ <b>Промокод не найден</b>\n\n"
            f"Промокод <code>{promo_code}</code> недействителен или уже использован.\n\n"
            f"💡 Проверьте правильность ввода.",
            reply_markup=nft_main_menu_keyboard(),
            parse_mode='HTML'
        )
        await set_last_message_id(state, error_msg.message_id)


# --- ХЕНДЛЕР 18: Отмена FSM ---
@router.callback_query(F.data == "cancel_fsm_mode")
async def cancel_fsm(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Отмена любого FSM состояния."""
    await callback.answer("Отменено")
    await state.clear()

    await delete_previous_message(state, callback.message.chat.id, bot)

    cancel_msg = await callback.message.answer(
        "❌ Действие отменено.",
        reply_markup=nft_main_menu_keyboard()
    )
    await set_last_message_id(state, cancel_msg.message_id)


# --- ХЕНДЛЕР: Начать удаление NFT ---
@router.callback_query(F.data.startswith("delete_nft_"))
async def start_delete_nft(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Начать процесс удаления NFT с подтверждением кодом."""
    await callback.answer()

    nft_id = int(callback.data.split('_')[2])

    # Генерируем случайный 6-значный код
    delete_code = str(random.randint(100000, 999999))

    # Сохраняем код и ID NFT в состояние
    await state.update_data(delete_nft_id=nft_id, delete_code=delete_code)
    await state.set_state(NFTState.waiting_for_delete_code)

    await delete_previous_message(state, callback.message.chat.id, bot)

    new_message = await callback.message.answer(
        f"⚠️ <b>Удаление NFT</b>\n\n"
        f"Вы уверены, что хотите <b>полностью удалить</b> этот NFT?\n\n"
        f"<b>Это действие необратимо!</b>\n\n"
        f"Для подтверждения введите код:\n\n"
        f"<code>{delete_code}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_nft")]
        ]),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР: Подтверждение удаления кодом ---
@router.message(NFTState.waiting_for_delete_code)
async def confirm_delete_nft(message: types.Message, session: AsyncSession, state: FSMContext, bot: Bot):
    """Подтверждение удаления NFT по коду."""

    # Удаляем предыдущее сообщение бота (с кодом)
    await delete_previous_message(state, message.chat.id, bot)
    # Удаляем сообщение пользователя (введенный код)
    await message.delete()

    # Получаем данные из состояния
    data = await state.get_data()
    correct_code = data.get('delete_code')
    nft_id = data.get('delete_nft_id')

    if not correct_code or not nft_id:
        await state.clear()
        await message.answer("❌ Ошибка: данные не найдены. Попробуйте снова.")
        return

    entered_code = message.text.strip()

    # Проверяем код
    if entered_code != correct_code:
        error_msg = await message.answer(
            f"❌ <b>Неверный код!</b>\n\n"
            f"Попробуйте снова или нажмите \"Отмена\".",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_nft")]
            ]),
            parse_mode='HTML'
        )
        await set_last_message_id(state, error_msg.message_id)
        return

    # Код верный - удаляем NFT
    nft_service = NFTService(session)
    nft = await nft_service.get_nft_by_id(nft_id)

    if not nft or nft.owner_id != message.from_user.id:
        await state.clear()
        await message.answer("❌ NFT не найден или вы не владелец")
        return

    # Удаляем NFT
    await nft_service.delete_nft(nft_id)

    await state.clear()

    success_msg = await message.answer(
        f"✅ <b>NFT успешно удален!</b>\n\n"
        f"NFT \"{nft.title}\" был полностью удален из системы.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Мои NFT", callback_data="show_my_nfts")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")]
        ]),
        parse_mode='HTML'
    )
    await set_last_message_id(state, success_msg.message_id)


# --- ХЕНДЛЕР: Отмена удаления ---
@router.callback_query(F.data == "cancel_delete_nft")
async def cancel_delete_nft(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext, bot: Bot):
    """Отменить удаление NFT."""
    await callback.answer("Удаление отменено")

    await state.clear()

    # Возвращаем обратно к просмотру NFT
    await delete_previous_message(state, callback.message.chat.id, bot)

    cancel_msg = await callback.message.answer(
        "❌ Удаление отменено",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Мои NFT", callback_data="show_my_nfts")],
            [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")]
        ])
    )
    await set_last_message_id(state, cancel_msg.message_id)


# --- ХЕНДЛЕР: Администратор подтверждает загрузку NFT ---
@router.callback_query(F.data.startswith("admin_approve_nft_"))
async def admin_approve_nft(callback: types.CallbackQuery, session: AsyncSession, bot: Bot):
    """Администратор подтверждает оплату комиссии и создает NFT."""
    await callback.answer()

    request_id = int(callback.data.split('_')[3])

    nft_service = NFTService(session)
    user_service = UserService(session)

    # Получаем запрос
    upload_request = await nft_service.get_upload_request(request_id)

    if not upload_request:
        await callback.answer("❌ Запрос не найден", show_alert=True)
        return

    if upload_request.status != "pending":
        await callback.answer("⚠️ Запрос уже обработан", show_alert=True)
        return

    # СОЗДАЕМ ВОДЯНОЙ ЗНАК СРАЗУ
    try:
        # Скачиваем оригинальное фото
        file = await bot.get_file(upload_request.photo_file_id)
        photo_bytes = await bot.download_file(file.file_path)

        # Добавляем водяной знак
        watermarked_bytes = add_watermark(photo_bytes.read())

        # Загружаем фото с водяным знаком
        watermarked_photo = BufferedInputFile(watermarked_bytes, filename="watermarked.jpg")

        # Отправляем админу (чтобы получить file_id)
        sent_photo = await bot.send_photo(
            chat_id=callback.from_user.id,
            photo=watermarked_photo
        )
        watermarked_file_id = sent_photo.photo[-1].file_id

        # Удаляем временное сообщение
        await sent_photo.delete()

    except Exception as e:
        print(f"Ошибка создания водяного знака: {e}")
        watermarked_file_id = None

    # Создаем NFT (сразу на продаже)
    nft = await nft_service.approve_upload_request(request_id)

    if not nft:
        await callback.answer("❌ Ошибка при создании NFT", show_alert=True)
        return

    # Сохраняем водяной знак
    if watermarked_file_id:
        nft.photo_file_id_watermarked = watermarked_file_id
        await session.commit()

    # Получаем пользователя
    user = await user_service.get_user_by_telegram_id(upload_request.user_id)

    # Обновляем сообщение администратора
    await callback.message.edit_caption(
        caption=f"✅ <b>NFT подтвержден и опубликован на маркетплейсе</b>\n\n"
                f"👤 Пользователь: {user.full_name}\n"
                f"💎 NFT: <b>{nft.title}</b>\n"
                f"💰 Цена: {nft.price} TON\n"
                f"🏦 Комиссия получена: {upload_request.commission:.2f} TON\n\n"
                f"✨ NFT автоматически выставлен на продажу\n"
                f"🆔 NFT ID: <code>{nft.id}</code>\n"
                f"📅 Опубликовано: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        parse_mode='HTML'
    )

    # Уведомляем пользователя
    try:
        await bot.send_photo(
            upload_request.user_id,
            photo=nft.photo_file_id,
            caption=f"✅ <b>NFT опубликован на маркетплейсе!</b>\n\n"
                    f"💎 <b>{nft.title}</b>\n\n"
                    f"👤 Владелец: {user.full_name}\n"
                    f"📝 Описание: {nft.description}\n"
                    f"💰 Цена: <b>{nft.price}</b> TON\n\n"
                    f"🆔 NFT ID: <code>{nft.id}</code>\n\n"
                    f"✨ Администратор подтвердил оплату комиссии!\n"
                    f"🛒 Ваш NFT автоматически выставлен на продажу в маркетплейсе.\n"
                    f"💡 Покупатели уже могут его увидеть и купить!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Мои NFT", callback_data="show_my_nfts")],
                [InlineKeyboardButton(text="🛒 Маркетплейс", callback_data="buy_nft_marketplace")],
                [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")]
            ]),
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Ошибка уведомления пользователя: {e}")


# --- ХЕНДЛЕР: Администратор отклоняет загрузку NFT ---
@router.callback_query(F.data.startswith("admin_reject_nft_"))
async def admin_reject_nft(callback: types.CallbackQuery, session: AsyncSession, bot: Bot):
    """Администратор отклоняет запрос на загрузку NFT."""
    await callback.answer()

    request_id = int(callback.data.split('_')[3])

    nft_service = NFTService(session)
    user_service = UserService(session)

    # Получаем запрос
    upload_request = await nft_service.get_upload_request(request_id)

    if not upload_request:
        await callback.answer("❌ Запрос не найден", show_alert=True)
        return

    if upload_request.status != "pending":
        await callback.answer("⚠️ Запрос уже обработан", show_alert=True)
        return

    # Отклоняем запрос
    await nft_service.reject_upload_request(request_id)

    # Получаем пользователя
    user = await user_service.get_user_by_telegram_id(upload_request.user_id)

    # Обновляем сообщение администратора
    await callback.message.edit_caption(
        caption=f"❌ <b>Запрос отклонен</b>\n\n"
                f"👤 Пользователь: {user.full_name}\n"
                f"💎 NFT: <b>{upload_request.title}</b>\n"
                f"💰 Цена: {upload_request.price} TON\n"
                f"🏦 Комиссия: {upload_request.commission:.2f} TON\n\n"
                f"📅 Отклонено: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        parse_mode='HTML'
    )

    # Уведомляем пользователя
    try:
        await bot.send_message(
            upload_request.user_id,
            f"❌ <b>Запрос на загрузку NFT отклонен</b>\n\n"
            f"💎 NFT: <b>{upload_request.title}</b>\n"
            f"💰 Цена: {upload_request.price} TON\n\n"
            f"⚠️ <b>Причина:</b> Комиссия не подтверждена администратором.\n\n"
            f"📞 Если вы оплатили комиссию, свяжитесь с поддержкой.",
            reply_markup=nft_main_menu_keyboard(),
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Ошибка уведомления пользователя: {e}")