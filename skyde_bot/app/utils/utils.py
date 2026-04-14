# skyde_bot/app/utils/utils.py
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest  # <-- Важный импорт
import logging

logger = logging.getLogger(__name__)


# --- СУЩЕСТВУЮЩАЯ ФУНКЦИЯ ---
async def delete_previous_message(state: FSMContext, chat_id: int, bot: Bot):
    """Удаляет предыдущее сообщение бота из состояния."""
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
                logger.error(f"Ошибка удаления сообщения: {e}")
        except Exception as e:
            # Непредвиденные ошибки
            logger.error(f"Непредвиденная ошибка при удалении: {e}")


# --- НОВАЯ ФУНКЦИЯ: set_last_message_id ---
async def set_last_message_id(state: FSMContext, message_id: int | None):
    """Сохраняет ID последнего сообщения бота в FSM-контексте."""
    await state.update_data(last_message_id=message_id)


# --- НОВАЯ ФУНКЦИЯ: clear_last_message_id ---
async def clear_last_message_id(state: FSMContext):
    """Очищает ID последнего сообщения бота."""
    await state.update_data(last_message_id=None)


# --- НОВАЯ ФУНКЦИЯ: get_last_message_id ---
async def get_last_message_id(state: FSMContext) -> int | None:
    """Получает ID последнего сообщения бота из состояния."""
    data = await state.get_data()
    return data.get("last_message_id")


# --- НОВАЯ ФУНКЦИЯ: safe_message_cleanup ---
async def safe_message_cleanup(state: FSMContext, chat_id: int, bot: Bot,
                               user_message_id: int | None = None):
    """
    Безопасная очистка сообщений.

    Args:
        state: FSM контекст
        chat_id: ID чата
        bot: Объект бота
        user_message_id: ID сообщения пользователя для удаления (опционально)
    """
    try:
        # Удаляем предыдущее сообщение бота
        await delete_previous_message(state, chat_id, bot)

        # Удаляем сообщение пользователя если передано
        if user_message_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=user_message_id)
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение пользователя: {e}")

    except Exception as e:
        logger.error(f"Ошибка в safe_message_cleanup: {e}")


# --- НОВАЯ ФУНКЦИЯ: update_message_history ---
async def update_message_history(state: FSMContext, new_message_id: int,
                                 max_history: int = 5):
    """
    Обновляет историю сообщений.

    Args:
        state: FSM контекст
        new_message_id: ID нового сообщения
        max_history: Максимальное количество сообщений в истории
    """
    data = await state.get_data()
    message_history = data.get("message_history", [])

    # Добавляем новое сообщение
    message_history.append(new_message_id)

    # Ограничиваем историю
    if len(message_history) > max_history:
        message_history = message_history[-max_history:]

    # Сохраняем
    await state.update_data(message_history=message_history)


# --- НОВАЯ ФУНКЦИЯ: cleanup_message_history ---
async def cleanup_message_history(state: FSMContext, chat_id: int, bot: Bot, keep_last: int = 1):
    """
    Очищает историю сообщений.

    Args:
        state: FSM контекст
        chat_id: ID чата
        bot: Объект бота
        keep_last: Сколько последних сообщений оставить
    """
    try:
        data = await state.get_data()
        message_history = data.get("message_history", [])

        if not message_history:
            return

        # Определяем какие сообщения удалить
        if keep_last > 0:
            to_delete = message_history[:-keep_last]
            to_keep = message_history[-keep_last:]
        else:
            to_delete = message_history
            to_keep = []

        # Удаляем старые сообщения
        for msg_id in to_delete:
            try:
                await bot.delete_message(chat_id, msg_id)
            except:
                pass

        # Обновляем историю
        await state.update_data(message_history=to_keep)

    except Exception as e:
        logger.error(f"Ошибка очистки истории сообщений: {e}")