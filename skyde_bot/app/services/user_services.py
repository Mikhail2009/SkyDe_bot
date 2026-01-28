from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from skyde_bot.app.database.models import User
from datetime import datetime
from sqlalchemy import update


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_next_uid(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        count = result.scalar()
        return (count or 0) + 1

    async def create_user(self, telegram_id: int, username: str, full_name: str,
                          phone: str, email: str, birth_date: str) -> User:
        uid = await self.get_next_uid()

        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            phone=phone,
            email=email,
            birth_date=datetime.strptime(birth_date, "%d.%m.%Y").date(),
            uid=uid,
            balance_g=0,
            premium_rate="Обычный"
        )

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def add_balance_g(self, user_id: int, amount: float):
        user = await self.get_user_by_telegram_id(user_id)
        if user:
            user.balance_g += amount
            await self.session.commit()

    async def set_avatar(self, telegram_id: int, file_id: str):
        user = await self.get_user_by_telegram_id(telegram_id)
        if user:
            user.avatar_file_id = file_id
            await self.session.commit()

    async def update_field(self, telegram_id: int, field_name: str, new_value: str):
        stmt = update(User).where(User.telegram_id == telegram_id).values({field_name: new_value})
        await self.session.execute(stmt)
        await self.session.commit()

    # Вставьте этот код вместо вашей функции update_balance

    async def update_balance(self, telegram_id: int, amount: float | int) -> float | int:
        """
        Обновляет баланс G-монет пользователя, фиксирует изменения и возвращает новый баланс.

        ВАЖНО: Возвращает float, чтобы сохранить дробную часть (копейки).
        Если пользователь не найден/обновлен, возвращает 0.
        """

        # 1. Выполняем атомарное обновление в базе данных и получаем НОВЫЙ БАЛАНС
        stmt = update(User).where(User.telegram_id == telegram_id).values(
            balance_g=User.balance_g + amount
        ).returning(User.balance_g)

        result = await self.session.execute(stmt)

        # 2. ФИКСИРУЕМ ТРАНЗАКЦИЮ! (Критически важно)
        try:
            await self.session.commit()
        except Exception as e:
            # В случае ошибки транзакции (например, таймаут) откатываем и логируем
            await self.session.rollback()
            print(f"ОШИБКА БД при фиксации баланса для {telegram_id}: {e}")
            return 0  # Возвращаем 0, так как изменение не прошло

        # Получаем новый баланс (возвращается как Decimal из SQLAlchemy)
        new_balance_decimal = result.scalar_one_or_none()

        # --- КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ ---
        if new_balance_decimal is None:

            print(f"ВНИМАНИЕ: Пользователь с telegram_id {telegram_id} не найден при обновлении баланса.")
            return 0

        # Возвращаем float, чтобы сохранить дробную часть (например, 49.50 вместо 49)
        return float(new_balance_decimal)

    # --- Добавьте здесь вспомогательный метод для чистого получения пользователя ---
    async def get_user_by_telegram_id_clean(self, telegram_id: int) -> User | None:
        """Получает пользователя, гарантируя, что это не кэшированный объект."""
        # Используем expire_all(), чтобы сбросить все кэшированные ORM-объекты
        self.session.expire_all()
        return await self.get_user_by_telegram_id(telegram_id)