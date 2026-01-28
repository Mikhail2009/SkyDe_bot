from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from skyde_bot.app.keyboards.inline import games_menu_keyboard
from skyde_bot.app.utils.utils import delete_previous_message, set_last_message_id
import logging

logger = logging.getLogger(__name__)

router = Router()


# --- ХЕНДЛЕР 1: Показать меню игр ---
@router.callback_query(F.data == "show_games")
async def show_games_menu(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Показать меню игр"""
    await callback.answer()

    # Удаляем предыдущее сообщение
    await delete_previous_message(state, callback.message.chat.id, bot)

    new_message = await callback.message.answer(
        "🕹 <b>Меню Игр</b>\n\n"
        "Выберите игру для начала:\n\n"
        "🎰 <b>Слоты</b> - испытай удачу!\n"
        "⚽️ <b>Футбол</b> - скоро...\n"
        "🎲 <b>Кости</b> - скоро...",
        reply_markup=games_menu_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)


# --- ХЕНДЛЕР 2: Недоступные игры (кроме слотов) ---
@router.callback_query(F.data == "start_football")
async def football_not_available(callback: types.CallbackQuery):
    """Футбол еще не доступен"""
    await callback.answer(
        "⚽️ Футбол скоро будет доступен!\n\n"
        "Следите за обновлениями 🚀",
        show_alert=True
    )


@router.callback_query(F.data == "start_dice")
async def dice_not_available(callback: types.CallbackQuery):
    """Кости еще не доступны"""
    await callback.answer(
        "🎲 Кости скоро будут доступны!\n\n"
        "Следите за обновлениями 🚀",
        show_alert=True
    )

# ПРИМЕЧАНИЕ: Хендлер для game_slots находится в slots.py
# и обрабатывается там (handle_start_slots)