from __future__ import annotations

from src.bot.handlers import cart as cart_handler
from src.bot.keyboards import empty_cart_keyboard, order_cancel_keyboard
from src.bot.max_client import MAXClient
from src.db.engine import async_session_maker
from src.services import cart_service, fsm_service, user_service


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
