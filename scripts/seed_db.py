import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from src.db.engine import async_session_maker
from src.db.models import Category, Product, ProductPhoto

SEED_FILE = Path(__file__).parent.parent / "data" / "seed_products.json"


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

            for prod_data in cat_data.get("products", []):
                # Проверить, существует ли товар
                result = await session.execute(
                    select(Product).where(
                        Product.title == prod_data["title"],
                        Product.category_id == category.id,
                    )
                )
                product = result.scalar_one_or_none()
                if product:
                    continue

                new_products_total += 1
                product = Product(
                    category_id=category.id,
                    title=prod_data["title"],
                    description=prod_data["description"],
                    price=prod_data["price"],
                    cover_url=prod_data["photo_urls"][0] if prod_data.get("photo_urls") else "",
                    sort_order=prod_data.get("sort_order", 0),
                    is_active=prod_data.get("is_active", True),
                )
                session.add(product)
                await session.flush()

                # Добавить фото
                for idx, photo_url in enumerate(prod_data.get("photo_urls", [])):
                    photo = ProductPhoto(
                        product_id=product.id,
                        url=photo_url,
                        sort_order=idx,
                    )
                    session.add(photo)

        await session.commit()
        print(f"Seed complete: new_products_total={new_products_total}")
        return new_products_total


if __name__ == "__main__":
    asyncio.run(seed())
