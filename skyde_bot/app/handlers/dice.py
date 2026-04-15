# skyde_bot/app/handlers/dice.py
import random
import asyncio
import logging
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from skyde_bot.app.states.game_states import DiceState
from skyde_bot.app.keyboards.inline import main_menu_keyboard
from skyde_bot.app.services.user_services import UserService
from skyde_bot.app.utils.utils import delete_previous_message, set_last_message_id

router = Router()
logger = logging.getLogger(__name__)

# --- КОНФИГУРАЦИЯ КОСТЕЙ ---
MIN_BET = 100  # Минимальная ставка
MAX_BET = 10000  # Максимальная ставка


def dice_main_keyboard() -> InlineKeyboardMarkup:
    """Главная клавиатура игры в кости."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="100 G", callback_data="dice_bet_100"),
            InlineKeyboardButton(text="500 G", callback_data="dice_bet_500"),
            InlineKeyboardButton(text="1000 G", callback_data="dice_bet_1000"),
        ],
        [InlineKeyboardButton(text="🎲 Больше/Меньше", callback_data="dice_guess")],
        [InlineKeyboardButton(text="✍️ Своя ставка", callback_data="dice_custom_bet")],
        [InlineKeyboardButton(text="⬅️ Назад в меню игр", callback_data="show_games")]
    ])


def dice_guess_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для угадывания больше/меньше."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 Больше 3.5", callback_data="dice_guess_high"),
            InlineKeyboardButton(text="📉 Меньше 3.5", callback_data="dice_guess_low")
        ],
        [InlineKeyboardButton(text="🎯 Точное число", callback_data="dice_guess_exact")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="game_dice")]
    ])


async def show_dice_menu(message: Message | CallbackQuery, state: FSMContext, bot: Bot):
    """Показывает меню игры в кости."""
    if isinstance(message, CallbackQuery):
        msg = message.message
        await message.answer()
    else:
        msg = message

    await delete_previous_message(state, msg.chat.id, bot)
    await state.clear()

    welcome_text = (
        "🎲 <b>ИГРА В КОСТИ</b>\n\n"

        "🎮 <b>Как играть:</b>\n"
        "1. Выберите размер ставки\n"
        "2. Бросаются 2 виртуальные кости\n"
        "3. Сумма очков определяет результат\n\n"

        "💰 <b>ТАБЛИЦА ВЫПЛАТ:</b>\n\n"

        "🎯 <b>Угадать точное число (от 2 до 12):</b>\n"
        "• ×5 (шанс ~8.3%)\n\n"

        "📈 <b>Угадать \"Больше 3.5\":</b>\n"
        "• Сумма 4-12 → ×1.8\n"
        "• Сумма 2-3 → проигрыш\n\n"

        "📉 <b>Угадать \"Меньше 3.5\":</b>\n"
        "• Сумма 2-3 → ×1.8\n"
        "• Сумма 4-12 → проигрыш\n\n"

        "🎲 <b>Особые комбинации:</b>\n"
        "• <code>⚀⚀</code> Две единицы (2) → ×3\n"
        "• <code>⚅⚅</code> Две шестерки (12) → ×3\n"
        "• <code>⚁⚅</code> 7 очков → ×2\n\n"

        "⚠️ <b>Минимальная ставка: 100 G</b>"
    )

    new_message = await msg.answer(
        welcome_text,
        reply_markup=dice_main_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


def roll_dice() -> tuple[int, int, int]:
    """Бросает 2 кости и возвращает результаты."""
    dice1 = random.randint(1, 6)
    dice2 = random.randint(1, 6)
    total = dice1 + dice2
    return dice1, dice2, total


def get_dice_emoji(number: int) -> str:
    """Возвращает эмодзи для числа на кости."""
    emoji_map = {
        1: "⚀",
        2: "⚁",
        3: "⚂",
        4: "⚃",
        5: "⚄",
        6: "⚅"
    }
    return emoji_map.get(number, "🎲")

def calculate_dice_win(dice1: int, dice2: int, total: int, bet: int, guess_type: str = None, guess_value: int = None) -> tuple[int, str]:
    """
    Рассчитывает выигрыш в костях.

    Args:
        dice1, dice2: Значения на костях
        total: Сумма
        bet: Ставка
        guess_type: Тип ставки ('high', 'low', 'exact')
        guess_value: Значение для точной ставки

    Returns:
        tuple: (win_amount, result_type)
    """

    # ОСОБЫЕ КОМБИНАЦИИ
    if dice1 == 1 and dice2 == 1:  # Две единицы
        return bet * 3, "two_ones"

    if dice1 == 6 and dice2 == 6:  # Две шестерки
        return bet * 3, "two_sixes"

    if total == 7:  # Сумма 7
        return bet * 2, "lucky_seven"

    # УГАДЫВАНИЕ
    if guess_type == "exact" and guess_value == total:
        return bet * 5, "exact_guess"

    if guess_type == "high" and total >= 4:
        return int(bet * 1.8), "high_guess"

    if guess_type == "low" and total <= 3:
        return int(bet * 1.8), "low_guess"

    # ПРОИГРЫШ
    return 0, "lose"


async def play_dice_game(user_id: int, bet: int, user_service: UserService,
                        bot: Bot, state: FSMContext, guess_type: str = None, guess_value: int = None):
    """Основная функция игры в кости."""

    try:
        # Проверяем баланс
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

        # Отправляем сообщение "Бросаем кости..."
        rolling_msg = await bot.send_message(
            user_id,
            "🎲 Бросаем кости...\n\n"
            "⚀ ⚁ ⚂ ⚃ ⚄ ⚅",
            parse_mode='HTML'
        )

        # Создаем эффект ожидания
        await asyncio.sleep(2)

        # Бросаем кости
        dice1, dice2, total = roll_dice()
        dice_emoji1 = get_dice_emoji(dice1)
        dice_emoji2 = get_dice_emoji(dice2)

        # Рассчитываем выигрыш
        win_amount, result_type = calculate_dice_win(dice1, dice2, total, bet, guess_type, guess_value)

        # Обновляем баланс если выигрыш
        if win_amount > 0:
            new_balance = await user_service.update_balance(user_id, win_amount)
        else:
            user = await user_service.get_user_by_telegram_id(user_id)
            new_balance = user.balance_g

        # Формируем текст результата
        result_text = f"🎲 <b>Результат: {dice_emoji1} + {dice_emoji2} = {total}</b>\n\n"

        if result_type == "two_ones":
            result_text += (
                f"🎯 <b>ДВЕ ЕДИНИЦЫ!</b>\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"💰 Выигрыш: <b>+{win_amount}</b> G (×3)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G"
            )

        elif result_type == "two_sixes":
            result_text += (
                f"🎯 <b>ДВЕ ШЕСТЕРКИ!</b>\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"💰 Выигрыш: <b>+{win_amount}</b> G (×3)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G"
            )

        elif result_type == "lucky_seven":
            result_text += (
                f"🍀 <b>СЧАСТЛИВАЯ СЕМЕРКА!</b>\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"💰 Выигрыш: <b>+{win_amount}</b> G (×2)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G"
            )

        elif result_type == "exact_guess":
            result_text += (
                f"🎯 <b>ТОЧНОЕ УГАДЫВАНИЕ!</b>\n\n"
                f"Вы угадали число {total}!\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"💰 Выигрыш: <b>+{win_amount}</b> G (×5)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G"
            )

        elif result_type == "high_guess":
            result_text += (
                f"📈 <b>УГАДАЛИ \"БОЛЬШЕ 3.5\"!</b>\n\n"
                f"Сумма: {total} (> 3.5)\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"💰 Выигрыш: <b>+{win_amount}</b> G (×1.8)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G"
            )

        elif result_type == "low_guess":
            result_text += (
                f"📉 <b>УГАДАЛИ \"МЕНЬШЕ 3.5\"!</b>\n\n"
                f"Сумма: {total} (< 3.5)\n\n"
                f"💵 Ставка: <b>{bet}</b> G\n"
                f"💰 Выигрыш: <b>+{win_amount}</b> G (×1.8)\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G"
            )

        else:  # lose
            if guess_type == "high":
                guess_text = f"вы поставили на 'Больше 3.5', а выпало {total}"
            elif guess_type == "low":
                guess_text = f"вы поставили на 'Меньше 3.5', а выпало {total}"
            elif guess_type == "exact":
                guess_text = f"вы ставили на {guess_value}, а выпало {total}"
            else:
                guess_text = "не повезло"

            result_text += (
                f"😔 <b>Не повезло</b>\n\n"
                f"{guess_text}.\n\n"
                f"💵 Ставка: <b>-{bet}</b> G\n"
                f"💼 Баланс: <b>{new_balance:.2f}</b> G\n\n"
                f"💡 Попробуйте еще раз!"
            )

        # Удаляем сообщение "Бросаем кости..."
        await rolling_msg.delete()

        # Отправляем результат
        result_msg = await bot.send_message(
            user_id,
            result_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎲 Играть снова", callback_data="game_dice")],
                [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")]
            ]),
            parse_mode='HTML'
        )

        await set_last_message_id(state, result_msg.message_id)

        # Логируем
        logger.info(f"🎲 User {user_id}: {dice1}+{dice2}={total} | Bet: {bet}, Win: {win_amount}")

    except Exception as e:
        logger.error(f"Ошибка в play_dice_game: {e}", exc_info=True)
        await bot.send_message(
            user_id,
            "❌ Произошла ошибка. Попробуйте позже.",
            reply_markup=main_menu_keyboard()
        )
    finally:
        await state.clear()


# --- ХЕНДЛЕРЫ ---

# 1. Запуск игры в кости
@router.callback_query(F.data == "game_dice")
async def handle_start_dice(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Запуск игры в кости."""
    logger.info("Запуск игры в кости")
    await show_dice_menu(callback, state, bot)


