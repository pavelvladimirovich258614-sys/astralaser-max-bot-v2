from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ProductPhoto


async def get_by_product_id(session: AsyncSession, product_id: int) -> list[ProductPhoto]:
    result = await session.execute(
        select(ProductPhoto).where(ProductPhoto.product_id == product_id).order_by(ProductPhoto.sort_order)
    )
    return list(result.scalars().all())


async def create_photos(session: AsyncSession, product_id: int, urls: list[str]) -> list[ProductPhoto]:
    """Создать ProductPhoto для каждого URL. sort_order = индекс. max_photo_token = None."""
    photos: list[ProductPhoto] = []
    for idx, url in enumerate(urls):
        photo = ProductPhoto(
            product_id=product_id,
            url=url,
            sort_order=idx,
            max_photo_token=None,
        )
        session.add(photo)
        photos.append(photo)
    await session.flush()
    return photos
