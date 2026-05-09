from __future__ import annotations

from src.bot.keyboards import cart_view_keyboard, empty_cart_keyboard
from src.bot.max_client import MAXClient
from src.db.engine import async_session_maker
from src.services import cart_service, user_service


async def show_cart(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Показать корзину пользователя. edit_message если message_id, иначе send."""
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
        keyboard = cart_view_keyboard()

    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
    else:
        await client.send_message(chat_id, text, reply_markup=keyboard)
