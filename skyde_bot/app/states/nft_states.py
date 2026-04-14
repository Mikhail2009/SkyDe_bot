from aiogram.fsm.state import StatesGroup, State


class NFTState(StatesGroup):
    """Состояния для работы с NFT."""
    waiting_for_promo = State()
    waiting_for_wallet = State()

    # Загрузка NFT
    waiting_for_nft_photo = State()
    waiting_for_nft_title = State()
    waiting_for_nft_description = State()
    waiting_for_nft_price = State()

    # Просмотр NFT
    browsing_my_nfts = State()
    browsing_marketplace = State()

    # Удаление NFT
    waiting_for_delete_code = State()  # ← НОВОЕ