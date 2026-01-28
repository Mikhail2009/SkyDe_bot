from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

class DBSessionMiddleware(BaseMiddleware):
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Добавлены self и session_pool
    def __init__(self, session_pool: async_sessionmaker):
        # 1. Сохраняем session_pool как атрибут экземпляра
        self.session_pool = session_pool
        super().__init__() # Необязательно, но полезно для наследования

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # 2. Логика, которую мы писали:
        async with self.session_pool() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise