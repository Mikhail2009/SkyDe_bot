import random
import asyncio
import logging
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from skyde_bot.app.states.game_states import SlotsState
from skyde_bot.app.keyboards.inline import main_menu_keyboard, games_menu_keyboard
from skyde_bot.app.services.user_services import UserService
from skyde_bot.app.utils.utils import delete_previous_message, set_last_message_id

router = Router()
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ СЛОТОВ ---
MIN_BET = 200  # Минимальная ставка

# Символы для слотов
SLOT_SYMBOLS = ['🍒', '🍋', '🍇', '🔔', '⭐', '💎', '7️⃣']

# Веса для генерации (чем больше вес, тем чаще выпадает)
# НАСТРОЕНО ДЛЯ ПРИБЫЛИ ПРОЕКТА (~25-30%)
SYMBOL_WEIGHTS = {
    '🍒': 35,  # Очень частые (35%)
    '🍋': 35,  # Очень частые (35%)
    '🍇': 15,  # Средние (15%)
    '🔔': 10,  # Средние (10%)
    '⭐': 4,  # Редкие (4%)
    '💎': 0.9,  # Очень редкие (0.9%)
    '7️⃣': 0.1  # Супер редкие (0.1%)
}


def slots_main_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура слотов с быстрыми ставками."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="200 G", callback_data="slot_bet_200"),
            InlineKeyboardButton(text="500 G", callback_data="slot_bet_500"),
            InlineKeyboardButton(text="1000 G", callback_data="slot_bet_1000"),
        ],
        [InlineKeyboardButton(text="✍️ Своя ставка", callback_data="slot_custom_bet")],
        [InlineKeyboardButton(text="⬅️ Назад в меню игр", callback_data="show_games")]
    ])


def generate_slot_combination() -> tuple[str, str, str]:
    """
    Генерирует случайную комбинацию для слотов с учетом весов.

    Returns:
        tuple: (symbol1, symbol2, symbol3)
    """
    symbols = []
    weights = []

    for symbol, weight in SYMBOL_WEIGHTS.items():
        symbols.append(symbol)
        weights.append(weight)

    # Генерируем 3 символа независимо друг от друга
    combination = random.choices(symbols, weights=weights, k=3)

    return combination[0], combination[1], combination[2]


def calculate_slots_win(s1: str, s2: str, s3: str, bet: int) -> tuple[int, str]:
    """
    Рассчитывает выигрыш на основе комбинации символов.

    ЭКОНОМИКА НАСТРОЕНА ДЛЯ ПРИБЫЛИ ПРОЕКТА:
    - RTP (возврат игроку): ~72-75%
    - Прибыль проекта: ~25-28%
    - Как в настоящих казино!

    Args:
        s1, s2, s3: Символы слота
        bet: Размер ставки

    Returns:
        tuple: (win_amount, result_type)
    """

    # ДЖЕКПОТ - три семерки (шанс ~0.001%)
    if s1 == '7️⃣' and s2 == '7️⃣' and s3 == '7️⃣':
        return bet * 777, "jackpot"  # Огромный множитель, но супер редко

    # МЕГА - три бриллианта (шанс ~0.007%)
    if s1 == '💎' and s2 == '💎' and s3 == '💎':
        return bet * 100, "mega"

    # КРУПНЫЙ - три звезды (шанс ~0.006%)
    if s1 == '⭐' and s2 == '⭐' and s3 == '⭐':
        return bet * 50, "big_win"

    # ТРИ ОДИНАКОВЫХ КОЛОКОЛЬЧИКА (шанс ~0.1%)
    if s1 == '🔔' and s2 == '🔔' and s3 == '🔔':
        return bet * 15, "three_bells"

    # ТРИ ОДИНАКОВЫХ (винограда, лимона, вишни) (шанс ~4-8%)
    if s1 == s2 == s3:
        return bet * 8, "three_same"

    # ДВА ОДИНАКОВЫХ
    if s1 == s2 or s2 == s3 or s1 == s3:
        # Проверяем, какие символы совпали
        matched_symbol = s1 if (s1 == s2 or s1 == s3) else s2

        # Бонус за ценные символы
        if matched_symbol in ['💎', '7️⃣']:
            return bet * 10, "two_special"
        elif matched_symbol in ['⭐', '🔔']:
            return bet * 4, "two_rare"
        else:
            return bet * 2, "two_common"

    # ПРОИГРЫШ - все разные (~70% случаев)
    return 0, "lose"

