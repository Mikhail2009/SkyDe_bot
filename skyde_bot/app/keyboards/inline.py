from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, List


# --- I. ОБЩИЕ КЛАВИАТУРЫ ---

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню бота."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🕹 Игры", callback_data="show_games")],
        [InlineKeyboardButton(text="💬 Чаты", callback_data="chat_menu")],
        [InlineKeyboardButton(text="✨ NFT/Промокоды", callback_data="nft_menu")],
        [InlineKeyboardButton(text="💬 Поддержка", callback_data="support")],
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой "Назад/Отмена" для выхода из FSM-состояния."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Отмена / Назад", callback_data="cancel_fsm_mode")]
    ])


def back_to_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")]
    ])


# --- II. КЛАВИАТУРЫ ПРОФИЛЯ/НАСТРОЕК ---

def profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура под профилем."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")]
    ])


def settings_keyboard() -> InlineKeyboardMarkup:
    """Меню настроек профиля."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 Изменить иконку", callback_data="change_icon")],
        [InlineKeyboardButton(text="✍️ Изменить имя", callback_data="set_full_name")],
        [InlineKeyboardButton(text="📞 Изменить телефон", callback_data="set_phone")],
        [InlineKeyboardButton(text="✉️ Изменить Email", callback_data="set_email")],
        [InlineKeyboardButton(text="💼 Изменить кошелёк", callback_data="set_wallet")],  # ← НОВАЯ КНОПКА
        [InlineKeyboardButton(text="⬅️ Назад в профиль", callback_data="profile")]
    ])


# --- III. КЛАВИАТУРЫ ДЛЯ ИГР ---

def games_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню выбора игр."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎰 Слоты", callback_data="game_slots")],
        [InlineKeyboardButton(text="⚽️ Футбол", callback_data="start_football")],
        [InlineKeyboardButton(text="🎲 Кости", callback_data="start_dice")],
        [InlineKeyboardButton(text="⬅️ Вернуться в главное меню", callback_data="main_menu_return")]
    ])


# --- IV. КЛАВИАТУРЫ ДЛЯ СЛОТОВ ---
# Клавиатуры слотов теперь находятся в slots.py


# --- V. КЛАВИАТУРЫ NFT/ПРОМОКОДОВ ---

def nft_menu_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для NFT меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Мои NFT", callback_data="show_my_nfts")],
        [InlineKeyboardButton(text="🛒 Купить NFT", callback_data="buy_nft")],
        [InlineKeyboardButton(text="💰 Продать NFT", callback_data="sell_nft")],
        [InlineKeyboardButton(text="🎁 Ввести промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data="main_menu_return")]
    ])


def back_to_nft_menu_keyboard() -> InlineKeyboardMarkup:
    """Вернуться в основное NFT меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в NFT меню", callback_data="nft_menu")]
    ])


# --- VI. КЛАВИАТУРЫ ДЛЯ ПОДДЕРЖКИ ---

def support_actions_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора действий после ответа ассистента."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👍 Помогло", callback_data="main_menu_return")],
        [InlineKeyboardButton(text="👨‍💻 Связаться с админом", callback_data="contact_admin")]
    ])