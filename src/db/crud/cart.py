from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import CartItem


async def get_user_cart(session: AsyncSession, user_id: int) -> list[CartItem]:
    result = await session.execute(select(CartItem).where(CartItem.user_id == user_id))
    return list(result.scalars().all())


async def get_user_cart_with_products(session: AsyncSession, user_id: int) -> list[CartItem]:
    """Корзина пользователя с eager-load товаров (для async-контекста)."""
    result = await session.execute(
        select(CartItem).where(CartItem.user_id == user_id).options(selectinload(CartItem.product))
    )
    return list(result.scalars().all())


async def add_item(session: AsyncSession, user_id: int, product_id: int, quantity: int = 1) -> CartItem:
    result = await session.execute(select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id))
    item = result.scalar_one_or_none()
    if item:
        item.quantity += quantity
    else:
        item = CartItem(user_id=user_id, product_id=product_id, quantity=quantity)
        session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def remove_item(session: AsyncSession, user_id: int, product_id: int) -> None:
    await session.execute(delete(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id))
    await session.commit()


async def update_quantity(session: AsyncSession, user_id: int, product_id: int, quantity: int) -> CartItem | None:
    if quantity <= 0:
        await remove_item(session, user_id, product_id)
        return None
    result = await session.execute(select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id))
    item = result.scalar_one_or_none()
    if item:
        item.quantity = quantity
        await session.commit()
        await session.refresh(item)
    return item


async def change_quantity(session: AsyncSession, user_id: int, product_id: int, delta: int) -> CartItem | None:
    """Изменить quantity на delta. Удалить позицию если quantity <= 0."""
    result = await session.execute(select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id))
    item = result.scalar_one_or_none()
    if not item:
        return None
    item.quantity += delta
    if item.quantity <= 0:
        await remove_item(session, user_id, product_id)
        return None
    await session.commit()
    await session.refresh(item)
    return item


async def clear_cart(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(CartItem).where(CartItem.user_id == user_id))
    await session.commit()
