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
