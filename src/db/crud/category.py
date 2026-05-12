from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Category


async def get_active_categories(session: AsyncSession) -> list[Category]:
    result = await session.execute(select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order))
    return list(result.scalars().all())


async def get_by_slug(session: AsyncSession, slug: str) -> Category | None:
    result = await session.execute(select(Category).where(Category.slug == slug))
    return result.scalar_one_or_none()


async def get_all_categories(session: AsyncSession) -> list[Category]:
    """Все категории (включая неактивные), сортировка по sort_order."""
    result = await session.execute(select(Category).order_by(Category.sort_order))
    return list(result.scalars().all())