# 2. Быстрая ставка
@router.callback_query(F.data.startswith("dice_bet_"))
async def handle_dice_bet(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    """Обработка быстрой ставки в костях."""
    await callback.answer()

    bet = int(callback.data.split('_')[2])
    user_id = callback.from_user.id

    await delete_previous_message(state, callback.message.chat.id, bot)

    user_service = UserService(session)
    await play_dice_game(user_id, bet, user_service, bot, state)


# 3. Режим угадывания
@router.callback_query(F.data == "dice_guess")
async def handle_dice_guess_mode(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Переход в режим угадывания."""
    await callback.answer()

    await state.set_state(DiceState.waiting_for_bet)
    await state.update_data(game_mode="guess")

    await delete_previous_message(state, callback.message.chat.id, bot)

    await callback.message.answer(
        "🎲 <b>Режим угадывания</b>\n\n"
        "Выберите тип ставки:",
        reply_markup=dice_guess_keyboard(),
        parse_mode='HTML'
    )


# 4. Угадать "Больше 3.5"
@router.callback_query(F.data == "dice_guess_high")
async def handle_dice_guess_high(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Ставка на 'Больше 3.5'."""
    await callback.answer()

    await state.update_data(guess_type="high")
    await state.set_state(DiceState.waiting_for_bet_amount)

    await delete_previous_message(state, callback.message.chat.id, bot)

    await callback.message.answer(
        "📈 <b>Ставка на 'Больше 3.5'</b>\n\n"
        f"Вы поставите, что сумма на костях будет 4-12.\n"
        f"Выигрыш: ×1.8\n\n"
        f"Введите размер ставки (от {MIN_BET} до {MAX_BET} G):",
        parse_mode='HTML'
    )


# 5. Угадать "Меньше 3.5"
@router.callback_query(F.data == "dice_guess_low")
async def handle_dice_guess_low(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Ставка на 'Меньше 3.5'."""
    await callback.answer()

    await state.update_data(guess_type="low")
    await state.set_state(DiceState.waiting_for_bet_amount)

    await delete_previous_message(state, callback.message.chat.id, bot)

    await callback.message.answer(
        "📉 <b>Ставка на 'Меньше 3.5'</b>\n\n"
        f"Вы поставите, что сумма на костях будет 2-3.\n"
        f"Выигрыш: ×1.8\n\n"
        f"Введите размер ставки (от {MIN_BET} до {MAX_BET} G):",
        parse_mode='HTML'
    )


# 6. Угадать точное число
@router.callback_query(F.data == "dice_guess_exact")
async def handle_dice_guess_exact(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Ставка на точное число."""
    await callback.answer()

    await state.set_state(DiceState.waiting_for_exact_number)

    await delete_previous_message(state, callback.message.chat.id, bot)

    await callback.message.answer(
        "🎯 <b>Угадать точное число</b>\n\n"
        "Введите число от 2 до 12, которое по вашему мнению выпадет на двух костях:\n\n"
        "💡 Шанс угадать: ~8.3%\n"
        "💰 Выигрыш: ×5",
        parse_mode='HTML'
    )


# 7. Обработка ввода точного числа
@router.message(DiceState.waiting_for_exact_number)
async def handle_exact_number_input(message: Message, state: FSMContext, bot: Bot):
    """Обработка введенного числа для угадывания."""
    await message.delete()

    try:
        number = int(message.text.strip())

        if number < 2 or number > 12:
            raise ValueError

        await state.update_data(guess_type="exact", guess_value=number)
        await state.set_state(DiceState.waiting_for_bet_amount)

        await delete_previous_message(state, message.chat.id, bot)

        await message.answer(
            f"🎯 <b>Ставка на число {number}</b>\n\n"
            f"Вы поставили на точное число {number}.\n"
            f"Выигрыш: ×5\n\n"
            f"Введите размер ставки (от {MIN_BET} до {MAX_BET} G):",
            parse_mode='HTML'
        )

    except ValueError:
        await message.answer(
            "❌ Введите число от 2 до 12:",
            parse_mode='HTML'
        )


# 8. Обработка ввода ставки для угадывания
@router.message(DiceState.waiting_for_bet_amount)
async def handle_guess_bet_input(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    """Обработка ставки для режима угадывания."""
    await message.delete()

    try:
        bet = int(message.text.strip())

        if bet < MIN_BET:
            raise ValueError(f"Минимум {MIN_BET} G")
        if bet > MAX_BET:
            raise ValueError(f"Максимум {MAX_BET} G")

        data = await state.get_data()
        guess_type = data.get('guess_type')
        guess_value = data.get('guess_value')

        user_id = message.from_user.id
        user_service = UserService(session)

        await delete_previous_message(state, message.chat.id, bot)
        await play_dice_game(user_id, bet, user_service, bot, state, guess_type, guess_value)

    except ValueError as e:
        await message.answer(
            f"❌ Ошибка: {e}\n\n"
            f"Введите число от {MIN_BET} до {MAX_BET}:",
            parse_mode='HTML'
        )


# 9. Своя ставка (без угадывания)
@router.callback_query(F.data == "dice_custom_bet")
async def handle_dice_custom_bet(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Ввод своей ставки без угадывания."""
    await callback.answer()

    await state.set_state(DiceState.waiting_for_bet_amount)
    await state.update_data(guess_type=None)

    await delete_previous_message(state, callback.message.chat.id, bot)

    await callback.message.answer(
        "✍️ <b>Своя ставка</b>\n\n"
        f"Введите размер ставки (от {MIN_BET} до {MAX_BET} G):\n\n"
        "💡 Простая игра - бросаются кости, выигрыш по особым комбинациям",
        parse_mode='HTML'
    )


# 10. Отмена
@router.callback_query(F.data == "cancel_dice")
async def handle_cancel_dice(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Отмена и возврат в меню костей."""
    await callback.answer("Отменено")
    await state.clear()
    await show_dice_menu(callback, state, bot)