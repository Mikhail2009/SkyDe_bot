import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from skyde_bot.app.database.models import User
from datetime import datetime


def hash_password(password: str) -> str:
    """Хеширует пароль через SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет пароль."""
    return hash_password(password) == password_hash


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_nickname(self, nickname: str) -> User | None:
        """Найти пользователя по никнейму (регистронезависимо)."""
        result = await self.session.execute(
            select(User).where(User.nickname == nickname.lower())
        )
        return result.scalar_one_or_none()

    async def is_nickname_taken(self, nickname: str) -> bool:
        """Проверить, занят ли никнейм."""
        user = await self.get_user_by_nickname(nickname)
        return user is not None

    async def get_next_uid(self) -> int:
        result = await self.session.execute(select(func.count(User.id)))
        count = result.scalar()
        return (count or 0) + 1

    async def create_user(
        self,
        telegram_id: int,
        username: str,
        nickname: str,
        password: str,
        phone: str,
        email: str,
        birth_date: str
    ) -> User:
        uid = await self.get_next_uid()

        user = User(
            telegram_id=telegram_id,
            username=username,
            nickname=nickname.lower(), # Храним в нижнем регистре
            full_name=nickname, # full_name = nickname для совместимости
            password_hash=hash_password(password),
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

    async def verify_login(self, nickname: str, password: str) -> User | None:
        """Проверяет никнейм и пароль. Возвращает пользователя или None."""
        user = await self.get_user_by_nickname(nickname)
        if user and verify_password(password, user.password_hash):
            return user
        return None

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

    async def update_balance(self, telegram_id: int, amount: float | int) -> float | int:
        stmt = update(User).where(User.telegram_id == telegram_id).values(
            balance_g=User.balance_g + amount
        ).returning(User.balance_g)

        result = await self.session.execute(stmt)

        try:
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            print(f"ОШИБКА БД при фиксации баланса для {telegram_id}: {e}")
            return 0

        new_balance_decimal = result.scalar_one_or_none()

        if new_balance_decimal is None:
            print(f"ВНИМАНИЕ: Пользователь с telegram_id {telegram_id} не найден.")
            return 0

        return float(new_balance_decimal)

    async def get_user_by_telegram_id_clean(self, telegram_id: int) -> User | None:
        self.session.expire_all()
        return await self.get_user_by_telegram_id(telegram_id)
