from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.crud import order as order_crud
from src.db.models import Order
from src.services.cart_service import CartViewDTO


def format_manager_notification(
    order_id: int,
    cart_view: CartViewDTO,
    customer_name: str,
    customer_phone: str,
    delivery_address: str,
    notes: str | None,
) -> str:
    """Сформировать текст уведомления менеджеру о новом заказе."""
    lines = [f"🔔 Новый заказ #{order_id}\n"]
    lines.append("Товары:")
    for idx, item in enumerate(cart_view.items, 1):
        lines.append(f"{idx}. {item.title}")
        lines.append(f"{item.price} ₽ × {item.quantity} = {item.line_total} ₽")
    lines.append(f"\nИтого: {cart_view.total} ₽\n")
    lines.append("Клиент:")
    lines.append(f"👤 {customer_name}")
    lines.append(f"📞 {customer_phone}")
    lines.append(f"📍 {delivery_address}")
    lines.append(f"✏️ {notes or '—'}")
    return "\n".join(lines)


async def get_user_orders(session: AsyncSession, user_id: int) -> list[Order]:
    """Получить последние 5 заказов пользователя (сортировка по убыванию id)."""
    orders = await order_crud.get_by_user(session, user_id)
    return orders[:5]


async def create_order_from_cart(
    session: AsyncSession,
    user_id: int,
    customer_name: str,
    customer_phone: str,
    delivery_address: str,
    notes: str | None,
    cart_view: CartViewDTO,
) -> Order:
    """Создать Order и OrderItem из текущей корзины со snapshot данных."""
    items = [
        {
            "product_id": item.product_id,
            "product_title_snapshot": item.title,
            "price_snapshot": item.price,
            "quantity": item.quantity,
        }
        for item in cart_view.items
    ]
    return await order_crud.create_order(
        session=session,
        user_id=user_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        delivery_address=delivery_address,
        total_amount=cart_view.total,
        notes=notes,
        items=items,
    )
