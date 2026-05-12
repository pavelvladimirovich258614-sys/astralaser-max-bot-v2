from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Product


async def get_by_id(session: AsyncSession, product_id: int) -> Product | None:
    result = await session.execute(select(Product).where(Product.id == product_id))
    return result.scalar_one_or_none()


async def get_by_category(session: AsyncSession, category_id: int) -> list[Product]:
    result = await session.execute(
        select(Product).where(Product.category_id == category_id, Product.is_active.is_(True)).order_by(Product.sort_order)
    )
    return list(result.scalars().all())


async def get_active_only(session: AsyncSession) -> list[Product]:
    result = await session.execute(select(Product).where(Product.is_active.is_(True)).order_by(Product.sort_order))
    return list(result.scalars().all())


async def get_by_category_all(session: AsyncSession, category_id: int) -> list[Product]:
    """Все товары категории (включая неактивные)."""
    result = await session.execute(
        select(Product).where(Product.category_id == category_id).order_by(Product.sort_order)
    )
    return list(result.scalars().all())


async def toggle_active(session: AsyncSession, product_id: int) -> Product | None:
    """Переключить is_active у товара. Возвращает обновлённый товар или None."""
    product = await get_by_id(session, product_id)
    if product is None:
        return None
    product.is_active = not product.is_active
    await session.commit()
    return product
