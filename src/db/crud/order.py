from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Order, OrderItem


async def create_order(
    session: AsyncSession,
    user_id: int,
    customer_name: str,
    customer_phone: str,
    delivery_address: str,
    total_amount: int,
    notes: str | None,
    items: list[dict[str, Any]],
) -> Order:
    order = Order(
        user_id=user_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        delivery_address=delivery_address,
        total_amount=total_amount,
        notes=notes,
    )
    session.add(order)
    await session.flush()

    for item_data in items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item_data["product_id"],
            product_title_snapshot=item_data["product_title_snapshot"],
            price_snapshot=item_data["price_snapshot"],
            quantity=item_data["quantity"],
        )
        session.add(order_item)

    await session.commit()
    await session.refresh(order)
    return order


async def get_by_id(session: AsyncSession, order_id: int) -> Order | None:
    result = await session.execute(
        select(Order).where(Order.id == order_id).options(selectinload(Order.items))
    )
    return result.scalar_one_or_none()


async def get_by_user(session: AsyncSession, user_id: int) -> list[Order]:
    result = await session.execute(select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()))
    return list(result.scalars().all())


async def list_by_status(session: AsyncSession, status: str) -> list[Order]:
    result = await session.execute(select(Order).where(Order.status == status).order_by(Order.created_at.desc()))
    return list(result.scalars().all())


async def update_status(session: AsyncSession, order: Order, status: str) -> Order:
    order.status = status
    await session.commit()
    await session.refresh(order)
    return order
