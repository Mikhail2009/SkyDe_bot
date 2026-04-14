from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Numeric, Date, ForeignKey, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from skyde_bot.app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    uid = Column(Integer, unique=True, nullable=False)

    # --- НОВЫЕ ПОЛЯ ---
    nickname = Column(String(32), unique=True, nullable=False, index=True) # Уникальный никнейм
    password_hash = Column(String(255), nullable=False) # Хеш пароля

    # --- СТАРЫЕ ПОЛЯ (оставляем для совместимости) ---
    username = Column(String(128)) # Telegram @username (необязательно)
    full_name = Column(String(128)) # Теперь = nickname для отображения
    phone = Column(String(20))
    email = Column(String(255))
    birth_date = Column(Date)

    avatar_file_id = Column(String(255), nullable=True)

    # Крипто-кошелек для NFT (только TON)
    crypto_wallet = Column(String(255), nullable=True)

    premium_rate = Column(String(50), default="Обычный")
    balance_g = Column(Numeric(10, 2), default=0.00)
    digital_ruble_balance = Column(Numeric(10, 2), default=0.00)

    registered_at = Column(DateTime, default=func.now())


class NFT(Base):
    """NFT токены пользователей."""
    __tablename__ = "nfts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    photo_file_id = Column(String(255), nullable=False)
    photo_file_id_watermarked = Column(String(255), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(20, 9), nullable=False)
    is_on_sale = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class NFTFavorite(Base):
    """Избранные NFT пользователей."""
    __tablename__ = "nft_favorites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    nft_id = Column(Integer, ForeignKey('nfts.id'), nullable=False)
    added_at = Column(DateTime, default=func.now())


class NFTPurchase(Base):
    """Активные сделки покупки NFT."""
    __tablename__ = "nft_purchases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nft_id = Column(Integer, ForeignKey('nfts.id'), nullable=False)
    buyer_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    status = Column(String(20), default="pending")
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)


class ChatSession(Base):
    """Активные сессии чатов между пользователями."""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user1_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    user2_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    ended_at = Column(DateTime, nullable=True)
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
    from_user_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    to_user_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class NFTDispute(Base):
    """Споры по сделкам NFT."""
    __tablename__ = "nft_disputes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    purchase_id = Column(Integer, ForeignKey('nft_purchases.id'), nullable=False)
    nft_id = Column(Integer, ForeignKey('nfts.id'), nullable=False)
    buyer_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    seller_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    status = Column(String(20), default="open")
    chat_session_id = Column(Integer, ForeignKey('chat_sessions.id'), nullable=True)
    created_at = Column(DateTime, default=func.now())
    resolved_at = Column(DateTime, nullable=True)


class NFTUploadRequest(Base):
    """Запросы на загрузку NFT."""
    __tablename__ = "nft_upload_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.telegram_id'), nullable=False)
    photo_file_id = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    commission = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), default="pending")
    nft_id = Column(Integer, ForeignKey('nfts.id'), nullable=True)
    created_at = Column(DateTime, default=func.now())
    processed_at = Column(DateTime, nullable=True)
