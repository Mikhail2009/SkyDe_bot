from aiogram import F
from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from typing import Dict
from skyde_bot.app.keyboards.inline import support_actions_keyboard, main_menu_keyboard, cancel_keyboard
from skyde_bot.app.states.support_states import SupportState
from typing import Dict

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from skyde_bot.app.keyboards.inline import InlineKeyboardMarkup, InlineKeyboardButton

from skyde_bot.app.keyboards.inline import support_actions_keyboard, main_menu_keyboard, cancel_keyboard
from skyde_bot.app.states.profile_states import ProfileState as SupportState

router = Router()


ADMIN_ID = 729292013

# База знаний (ключевое слово: ответ)
FAQ_ANSWERS: Dict[str, str] = {
    "аватар": "Для смены аватара зайдите в 'Профиль' -> 'Настройки' -> 'Изменить иконку'.",
    "имя": "Вы можете изменить ваше имя и другие личные данные в разделе 'Профиль' -> 'Настройки'.",
    "баланс": "Проверьте ваш текущий баланс G-монет и цифровых рублей в разделе 'Профиль'. Обновление может занимать до 5 минут.",
    "промокод": "Чтобы ввести промокод, перейдите в меню 'NFT' -> 'Ввести промокод'.",
    "регистрация": "Если вы не можете зарегистрироваться, убедитесь, что ваш Telegram ID не заблокирован и попробуйте команду /start заново.",
}


def support_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура отмены ТОЛЬКО для поддержки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена поддержки", callback_data="cancel_support")]
    ])


# --- ХЕНДЛЕР: Отмена поддержки ---
@router.callback_query(F.data == "cancel_support")
async def cancel_support_handler(callback: CallbackQuery, state: FSMContext):
    """Отмена только режима поддержки."""
    await callback.answer("Поддержка отменена")

    # Проверяем, что мы именно в поддержке
    current_state = await state.get_state()
    if current_state != SupportState.waiting_for_question.state:
        await callback.answer("Не в режиме поддержки")
        return

    await state.clear()
    await callback.message.edit_text(
        "❌ Поддержка отменена.",
        reply_markup=main_menu_keyboard(),
        parse_mode='Markdown'
    )


@router.callback_query(F.data == "support")
async def start_support(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(SupportState.waiting_for_question)

    await callback.message.answer(
        "🤖 Ассистент поддержки SkyDe\n\n"
        "Пожалуйста, опишите ваш вопрос или проблему одним сообщением.",
        reply_markup=support_cancel_keyboard(),  # ← СПЕЦИАЛЬНАЯ клавиатура
        parse_mode='Markdown'
    )


# --- ХЕНДЛЕР 2: Обработка вопроса ---
@router.message(SupportState.waiting_for_question)
async def process_question(message: Message, state: FSMContext, bot: Bot):
    """Обработка введенного вопроса."""

    question = message.text.lower()
    found_answer = None

    # Поиск по ключевым словам
    for keyword, answer in FAQ_ANSWERS.items():
        if keyword in question:
            found_answer = answer
            break

    # Формирование ответа
    if found_answer:
        response_text = f"💡 Ответ ассистента:\n\n{found_answer}\n\nПомогло ли это решить вашу проблему?"
    else:
        response_text = "🤷‍♂️ Извините, я не нашел готового ответа на ваш вопрос. Вы хотите связаться с живым администратором?"

    # Отправка ответа
    await message.answer(
        response_text,
        reply_markup=support_actions_keyboard(),
        parse_mode='Markdown'
    )


# --- ХЕНДЛЕР 3: Связь с администратором (callback_data="contact_admin") ---
@router.callback_query(F.data == "contact_admin")
async def contact_admin(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Пересылает последний вопрос пользователя администратору."""

    await callback.answer("Передаю обращение администратору...")

    # Очищаем состояние пользователя
    await state.clear()

    try:
        # Пытаемся переслать сообщение, которое пользователь задал до текущего колбэка
        await bot.forward_message(
            chat_id=ADMIN_ID,
            from_chat_id=callback.from_user.id,
            message_id=callback.message.message_id - 1
        )

        # 2. Отправляем пользователю подтверждение
        await callback.message.edit_text("✅ Ваше обращение передано администратору! Ожидайте ответа.",
            reply_markup=main_menu_keyboard(),
            parse_mode='Markdown'
        )

    except Exception as e:
        await callback.message.edit_text(
            "❌ Ошибка при передаче обращения. Попробуйте позже.",
            reply_markup=main_menu_keyboard(),
            parse_mode='Markdown'
        )


# --- ХЕНДЛЕР: Отмена FSM-режима ---
@router.callback_query(F.data == "cancel_fsm_mode")
async def cancel_fsm_mode(callback: CallbackQuery, state: FSMContext):
    """Сбрасывает FSM-состояние и возвращает пользователя в главное меню."""

    await callback.answer("Отменено.")

    # 1. Проверяем текущее состояние
    current_state = await state.get_state()

    # 2. Сбрасываем состояние
    await state.clear()

    # 3. Отправка подтверждения и возврат в главное меню
    await callback.message.edit_text(
        "❌ Ввод отменен. Возврат в главное меню.",
        reply_markup=main_menu_keyboard(),
        parse_mode='Markdown'
    )