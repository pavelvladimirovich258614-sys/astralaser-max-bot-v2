from __future__ import annotations

import logging
import re

from src.bot.handlers import cart as cart_handler
from src.bot.keyboards import (
    empty_cart_keyboard,
    order_cancel_keyboard,
    order_ready_keyboard,
)
from src.bot.max_client import MAXClient
from src.db.engine import async_session_maker
from src.services import cart_service, fsm_service, user_service

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"^\+?\d[\d\s\-\(\)]{9,17}$")


async def _best_effort_delete(
    client: MAXClient,
    chat_id: int | str,
    message_id: str | None,
) -> None:
    """Попытаться удалить пользовательское сообщение; не падать при ошибке."""
    if not message_id:
        return
    try:
        ok = await client.delete_message(chat_id, message_id)
        if not ok:
            logger.info("delete_message returned False for message_id=%s", message_id)
    except Exception:
        logger.info("delete_message failed for message_id=%s", message_id, exc_info=True)


async def start_checkout(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Старт оформления заказа. Пустая корзина → пустая корзина. Непустая → FSM ожидание ФИО."""
    async with async_session_maker() as session:
        user = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        cart_view = await cart_service.get_cart_view(session, user.id)

        if not cart_view.items:
            text = "🛒 Корзина пуста.\n\nВы можете перейти в каталог и выбрать изделие с гравировкой."
            keyboard = empty_cart_keyboard()
        else:
            await fsm_service.set_waiting_name(session, user.id)
            await session.commit()
            text = (
                "📝 Оформление заказа\n\n"
                "Шаг 1/4. Как вас зовут?\n\n"
                "Напишите ФИО одним сообщением."
            )
            keyboard = order_cancel_keyboard()

    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
    else:
        await client.send_message(chat_id, text, reply_markup=keyboard)


async def cancel_checkout(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Отменить оформление заказа и вернуть пользователя в корзину."""
    async with async_session_maker() as session:
        user = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        await fsm_service.clear_state(session, user.id)
        await session.commit()

    await cart_handler.show_cart(client, chat_id, user_id, message_id)


async def handle_fsm_message(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None,
    text: str,
) -> bool:
    """Обработать текстовое сообщение пользователя в FSM-состоянии оформления заказа.

    Возвращает True если сообщение было обработано (FSM-active state).
    """
    async with async_session_maker() as session:
        user = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        state, data = await fsm_service.get_state(session, user.id)

        if not fsm_service.is_order_state(state):
            return False

        if state == fsm_service.ORDER_WAITING_NAME:
            if _validate_name(text):
                await fsm_service.update_data(session, user.id, {"customer_name": text.strip()}, fsm_service.ORDER_WAITING_PHONE)
                await session.commit()
                await client.send_message(
                    chat_id,
                    "Шаг 2/4. Укажите телефон\n\nФормат: +7 XXX XXX XX XX",
                    reply_markup=order_cancel_keyboard(),
                )
                await _best_effort_delete(client, chat_id, message_id)
            else:
                await client.send_message(
                    chat_id,
                    "Пожалуйста, напишите ФИО полностью.",
                    reply_markup=order_cancel_keyboard(),
                )
            return True

        if state == fsm_service.ORDER_WAITING_PHONE:
            if _validate_phone(text):
                await fsm_service.update_data(session, user.id, {"phone": text.strip()}, fsm_service.ORDER_WAITING_ADDRESS)
                await session.commit()
                await client.send_message(
                    chat_id,
                    "Шаг 3/4. Укажите адрес доставки или пункт СДЭК.",
                    reply_markup=order_cancel_keyboard(),
                )
                await _best_effort_delete(client, chat_id, message_id)
            else:
                await client.send_message(
                    chat_id,
                    "Не похоже на телефон. Формат: +7 XXX XXX XX XX. Попробуйте ещё раз.",
                    reply_markup=order_cancel_keyboard(),
                )
            return True

        if state == fsm_service.ORDER_WAITING_ADDRESS:
            if _validate_address(text):
                await fsm_service.update_data(session, user.id, {"address": text.strip()}, fsm_service.ORDER_WAITING_NOTES)
                await session.commit()
                await client.send_message(
                    chat_id,
                    "Шаг 4/4. Напишите текст гравировки или комментарий к заказу.\n\nЕсли комментария нет — напишите прочерк.",
                    reply_markup=order_cancel_keyboard(),
                )
                await _best_effort_delete(client, chat_id, message_id)
            else:
                await client.send_message(
                    chat_id,
                    "Пожалуйста, укажите адрес доставки полностью.",
                    reply_markup=order_cancel_keyboard(),
                )
            return True

        if state == fsm_service.ORDER_WAITING_NOTES:
            notes = text.strip()
            if len(notes) > 500:
                await client.send_message(
                    chat_id,
                    "Слишком длинный комментарий. Максимум 500 символов. Попробуйте короче.",
                    reply_markup=order_cancel_keyboard(),
                )
                return True
            if not notes:
                notes = "Обсудим с менеджером"
            await fsm_service.update_data(session, user.id, {"notes": notes}, fsm_service.ORDER_READY_CONFIRM)
            await session.commit()
            await client.send_message(
                chat_id,
                "✅ Данные для заказа собраны.\n\nСледующий шаг — проверить заказ и подтвердить оформление.",
                reply_markup=order_ready_keyboard(),
            )
            await _best_effort_delete(client, chat_id, message_id)
            return True

        return False


def _validate_name(text: str) -> bool:
    stripped = text.strip()
    if not stripped or len(stripped) < 2 or len(stripped) > 100:
        return False
    if stripped.startswith("/"):
        return False
    words = stripped.split()
    return len(words) >= 2 or len(stripped) > 5


def _validate_phone(text: str) -> bool:
    stripped = text.strip()
    return bool(_PHONE_RE.match(stripped))


def _validate_address(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and 5 <= len(stripped) <= 300
