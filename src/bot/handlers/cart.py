from __future__ import annotations

from src.bot.keyboards import cart_view_keyboard, clear_confirm_keyboard, empty_cart_keyboard
from src.bot.max_client import MAXClient
from src.db.engine import async_session_maker
from src.services import cart_service, user_service


async def _render_cart(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None,
) -> None:
    """Получить корзину пользователя и отрендерить через edit_message или send_message."""
    async with async_session_maker() as session:
        user = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        cart_view = await cart_service.get_cart_view(session, user.id)

    if not cart_view.items:
        text = "🛒 Корзина пуста.\n\nВы можете перейти в каталог и выбрать изделие с гравировкой."
        keyboard = empty_cart_keyboard()
    else:
        lines = ["🛒 Ваша корзина\n"]
        for idx, item in enumerate(cart_view.items, 1):
            lines.append(f"{idx}. {item.title}")
            lines.append(f"{item.price} ₽ × {item.quantity} = {item.line_total} ₽")
            lines.append("")
        lines.append(f"Итого: {cart_view.total} ₽")
        text = "\n".join(lines)
        keyboard = cart_view_keyboard(cart_view.items)

    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
    else:
        await client.send_message(chat_id, text, reply_markup=keyboard)


async def show_cart(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Показать корзину пользователя."""
    await _render_cart(client, chat_id, user_id, message_id)


async def change_quantity(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str,
    product_id: int,
    delta: int,
) -> None:
    """Изменить количество товара в корзине."""
    async with async_session_maker() as session:
        user = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        await cart_service.change_quantity(session, user.id, product_id, delta)
    await _render_cart(client, chat_id, user_id, message_id)


async def remove_item(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str,
    product_id: int,
) -> None:
    """Удалить позицию из корзины."""
    async with async_session_maker() as session:
        user = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        await cart_service.remove_item(session, user.id, product_id)
    await _render_cart(client, chat_id, user_id, message_id)


async def confirm_clear_cart(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str,
) -> None:
    """Показать подтверждение очистки корзины."""
    text = "🗑 Очистить корзину?\n\nВсе товары будут удалены из корзины."
    keyboard = clear_confirm_keyboard()
    await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)


async def clear_cart(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str,
) -> None:
    """Очистить корзину и вернуть пустой экран."""
    async with async_session_maker() as session:
        user = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        await cart_service.clear_cart(session, user.id)
    await _render_cart(client, chat_id, user_id, message_id)


async def cancel_clear_cart(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str,
) -> None:
    """Отменить очистку и вернуть экран корзины."""
    await _render_cart(client, chat_id, user_id, message_id)
