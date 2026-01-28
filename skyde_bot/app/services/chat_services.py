from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update
from skyde_bot.app.database.models import ChatSession, ChatMessage, ChatRequest, User
from datetime import datetime


class ChatService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_user_by_username(self, username: str) -> User | None:
        """Найти пользователя по @username."""
        # Убираем @ если есть
        username = username.lstrip('@')

        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def create_chat_request(self, from_user_id: int, to_user_id: int) -> ChatRequest:
        """Создать запрос на переписку."""

        # Проверяем, нет ли уже активного запроса
        existing = await self.session.execute(
            select(ChatRequest).where(
                and_(
                    ChatRequest.from_user_id == from_user_id,
                    ChatRequest.to_user_id == to_user_id,
                    ChatRequest.status == "pending"
                )
            )
        )

        if existing.scalar_one_or_none():
            return None  # Запрос уже существует

        request = ChatRequest(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            status="pending"
        )

        self.session.add(request)
        await self.session.commit()
        await self.session.refresh(request)

        return request

    async def accept_chat_request(self, request_id: int) -> ChatSession:
        """Принять запрос на переписку и создать сессию чата."""

        # Получаем запрос
        result = await self.session.execute(
            select(ChatRequest).where(ChatRequest.id == request_id)
        )
        request = result.scalar_one_or_none()

        if not request or request.status != "pending":
            return None

        # Обновляем статус запроса
        request.status = "accepted"

        # Создаем сессию чата
        session = ChatSession(
            user1_id=request.from_user_id,
            user2_id=request.to_user_id,
            is_active=True
        )

        self.session.add(session)
        await self.session.commit()
        await self.session.refresh(session)

        return session

    async def reject_chat_request(self, request_id: int):
        """Отклонить запрос на переписку."""
        await self.session.execute(
            update(ChatRequest)
            .where(ChatRequest.id == request_id)
            .values(status="rejected")
        )
        await self.session.commit()

    async def ignore_chat_request(self, request_id: int):
        """Игнорировать запрос на переписку."""
        await self.session.execute(
            update(ChatRequest)
            .where(ChatRequest.id == request_id)
            .values(status="ignored")
        )
        await self.session.commit()

    async def get_active_session(self, user_id: int) -> ChatSession | None:
        """Получить активную сессию чата для пользователя."""
        result = await self.session.execute(
            select(ChatSession).where(
                and_(
                    or_(
                        ChatSession.user1_id == user_id,
                        ChatSession.user2_id == user_id
                    ),
                    ChatSession.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def send_message(self, session_id: int, sender_id: int, text: str) -> ChatMessage:
        """Отправить сообщение в чат."""

        message = ChatMessage(
            session_id=session_id, sender_id=sender_id,
            message_text=text
        )

        # Обновляем время последнего сообщения в сессии
        await self.session.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(last_message_at=datetime.now())
        )

        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)

        return message

    async def end_chat_session(self, session_id: int):
        """Завершить сессию чата."""
        await self.session.execute(
            update(ChatSession)
            .where(ChatSession.id == session_id)
            .values(is_active=False, ended_at=datetime.now())
        )
        await self.session.commit()

    async def get_recent_contacts(self, user_id: int, limit: int = 5):
        """Получить последних собеседников пользователя."""
        result = await self.session.execute(
            select(ChatSession)
            .where(
                or_(
                    ChatSession.user1_id == user_id,
                    ChatSession.user2_id == user_id
                )
            )
            .order_by(ChatSession.last_message_at.desc())
            .limit(limit)
        )

        sessions = result.scalars().all()

        # Получаем ID собеседников
        contacts = []
        for session in sessions:
            other_user_id = session.user2_id if session.user1_id == user_id else session.user1_id

            # Получаем данные собеседника
            user_result = await self.session.execute(
                select(User).where(User.telegram_id == other_user_id)
            )
            other_user = user_result.scalar_one_or_none()

            if other_user:
                contacts.append({
                    'user': other_user,
                    'session_id': session.id,
                    'is_active': session.is_active
                })

        return contacts

    async def get_other_user_in_session(self, session_id: int, current_user_id: int) -> User | None:
        """Получить данные собеседника в активной сессии."""
        result = await self.session.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        session = result.scalar_one_or_none()

        if not session:
            return None

        other_user_id = session.user2_id if session.user1_id == current_user_id else session.user1_id

        user_result = await self.session.execute(
            select(User).where(User.telegram_id == other_user_id)
        )

        return user_result.scalar_one_or_none()