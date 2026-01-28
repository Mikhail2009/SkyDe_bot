from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Numeric, Date, ForeignKey, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from skyde_bot.app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    uid = Column(Integer, unique=True, nullable=False)

    username = Column(String(128))
    full_name = Column(String(128))
    phone = Column(String(20))
    email = Column(String(255))
    birth_date = Column(Date)

    avatar_file_id = Column(String(255), nullable=True)

    # Крипто-кошелек для NFT (только TON)
    crypto_wallet = Column(String(255), nullable=True)

    premium_rate = Column(String(50), default="Обычный")
    balance_g = Column(Numeric(10, 2), default=49.5)
    digital_ruble_balance = Column(Numeric(10, 2), default=0.00)

    registered_at = Column(DateTime, default=func.now())


class ChatSession(Base):
    """Активные сессии чатов между пользователями."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Участники чата
    user1_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    user2_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)

    # Статус
    is_active = Column(Boolean, default=True)  # Активен ли чат

    # Временные метки
    created_at = Column(DateTime, default=func.now())
    ended_at = Column(DateTime, nullable=True)

    # Последнее сообщение (для сортировки в списке)
    last_message_at = Column(DateTime, default=func.now())


class ChatMessage(Base):
    """История сообщений в чатах."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)

    session_id = Column(Integer, ForeignKey('chat_sessions.id'), nullable=False)
    sender_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)

    message_text = Column(Text, nullable=False)

    created_at = Column(DateTime, default=func.now())


class ChatRequest(Base):
    """Запросы на начало переписки."""
    __tablename__ = "chat_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Кто отправил запрос
    from_user_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    # Кому отправлен запрос
    to_user_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)

    # Статус запроса
    status = Column(String(20), default="pending")  # pending, accepted, rejected, ignored

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())