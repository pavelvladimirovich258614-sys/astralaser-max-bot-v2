from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.crud import cart as cart_crud
from src.db.models import User


async def add_item(session: AsyncSession, user: User, product_id: int, quantity: int = 1) -> None:
    """Добавить товар в корзину пользователя."""
    await cart_crud.add_item(session, user_id=user.id, product_id=product_id, quantity=quantity)
