from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest  # <-- Важный импорт


# --- НОВАЯ ФУНКЦИЯ ---
async def set_last_message_id(state: FSMContext, message_id: int | None):
    """Сохраняет ID последнего сообщения бота в FSM-контексте."""
    await state.update_data(last_message_id=message_id)


async def delete_previous_message(state: FSMContext, chat_id: int, bot: Bot):
    data = await state.get_data()
    message_id = data.get("last_message_id")

    if message_id:
        try:
            # Пытаемся удалить сообщение
            await bot.delete_message(chat_id=chat_id, message_id=message_id)

            # Если удаление успешно, сбрасываем ID в контексте
            await state.update_data(last_message_id=None)

        except TelegramBadRequest as e:
            # Игнорируем ошибку, если сообщение не найдено (оно уже удалено)
            if "message to delete not found" in str(e):
                await state.update_data(last_message_id=None)  # Сбросить ID, чтобы не повторять попытку
                pass
            else:
                # Если это другая ошибка (нет прав, и т.д.), выводим её
                print(f"Ошибка удаления сообщения: {e}")
        except Exception as e:
            # Непредвиденные ошибки
            print(f"Непредвиденная ошибка при удалении: {e}")