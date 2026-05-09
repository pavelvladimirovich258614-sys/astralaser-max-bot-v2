from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.crud import order as order_crud
from src.db.models import Order
from src.services.cart_service import CartViewDTO


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
