import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from skyde_bot.app.config import BOT_TOKEN, DATABASE_URL
from skyde_bot.app.database.base import Base
from skyde_bot.app.middlewares.session_middleware import DBSessionMiddleware

# --- ИМПОРТ РОУТЕРОВ (ПРАВИЛЬНЫЙ ПОРЯДОК) ---
from skyde_bot.app.handlers.common_handlers import router as common_router
from skyde_bot.app.handlers.dev_menu import router as dev_router
from skyde_bot.app.handlers.support import router as support_router
from skyde_bot.app.handlers.profile import router as profile_router
from skyde_bot.app.handlers.slots import router as slots_router
from skyde_bot.app.handlers.games import router as games_router
from skyde_bot.app.handlers.nft import router as nft_router
from skyde_bot.app.handlers.chats import router as chats_router
from skyde_bot.app.handlers.start import router as start_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_db_tables(engine):
    """Создает таблицы базы данных, если они еще не существуют."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Таблицы созданы!")


async def main():
    """Основная функция для инициализации и запуска бота."""

    # --- 1. НАСТРОЙКА DB ---
    engine = create_async_engine(DATABASE_URL, echo=False)
    await create_db_tables(engine)

    session_pool = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # --- 2. НАСТРОЙКА БОТА И ДИСПЕТЧЕРА ---
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # --- 3. MIDDLEWARE ---
    @dp.update.outer_middleware()
    async def log_update_middleware(handler, event, data):
        """Логирует все входящие апдейты."""
        logger.info(f"📨 Received update: {event.update_id if hasattr(event, 'update_id') else 'unknown'}")
        return await handler(event, data)

    # Регистрация DB middleware
    dp.update.outer_middleware(DBSessionMiddleware(session_pool=session_pool))

    # --- 4. ВКЛЮЧЕНИЕ РОУТЕРОВ (КРИТИЧЕСКИ ВАЖНЫЙ ПОРЯДОК) ---
    dp.include_router(common_router)  # 1. ОБЩИЕ хендлеры (main_menu_return)
    dp.include_router(dev_router)  # 2. Команды разработчика (/dev)
    dp.include_router(support_router)  # 3. Поддержка (FSM состояния)
    dp.include_router(profile_router)  # 4. Профиль (FSM состояния)
    dp.include_router(slots_router)  # 5. Слоты (специфичные callback для игры)
    dp.include_router(games_router)  # 6. Общие игры (show_games)
    dp.include_router(nft_router)  # 7. NFT (FSM состояния для промокодов)
    dp.include_router(chats_router)  # 8. ЧАТЫ (FSM состояния для диалогов) ← НОВОЕ
    dp.include_router(start_router)  # 9. Регистрация и главное меню (должен быть последним)

    # --- 5. ЗАПУСК БОТА ---
    logger.info("🚀 Bot started!")
    logger.info(f"📋 Registered routers: {len(dp.sub_routers)} routers")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("🛑 Bot stopped!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user!")