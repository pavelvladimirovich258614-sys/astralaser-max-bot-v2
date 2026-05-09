from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.crud import cart as cart_crud
from src.db.models import User


@dataclass(frozen=True)
class CartItemDTO:
    product_id: int
    title: str
    price: int
    quantity: int
    line_total: int


@dataclass(frozen=True)
class CartViewDTO:
    items: list[CartItemDTO]
    total: int


async def add_item(session: AsyncSession, user: User, product_id: int, quantity: int = 1) -> None:
    """Добавить товар в корзину пользователя."""
    await cart_crud.add_item(session, user_id=user.id, product_id=product_id, quantity=quantity)


async def get_cart_view(session: AsyncSession, user_id: int) -> CartViewDTO:
    """Получить корзину пользователя с DTO для отображения."""
    cart_items = await cart_crud.get_user_cart_with_products(session, user_id)
    items: list[CartItemDTO] = []
    total = 0
    for ci in cart_items:
        line_total = ci.product.price * ci.quantity
        items.append(
            CartItemDTO(
                product_id=ci.product_id,
                title=ci.product.title,
                price=ci.product.price,
                quantity=ci.quantity,
                line_total=line_total,
            )
        )
        total += line_total
    return CartViewDTO(items=items, total=total)


async def change_quantity(session: AsyncSession, user_id: int, product_id: int, delta: int) -> CartViewDTO:
    """Изменить количество товара на delta и вернуть актуальную корзину."""
    await cart_crud.change_quantity(session, user_id, product_id, delta)
    return await get_cart_view(session, user_id)


async def remove_item(session: AsyncSession, user_id: int, product_id: int) -> CartViewDTO:
    """Удалить позицию из корзины и вернуть актуальную корзину."""
    await cart_crud.remove_item(session, user_id, product_id)
    return await get_cart_view(session, user_id)


async def clear_cart(session: AsyncSession, user_id: int) -> CartViewDTO:
    """Очистить корзину и вернуть актуальную корзину."""
    await cart_crud.clear_cart(session, user_id)
    return await get_cart_view(session, user_id)
