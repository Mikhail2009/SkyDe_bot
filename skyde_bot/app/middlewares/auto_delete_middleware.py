# skyde_bot/app/middlewares/auto_delete_middleware.py
import asyncio
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class AutoDeleteMiddleware(BaseMiddleware):
    """Middleware для автоматического удаления сообщений."""

    def __init__(self, delete_previous: bool = True, delete_user: bool = True,
             delay_bot: int = 0, delay_user: int = 0):
        """
        Args:
            delete_previous: Удалять ли предыдущее сообщение бота
            delete_user: Удалять ли сообщения пользователя
            delay_bot: Задержка перед удалением сообщений бота (секунды)
            delay_user: Задержка перед удалением сообщений пользователя (секунды)
        """
        self.delete_previous = delete_previous
        self.delete_user = delete_user
        self.delay_bot = delay_bot
        self.delay_user = delay_user
        super().__init__()

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        """Основной метод middleware."""

        bot: Bot = data.get("bot")
        state: FSMContext = data.get("state")

        if not bot or not state:
            return await handler(event, data)

        # Получаем предыдущее сообщение бота из состояния
        state_data = await state.get_data()
        last_bot_message_id = state_data.get("last_message_id")

        try:
            # Удаляем предыдущее сообщение бота
            if self.delete_previous and last_bot_message_id:
                if self.delay_bot > 0:
                    await asyncio.sleep(self.delay_bot)

                try:
                    await bot.delete_message(
                        chat_id=event.from_user.id,
                        message_id=last_bot_message_id
                    )
                    logger.debug(f"Удалено предыдущее сообщение бота: {last_bot_message_id}")
                except Exception as e:
                    logger.debug(f"Не удалось удалить предыдущее сообщение: {e}")

            # Удаляем сообщение пользователя (если это Message)
            if self.delete_user and isinstance(event, Message):
                if self.delay_user > 0:
                    await asyncio.sleep(self.delay_user)

                try:
                    await event.delete()
                    logger.debug(f"Удалено сообщение пользователя: {event.message_id}")
                except Exception as e:
                    logger.debug(f"Не удалось удалить сообщение пользователя: {e}")

            # Вызываем основной обработчик
            result = await handler(event, data)

            # Сохраняем ID нового сообщения бота (если оно было отправлено)
            if isinstance(event, CallbackQuery) and hasattr(event, 'message'):
                # Для CallbackQuery - не обновляем, т.к. сообщение уже старое
                pass
            elif result and hasattr(result, 'message_id'):
                # Если handler вернул Message
                await state.update_data(last_message_id=result.message_id)
                logger.debug(f"Сохранено новое сообщение бота: {result.message_id}")

            return result

        except Exception as e:
            logger.error(f"Ошибка в AutoDeleteMiddleware: {e}")
            return await handler(event, data)


class SmartAutoDeleteMiddleware(BaseMiddleware):
    """Умный middleware с разной логикой для разных типов сообщений."""

    def __init__(self):
        # Настройки для разных типов сообщений
        self.settings = {
            'command': {'delete_previous': True, 'delete_user': True, 'delay_user': 1},
            'text': {'delete_previous': True, 'delete_user': True, 'delay_user': 2},
            'callback': {'delete_previous': True, 'delete_user': False},
            'photo': {'delete_previous': True, 'delete_user': True, 'delay_user': 3},
        }
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:

        bot: Bot = data.get("bot")
        state: FSMContext = data.get("state")

        if not bot or not state:
            return await handler(event, data)

        # Определяем тип события
        event_type = self._get_event_type(event)
        settings = self.settings.get(event_type, {})

        # Получаем предыдущее сообщение бота
        state_data = await state.get_data()
        last_bot_message_id = state_data.get("last_message_id")

        try:
            # Удаляем предыдущее сообщение бота
            if settings.get('delete_previous', True) and last_bot_message_id:
                delay = settings.get('delay_bot', 0)
                if delay > 0:
                    await asyncio.sleep(delay)

                try:
                    await bot.delete_message(
                        chat_id=event.from_user.id,
                        message_id=last_bot_message_id
                    )
                except:
                    pass  # Игнорируем ошибки удаления

            # Удаляем сообщение пользователя
            if settings.get('delete_user', False) and isinstance(event, Message):
                delay = settings.get('delay_user', 0)
                if delay > 0:
                    await asyncio.sleep(delay)

                try:
                    await event.delete()
                except:
                    pass

            # Выполняем основной handler
            result = await handler(event, data)

            # Сохраняем ID нового сообщения
            if result and hasattr(result, 'message_id'):
                await state.update_data(last_message_id=result.message_id)

            return result

        except Exception as e:
            logger.error(f"Ошибка в SmartAutoDeleteMiddleware: {e}")
            return await handler(event, data)

    def _get_event_type(self, event: TelegramObject) -> str:
        """Определяет тип события."""
        if isinstance(event, CallbackQuery):
            return 'callback'
        elif isinstance(event, Message):
            if event.text and event.text.startswith('/'):
                return 'command'
            elif event.photo:
                return 'photo'
            elif event.text:
                return 'text'
        return 'other'