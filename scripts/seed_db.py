import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select

from src.bot.max_client import MAXClient
from src.config import get_settings
from src.db.engine import async_session_maker
from src.db.models import Category, Product, ProductPhoto
from src.services import max_upload_service

SEED_FILE = Path(__file__).parent.parent / "data" / "seed_products.json"

from src.utils.logging_config import setup_logging

setup_logging(logging.INFO)
logger = logging.getLogger(__name__)


async def seed() -> int:
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    async with async_session_maker() as session:
        new_products_total = 0
        for cat_data in data["categories"]:
            # Получить или создать категорию
            result = await session.execute(select(Category).where(Category.slug == cat_data["slug"]))
            category = result.scalar_one_or_none()
            if not category:
                category = Category(
                    title=cat_data["title"],
                    slug=cat_data["slug"],
                    description=cat_data.get("description"),
                    sort_order=cat_data.get("sort_order", 0),
                    is_active=cat_data.get("is_active", True),
                )
                session.add(category)
                await session.flush()
            else:
                category.title = cat_data["title"]
                category.description = cat_data.get("description")
                category.sort_order = cat_data.get("sort_order", 0)
                category.is_active = cat_data.get("is_active", True)

            for prod_data in cat_data.get("products", []):
                # Ищем по category+sort_order, чтобы переименование не создало дубль.
                result = await session.execute(
                    select(Product).where(
                        Product.category_id == category.id,
                        Product.sort_order == prod_data.get("sort_order", 0),
                    )
                )
                product = result.scalar_one_or_none()
                photo_urls = prod_data.get("photo_urls", [])
                cover_url = photo_urls[0] if photo_urls else ""
                if not product:
                    new_products_total += 1
                    product = Product(
                        category_id=category.id,
                        title=prod_data["title"],
                        description=prod_data["description"],
                        price=prod_data["price"],
                        cover_url=cover_url,
                        sort_order=prod_data.get("sort_order", 0),
                        is_active=prod_data.get("is_active", True),
                    )
                    session.add(product)
                    await session.flush()
                else:
                    product.title = prod_data["title"]
                    product.description = prod_data["description"]
                    product.price = prod_data["price"]
                    product.cover_url = cover_url
                    product.sort_order = prod_data.get("sort_order", 0)
                    product.is_active = prod_data.get("is_active", True)

                result = await session.execute(select(ProductPhoto).where(ProductPhoto.product_id == product.id))
                photos_by_order = {photo.sort_order: photo for photo in result.scalars().all()}

                for idx, photo_url in enumerate(prod_data.get("photo_urls", [])):
                    photo = photos_by_order.get(idx)
                    if not photo:
                        session.add(ProductPhoto(product_id=product.id, url=photo_url, sort_order=idx))
                        continue

                    if photo.url != photo_url:
                        photo.url = photo_url
                        photo.max_photo_token = None

                await session.execute(
                    delete(ProductPhoto).where(
                        ProductPhoto.product_id == product.id,
                        ProductPhoto.sort_order >= len(photo_urls),
                    )
                )

        await session.commit()
        print(f"Seed complete: new_products_total={new_products_total}")

        # Загрузка фото в MAX (требует MAX_BOT_TOKEN)
        settings = get_settings()
        if settings.max_bot_token:
            await _upload_photos_to_max()
        else:
            logger.warning("MAX_BOT_TOKEN not set, skipping photo upload to MAX")

        return new_products_total


async def _upload_photos_to_max() -> None:
    """Идемпотентно загружает фото из БД в MAX API."""
    client = MAXClient()
    try:
        async with async_session_maker() as session:
            result = await session.execute(select(ProductPhoto).where(ProductPhoto.max_photo_token.is_(None)))
            photos = list(result.scalars().all())

            for photo in photos:
                token = await max_upload_service.upload_image_from_url(client, photo.url)
                if token:
                    photo.max_photo_token = token
                    await session.commit()
                    logger.info("Uploaded photo for product_id=%s", photo.product_id)
                    await asyncio.sleep(1)
                else:
                    logger.warning("Failed to upload photo for product_id=%s: %s", photo.product_id, photo.url)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(seed())
