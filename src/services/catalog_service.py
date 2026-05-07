from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.crud import category as category_crud
from src.db.crud import product as product_crud
from src.db.crud import product_photo as photo_crud
from src.db.models import Category, Product


@dataclass(frozen=True)
class CategoryDTO:
    id: int
    title: str
    slug: str
    products_count: int


@dataclass(frozen=True)
class ProductDTO:
    id: int
    title: str
    price: int
    cover_url: str


@dataclass(frozen=True)
class ProductCardDTO:
    title: str
    price: int
    description: str
    photo_url: str
    photo: dict[str, Any] | None
    photo_count: int
    photo_index: int
    category_slug: str


async def get_categories_with_count(session: AsyncSession) -> list[CategoryDTO]:
    """Все активные категории с количеством активных товаров."""
    # Запрос: категории + count(products)
    stmt = (
        select(Category, func.count(Product.id))
        .outerjoin(Product, (Category.id == Product.category_id) & Product.is_active.is_(True))
        .where(Category.is_active.is_(True))
        .group_by(Category.id)
        .order_by(Category.sort_order)
    )
    result = await session.execute(stmt)
    return [
        CategoryDTO(id=cat.id, title=cat.title, slug=cat.slug, products_count=count)
        for cat, count in result.all()
    ]


async def get_products_by_slug(session: AsyncSession, slug: str) -> list[ProductDTO]:
    """Товары категории по slug."""
    category = await category_crud.get_by_slug(session, slug)
    if not category:
        return []
    products = await product_crud.get_by_category(session, category.id)
    return [
        ProductDTO(id=p.id, title=p.title, price=p.price, cover_url=p.cover_url)
        for p in products
    ]


async def get_product_card(
    session: AsyncSession, product_id: int, photo_index: int = 0,
) -> ProductCardDTO | None:
    """Карточка товара: фото по индексу (циклически)."""
    # Eager-load category to avoid lazy-loading issues in async session
    result = await session.execute(
        select(Product).where(Product.id == product_id).options(selectinload(Product.category))
    )
    product = result.scalar_one_or_none()
    if not product:
        return None

    photos = await photo_crud.get_by_product_id(session, product.id)
    photo_count = len(photos)
    category_slug = product.category.slug if product.category else ""

    if photo_count == 0:
        # Если нет фото в таблице product_photos, используем cover_url
        return ProductCardDTO(
            title=product.title,
            price=product.price,
            description=product.description,
            photo_url=product.cover_url,
            photo=None,
            photo_count=1,
            photo_index=0,
            category_slug=category_slug,
        )

    # Циклическая пагинация
    photo_index = photo_index % photo_count
    photo_obj = photos[photo_index]
    photo_payload: dict[str, Any] | None = None
    if photo_obj.max_photo_token is not None:
        photo_payload = {"token": photo_obj.max_photo_token}

    return ProductCardDTO(
        title=product.title,
        price=product.price,
        description=product.description,
        photo_url=photo_obj.url,
        photo=photo_payload,
        photo_count=photo_count,
        photo_index=photo_index,
        category_slug=category_slug,
    )