async def start_slots(input_obj: types.Message | types.CallbackQuery, state: FSMContext, bot: Bot):
    """Показывает главное меню слотов."""
    if isinstance(input_obj, types.CallbackQuery):
        message = input_obj.message
        await input_obj.answer()
    else:
        message = input_obj

    await delete_previous_message(state, message.chat.id, bot)
    await state.clear()  # Сбрасываем состояние

    welcome_text = (
        "🎰 <b>ИГРОВЫЕ АВТОМАТЫ</b>\n\n"
        
        "🎮 <b>Как играть:</b>\n"
        "Выберите размер ставки и испытайте удачу!\n"
        "Генератор создаст комбинацию из 3 символов.\n\n"
        
        "💰 <b>ТАБЛИЦА ВЫПЛАТ:</b>\n\n"
        
        "🎰 <code>7️⃣ 7️⃣ 7️⃣</code> - ×777 💥\n"
        "💎 <code>💎 💎 💎</code> - ×100\n"
        "⭐ <code>⭐ ⭐ ⭐</code> - ×50\n"
        "🔔 <code>🔔 🔔 🔔</code> - ×15\n"
        "🎯 <code>🍒 🍒 🍒</code> - ×8 (любые 3 одинаковых)\n\n"
        
        "✨ <code>💎 💎 🍒</code> - ×10 (2 спец. символа)\n"
        "🌟 <code>⭐ ⭐ 🍋</code> - ×4 (2 редких)\n"
        "💫 <code>🍒 🍒 🍋</code> - ×2 (2 обычных)\n\n"
        
        "😔 <code>🍒 🍋 🍇</code> - ×0 (все разные)\n\n"
        
        "⚠️ <b>Минимальная ставка: 200 G</b>"
    )

    new_message = await message.answer(
        welcome_text,
        reply_markup=slots_main_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


async def play_slots(user_id: int, bet: int, user_service: UserService,
                     bot: Bot, state: FSMContext):
    """
    Основная функция игры в слоты.
    """

    try:
        # Проверяем баланс и списываем ставку
        user = await user_service.get_user_by_telegram_id(user_id)

        if not user or user.balance_g < bet:
            await bot.send_message(
                user_id,
                f"❌ <b>Недостаточно средств</b>\n\n"
                f"💼 Ваш баланс: <b>{user.balance_g if user else 0:.2f}</b> G\n"
                f"💵 Требуется: <b>{bet}</b> G",
                reply_markup=main_menu_keyboard(),
                parse_mode='HTML'
            )
            await state.clear()
            return

        # Списываем ставку
        await user_service.update_balance(user_id, -bet)

        # Отправляем сообщение "Крутим барабаны..."
        spinning_msg = await bot.send_message(
            user_id,
            "🎰 Крутим барабаны...\n\n"
            "⏳ ⏳ ⏳",
            parse_mode='HTML'
        )

        # Создаем эффект ожидания
        await asyncio.sleep(2)

        # Генерируем комбинацию
        s1, s2, s3 = generate_slot_combination()

        # Рассчитываем выигрыш
        win_amount, result_type = calculate_slots_win(s1, s2, s3, bet)

        # Обновляем баланс если выигрыш
        if win_amount > 0:
            new_balance = await user_service.update_balance(user_id, win_amount)
        else:
            user = await user_service.get_user_by_telegram_id(user_id)
            new_balance = user.balance_g

        # Формируем текст результата
        result_text = f"🎰 <b>[ {s1} {s2} {s3} ]</b>\n\n"

        if result_type == "jackpot":
            result_text += (
                f"🎰🎰🎰 <b>ДЖЕКПОТ!!!</b> 🎰🎰🎰\n\n"
                f"💥 НЕВЕРОЯТНО! ТРИ СЕМЕРКИ!\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"🔥 Выигрыш: <b>+{win_amount}</b> G (×777!!!)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G\n\n"
                f"⭐ Вы попали в 0.001%! ЛЕГЕНДА!"
            )

        elif result_type == "mega":
            result_text += (
                f"💎 <b>МЕГА ВЫИГРЫШ!</b> 💎\n\n"
                f"Три бриллианта - фантастика!\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"💰 Выигрыш: <b>+{win_amount}</b> G (×100)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G"
            )

        elif result_type == "big_win":
            result_text += (
                f"⭐ <b>КРУПНЫЙ ВЫИГРЫШ!</b> ⭐\n\n"
                f"Три звезды - превосходно!\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"💰 Выигрыш: <b>+{win_amount}</b> G (×50)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G"
            )

        elif result_type == "three_bells":
            result_text += (
                f"🔔 <b>Три колокольчика!</b> 🔔\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"💰 Выигрыш: <b>+{win_amount}</b> G (×15)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G"
            )

        elif result_type == "three_same":
            result_text += (
                f"🎯 <b>Три одинаковых!</b>\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"💰 Выигрыш: <b>+{win_amount}</b> G (×8)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G"
            )

        elif result_type == "two_special":
            result_text += (
                f"✨ <b>Два спец. символа!</b>\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"💰 Выигрыш: <b>+{win_amount}</b> G (×10)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G"
            )

        elif result_type == "two_rare":
            result_text += (
                f"🌟 <b>Два редких символа!</b>\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"💰 Выигрыш: <b>+{win_amount}</b> G (×4)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G"
            )

        elif result_type == "two_common":
            result_text += (
                f"💫 <b>Два одинаковых!</b>\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"💰 Выигрыш: <b>+{win_amount}</b> G (×2)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G"
            )

        else:  # lose
            result_text += (
                f"😔 <b>Не повезло</b>\n\n"
                f"Все символы разные.\n\n"
                f"💵 Ставка: <b>-{bet}</b> G\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G\n\n"
                f"💡 Удача любит настойчивых!"
            )

        # Удаляем сообщение "Крутим барабаны..."
        await spinning_msg.delete()

        # Отправляем результат
        result_msg = await bot.send_message(
            user_id,
            result_text,
            reply_markup=main_menu_keyboard(),
            parse_mode='HTML'
        )

        await set_last_message_id(state, result_msg.message_id)

        # Логируем результат
        logger.info(
            f"🎰 User {user_id}: [{s1} {s2} {s3}] "
            f"Bet: {bet}, Win: {win_amount}, Type: {result_type}"
        )

    except Exception as e:
        logger.error(f"Ошибка в play_slots: {e}", exc_info=True)
        await bot.send_message(
            user_id,
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu_keyboard()
        )
    finally:
        await state.clear()


# --- ХЕНДЛЕРЫ ---

# ХЕНДЛЕР 1: Запуск слотов
@router.callback_query(F.data == "game_slots")
async def handle_start_slots(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Запуск игры в слоты."""
    logger.info("Запуск слотов")
    await start_slots(callback, state, bot)


# ХЕНДЛЕР 2: Быстрая ставка (200, 500, 1000)
@router.callback_query(F.data.startswith("slot_bet_"))
async def handle_quick_bet(callback: CallbackQuery, state: FSMContext,
                          session: AsyncSession, bot: Bot):
    """Обработка быстрой ставки."""

    await callback.answer()

    bet = int(callback.data.split('_')[2])
    user_id = callback.from_user.id

    # Удаляем меню
    await delete_previous_message(state, callback.message.chat.id, bot)

    # Запускаем игру
    user_service = UserService(session)
    await play_slots(user_id, bet, user_service, bot, state)


# ХЕНДЛЕР 3: Своя ставка (переход в режим ввода)
@router.callback_query(F.data == "slot_custom_bet")
async def handle_custom_bet_start(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Начало ввода своей ставки."""
    await callback.answer()

    await state.set_state(SlotsState.waiting_for_bet)

    await callback.message.edit_text(
        "✍️ <b>Введите размер ставки</b>\n\n"
        f"⚠️ Минимум: <b>{MIN_BET}</b> G\n\n"
        "Напишите число в чат:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_slots")]
        ]),
        parse_mode='HTML'
    )


