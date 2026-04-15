from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update, delete  # ← Убедитесь что delete есть
from skyde_bot.app.database.models import NFT, NFTFavorite, NFTPurchase, User, NFTDispute
from datetime import datetime, timedelta
from typing import List, Optional


class NFTService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_nft(
            self,
            owner_id: int,
            photo_file_id: str,
            title: str,
            description: str,
            price: float
    ) -> NFT:
        """Создать новый NFT (сразу на продаже)."""
        nft = NFT(
            owner_id=owner_id,
            photo_file_id=photo_file_id,
            title=title,
            description=description,
            price=price,
            is_on_sale=True  # ← СРАЗУ НА ПРОДАЖЕ
        )

        self.session.add(nft)
        await self.session.commit()
        await self.session.refresh(nft)

        return nft

    async def get_user_nfts(self, user_id: int) -> List[NFT]:
        """Получить все NFT пользователя."""
        result = await self.session.execute(
            select(NFT)
            .where(NFT.owner_id == user_id)
            .order_by(NFT.created_at.desc())
        )
        return result.scalars().all()

    async def get_nft_by_id(self, nft_id: int) -> Optional[NFT]:
        """Получить NFT по ID."""
        result = await self.session.execute(
            select(NFT).where(NFT.id == nft_id)
        )
        return result.scalar_one_or_none()

    async def toggle_sale_status(self, nft_id: int, watermarked_file_id: str = None) -> NFT:
        """Переключить статус продажи NFT."""
        result = await self.session.execute(
            select(NFT).where(NFT.id == nft_id)
        )
        nft = result.scalar_one_or_none()

        if nft:
            nft.is_on_sale = not nft.is_on_sale

            # Если выставляем на продажу, сохраняем ID фото с водяным знаком
            if nft.is_on_sale and watermarked_file_id:
                nft.photo_file_id_watermarked = watermarked_file_id

            await self.session.commit()
            await self.session.refresh(nft)

        return nft

    async def get_marketplace_nfts(self, exclude_user_id: int = None) -> List[NFT]:
        """Получить все NFT на продаже (кроме своих)."""
        query = select(NFT).where(NFT.is_on_sale == True)

        if exclude_user_id:
            query = query.where(NFT.owner_id != exclude_user_id)

        query = query.order_by(NFT.created_at.desc())

        result = await self.session.execute(query)
        return result.scalars().all()

    async def add_to_favorites(self, user_id: int, nft_id: int) -> bool:
        """Добавить NFT в избранное."""
        # Проверяем, нет ли уже в избранном
        existing = await self.session.execute(
            select(NFTFavorite).where(
                and_(
                    NFTFavorite.user_id == user_id,
                    NFTFavorite.nft_id == nft_id
                )
            )
        )

        if existing.scalar_one_or_none():
            return False  # Уже в избранном

        favorite = NFTFavorite(user_id=user_id, nft_id=nft_id)
        self.session.add(favorite)
        await self.session.commit()

        return True

    async def remove_from_favorites(self, user_id: int, nft_id: int):
        """Удалить NFT из избранного."""
        await self.session.execute(
            delete(NFTFavorite).where(
                and_(
                    NFTFavorite.user_id == user_id,
                    NFTFavorite.nft_id == nft_id
                )
            )
        )
        await self.session.commit()

    async def get_user_favorites(self, user_id: int) -> List[NFT]:
        """Получить избранные NFT пользователя."""
        result = await self.session.execute(
            select(NFT)
            .join(NFTFavorite, NFTFavorite.nft_id == NFT.id)
            .where(NFTFavorite.user_id == user_id)
            .order_by(NFTFavorite.added_at.desc())
        )
        return result.scalars().all()

    async def is_in_favorites(self, user_id: int, nft_id: int) -> bool:
        """Проверить, находится ли NFT в избранном."""
        result = await self.session.execute(
            select(NFTFavorite).where(
                and_(
                    NFTFavorite.user_id == user_id,
                    NFTFavorite.nft_id == nft_id
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def create_purchase(self, nft_id: int, buyer_id: int) -> Optional[NFTPurchase]:
        """Создать сделку покупки (таймер 10 минут)."""
        # Проверяем, нет ли активной сделки на этот NFT
        existing = await self.session.execute(
            select(NFTPurchase).where(
                and_(
                    NFTPurchase.nft_id == nft_id,
                    NFTPurchase.status == "pending",
                    NFTPurchase.expires_at > datetime.now()
                )
            )
        )

        if existing.scalar_one_or_none():
            return None  # Уже есть активная сделка

        purchase = NFTPurchase(
            nft_id=nft_id,
            buyer_id=buyer_id,
            status="pending",
            expires_at=datetime.now() + timedelta(minutes=10)
        )

        self.session.add(purchase)
        await self.session.commit()
        await self.session.refresh(purchase)

        return purchase

    async def get_active_purchase(self, nft_id: int) -> Optional[NFTPurchase]:
        """Получить активную сделку по NFT."""
        result = await self.session.execute(
            select(NFTPurchase).where(
                and_(
                    NFTPurchase.nft_id == nft_id,
                    NFTPurchase.status == "pending",
                    NFTPurchase.expires_at > datetime.now()
                )
            )
        )
        return result.scalar_one_or_none()

    async def complete_purchase(self, purchase_id: int, new_owner_id: int):
        """Завершить сделку - перевести NFT новому владельцу."""
        # Получаем сделку
        result = await self.session.execute(
            select(NFTPurchase).where(NFTPurchase.id == purchase_id)
        )
        purchase = result.scalar_one_or_none()

        if not purchase:
            return False

        # Получаем NFT
        nft = await self.get_nft_by_id(purchase.nft_id)

        if not nft:
            return False

        # Переводим NFT новому владельцу
        nft.owner_id = new_owner_id
        nft.is_on_sale = False
        nft.photo_file_id_watermarked = None

        # Завершаем сделку
        purchase.status = "completed"
        purchase.completed_at = datetime.now()

        await self.session.commit()

        return True

    async def cancel_purchase(self, purchase_id: int):
        """Отменить сделку."""
        await self.session.execute(
            update(NFTPurchase)
            .where(NFTPurchase.id == purchase_id)
            .values(status="cancelled")
        )
        await self.session.commit()

    async def expire_old_purchases(self):
        """Автоматически отменить просроченные сделки."""
        await self.session.execute(
            update(NFTPurchase)
            .where(
                and_(
                    NFTPurchase.status == "pending",
                    NFTPurchase.expires_at <= datetime.now()
                )
            )
            .values(status="expired")
        )
        await self.session.commit()

    async def delete_nft(self, nft_id: int):
        from sqlalchemy import delete
        from skyde_bot.app.database.models import NFT

        await self.session.execute(delete(NFT).where(NFT.id == nft_id))
        await self.session.commit()  # БЕЗ ЭТОГО ИЗМЕНЕНИЯ НЕ СОХРАНЯТСЯ

    async def create_dispute(self, purchase_id: int, nft_id: int, buyer_id: int, seller_id: int):
        """Создать спор по сделке."""
        # Проверяем, нет ли уже спора
        existing = await self.session.execute(
            select(NFTDispute).where(
                and_(
                    NFTDispute.purchase_id == purchase_id,
                    NFTDispute.status == "open"
                )
            )
        )

        if existing.scalar_one_or_none():
            return None  # Спор уже существует

        dispute = NFTDispute(
            purchase_id=purchase_id,
            nft_id=nft_id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            status="open"
        )

        self.session.add(dispute)
        await self.session.commit()
        await self.session.refresh(dispute)

        return dispute

    async def get_dispute_by_purchase(self, purchase_id: int):
        """Получить спор по ID сделки."""
        result = await self.session.execute(
            select(NFTDispute).where(
                and_(
                    NFTDispute.purchase_id == purchase_id,
                    NFTDispute.status == "open"
                )
            )
        )
        return result.scalar_one_or_none()

    async def link_dispute_to_chat(self, dispute_id: int, chat_session_id: int):
        """Привязать спор к чат-сессии."""
        await self.session.execute(
            update(NFTDispute)
            .where(NFTDispute.id == dispute_id)
            .values(chat_session_id=chat_session_id)
        )
        await self.session.commit()

    async def resolve_dispute(self, dispute_id: int):
        """Закрыть спор."""
        await self.session.execute(
            update(NFTDispute)
            .where(NFTDispute.id == dispute_id)
            .values(status="resolved", resolved_at=datetime.now())
        )
        await self.session.commit()

    async def create_upload_request(
            self,
            user_id: int,
            photo_file_id: str,
            title: str,
            description: str,
            price: float,
            commission: float
    ):
        """Создать запрос на загрузку NFT."""
        from skyde_bot.app.database.models import NFTUploadRequest

        upload_request = NFTUploadRequest(
            user_id=user_id,
            photo_file_id=photo_file_id,
            title=title,
            description=description,
            price=price,
            commission=commission,
            status="pending"
        )

        self.session.add(upload_request)
        await self.session.commit()
        await self.session.refresh(upload_request)

        return upload_request

    async def get_upload_request(self, request_id: int):
        """Получить запрос на загрузку по ID."""
        from skyde_bot.app.database.models import NFTUploadRequest

        result = await self.session.execute(
            select(NFTUploadRequest).where(NFTUploadRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def approve_upload_request(self, request_id: int) -> NFT:
        """Подтвердить запрос и создать NFT (сразу на продаже)."""
        from skyde_bot.app.database.models import NFTUploadRequest

        # Получаем запрос
        result = await self.session.execute(
            select(NFTUploadRequest).where(NFTUploadRequest.id == request_id)
        )
        upload_request = result.scalar_one_or_none()

        if not upload_request or upload_request.status != "pending":
            return None

        # Создаем NFT СРАЗУ НА ПРОДАЖЕ
        nft = NFT(
            owner_id=upload_request.user_id,
            photo_file_id=upload_request.photo_file_id,
            title=upload_request.title,
            description=upload_request.description,
            price=upload_request.price,
            is_on_sale=True  # ← СРАЗУ НА ПРОДАЖЕ
        )

        self.session.add(nft)
        await self.session.flush()  # Получаем ID NFT

        # Обновляем запрос
        upload_request.status = "approved"
        upload_request.nft_id = nft.id
        upload_request.processed_at = datetime.now()

        await self.session.commit()
        await self.session.refresh(nft)

        return nft

    async def reject_upload_request(self, request_id: int):
        """Отклонить запрос на загрузку."""
        from skyde_bot.app.database.models import NFTUploadRequest

        await self.session.execute(
            update(NFTUploadRequest)
            .where(NFTUploadRequest.id == request_id)
            .values(status="rejected", processed_at=datetime.now())
        )
        await self.session.commit()
