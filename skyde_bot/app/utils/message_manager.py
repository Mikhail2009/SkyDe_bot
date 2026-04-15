# skyde_bot/app/utils/message_manager.py
import asyncio
from typing import List, Optional
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import logging

logger = logging.getLogger(__name__)


class MessageManager:
    """Менеджер для управления сообщениями (удаление, очистка истории)."""

    def init(self, bot: Bot, state: FSMContext):
        self.bot = bot
        self.state = state
        self.user_id = None

    async def init(self, user_id: int):
        """Инициализация менеджера."""
        self.user_id = user_id

    async def delete_previous_bot_message(self):
        """Удаляет предыдущее сообщение бота из состояния."""
        data = await self.state.get_data()
        message_id = data.get("last_message_id")

        if message_id and self.user_id:
            try:
                await self.bot.delete_message(
                    chat_id=self.user_id,
                    message_id=message_id
                )
                await self.state.update_data(last_message_id=None)
                return True
            except TelegramBadRequest as e:
                if "message to delete not found" not in str(e):
                    logger.error(f"Ошибка удаления сообщения: {e}")
                await self.state.update_data(last_message_id=None)
            except Exception as e:
                logger.error(f"Ошибка удаления сообщения: {e}")

        return False

    async def delete_user_message(self, message_id: int):
        """Удаляет сообщение пользователя."""
        if self.user_id:
            try:
                await self.bot.delete_message(
                    chat_id=self.user_id,
                    message_id=message_id
                )
                return True
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение пользователя: {e}")
        return False

    async def save_bot_message(self, message_id: int):
        """Сохраняет ID сообщения бота в состояние."""
        await self.state.update_data(last_message_id=message_id)

    async def clear_chat_history(self, keep_last: int = 0):
        """
        Очищает историю чата.

        Args:
            keep_last: Сколько последних сообщений оставить
        """
        if not self.user_id:
            return

        # Этот метод сложнее, требует хранения истории сообщений
        data = await self.state.get_data()
        message_history = data.get("message_history", [])

        # Удаляем старые сообщения
        for msg_id in message_history[:-keep_last] if keep_last > 0 else message_history:
            try:
                await self.bot.delete_message(self.user_id, msg_id)
                await asyncio.sleep(0.1)  # Задержка чтобы не спамить API
            except:
                pass

        # Очищаем историю
        await self.state.update_data(
            message_history=message_history[-keep_last:] if keep_last > 0 else []
        )

    async def cleanup_after_handler(self, user_message_id: Optional[int] = None):
        """
        Очистка после обработчика.
        Удаляет предыдущее сообщение бота и сообщение пользователя.
        """
        tasks = []

        # Удаляем предыдущее сообщение бота
        tasks.append(self.delete_previous_bot_message())

        # Удаляем сообщение пользователя если передано
        if user_message_id:
            tasks.append(self.delete_user_message(user_message_id))

        # Выполняем параллельно
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Фабрика для создания менеджера
async def get_message_manager(bot: Bot, state: FSMContext, user_id: int) -> MessageManager:
    """Создает и инициализирует менеджер сообщений."""
    manager = MessageManager(bot, state)
    await manager.init(user_id)
    return manager