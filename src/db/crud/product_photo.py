from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ProductPhoto


async def get_by_product_id(session: AsyncSession, product_id: int) -> list[ProductPhoto]:
    result = await session.execute(
        select(ProductPhoto).where(ProductPhoto.product_id == product_id).order_by(ProductPhoto.sort_order)
    )
    return list(result.scalars().all())