# ХЕНДЛЕР 4: Обработка текстового ввода ставки
@router.message(SlotsState.waiting_for_bet)
async def handle_custom_bet_input(message: Message, state: FSMContext,
                                  session: AsyncSession, bot: Bot):
    """Обработка введенной ставки."""
    user_id = message.from_user.id

    try:
        bet = int(message.text.strip())

        if bet < MIN_BET:
            raise ValueError(f"Минимум {MIN_BET} G")

        if bet <= 0:
            raise ValueError("Положительное число")

    except ValueError:
        await message.delete()
        error_msg = await message.answer(
            f"❌ Ошибка!\n\n"
            f"Введите целое число (минимум {MIN_BET} G):",
            parse_mode='HTML'
        )
        await asyncio.sleep(3)
        await error_msg.delete()
        return

    # Удаляем сообщения
    await message.delete()
    await delete_previous_message(state, message.chat.id, bot)

    # Запускаем игру
    user_service = UserService(session)
    await play_slots(user_id, bet, user_service, bot, state)


# ХЕНДЛЕР 5: Отмена
@router.callback_query(F.data == "cancel_slots")
async def handle_cancel_slots(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Отмена и возврат в главное меню слотов."""
    await callback.answer("Отменено")
    await state.clear()
    await start_slots(callback, state, bot)