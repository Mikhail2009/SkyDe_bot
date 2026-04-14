from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from skyde_bot.app.keyboards.inline import main_menu_keyboard
from skyde_bot.app.utils.utils import delete_previous_message, set_last_message_id

router = Router()


@router.callback_query(F.data == "main_menu_return")
async def process_main_menu_return(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """
    ГЛОБАЛЬНЫЙ хендлер возврата в главное меню.
    Вызывается из любого раздела: Профиль, Игры, NFT, Поддержка.
    """
    await callback.answer()

    # 1. Сброс FSM-состояния
    await state.clear()

    # 2. КРИТИЧЕСКОЕ: Удаление предыдущего сообщения
    await delete_previous_message(state, callback.message.chat.id, bot)

    # 3. Отправка главного меню
    new_message = await callback.message.answer(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=main_menu_keyboard(),
        parse_mode='HTML'
    )
    await set_last_message_id(state, new_message.message_id)