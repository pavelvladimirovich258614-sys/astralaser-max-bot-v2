from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.crud import category as category_crud
from src.db.crud import order as order_crud
from src.db.crud import product as product_crud
from src.db.models import Category, Order, Product, ProductPhoto

VALID_STATUSES = {"pending", "confirmed", "completed", "cancelled"}

_STATUS_EMOJI = {
    "pending": "🟡",
    "confirmed": "🔵",
    "completed": "✅",
    "cancelled": "❌",
}


async def get_recent_orders(session: AsyncSession, limit: int = 10) -> list[Order]:
    """Получить последние N заказов (все статусы), сортировка по убыванию created_at."""
    # Используем list_all из order_crud или добавляем новый метод
    # Пока order_crud не имеет list_all, используем get_by_user для всех?
    # Нет, нужен list_all. Добавим в order_crud или сделаем запрос здесь.
    # Лучше добавить в order_crud list_all, но запрещено менять CRUD?
    # Нет, разрешено — admin_service использует CRUD.
    # Давайте добавим list_all в order_crud.
    from sqlalchemy import select

    result = await session.execute(
        select(Order).order_by(Order.created_at.desc(), Order.id.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def get_order_detail(session: AsyncSession, order_id: int) -> Order | None:
    """Получить заказ с загруженными items по ID."""
    return await order_crud.get_by_id(session, order_id)


async def update_order_status(session: AsyncSession, order_id: int, status: str) -> Order | None:
    """Обновить статус заказа. Возвращает Order или None если не найден или статус невалиден."""
    if status not in VALID_STATUSES:
        return None
    order = await order_crud.get_by_id(session, order_id)
    if order is None:
        return None
    return await order_crud.update_status(session, order, status)


def status_emoji(status: str) -> str:
    """Эмодзи для статуса заказа."""
    return _STATUS_EMOJI.get(status, "⚪")


def status_label(status: str) -> str:
    """Человекочитаемая метка статуса."""
    labels = {
        "pending": "В ожидании",
        "confirmed": "Подтверждён",
        "completed": "Завершён",
        "cancelled": "Отменён",
    }
    return labels.get(status, status)


# ---------------------------------------------------------------------------
# Product management (F10.3)
# ---------------------------------------------------------------------------


async def get_admin_categories(session: AsyncSession) -> list[dict[str, object]]:
    """Все категории с количеством всех товаров (включая неактивные)."""
    stmt = (
        select(Category, func.count(Product.id))
        .outerjoin(Product, Category.id == Product.category_id)
        .group_by(Category.id)
        .order_by(Category.sort_order)
    )
    result = await session.execute(stmt)
    return [
        {"category": cat, "product_count": count}
        for cat, count in result.all()
    ]


async def get_admin_category_by_slug(session: AsyncSession, slug: str) -> Category | None:
    """Получить категорию по slug для админа (включая неактивные)."""
    return await category_crud.get_by_slug(session, slug)


async def get_admin_category_by_id(session: AsyncSession, category_id: int) -> Category | None:
    """Получить категорию по id для админа (включая неактивные)."""
    categories = await category_crud.get_all_categories(session)
    for cat in categories:
        if cat.id == category_id:
            return cat
    return None


async def get_admin_products_by_category(session: AsyncSession, category_id: int) -> list[Product]:
    """Все товары категории (включая неактивные)."""
    return await product_crud.get_by_category_all(session, category_id)


async def get_admin_product_detail(session: AsyncSession, product_id: int) -> dict[str, object] | None:
    """Детали товара для админа: товар, категория, количество фото."""
    result = await session.execute(
        select(Product).where(Product.id == product_id).options(selectinload(Product.category))
    )
    product = result.scalar_one_or_none()
    if product is None:
        return None
    photo_count_result = await session.execute(
        select(func.count(ProductPhoto.id)).where(ProductPhoto.product_id == product_id)
    )
    photo_count = photo_count_result.scalar() or 0
    return {
        "product": product,
        "category": product.category,
        "photo_count": photo_count,
    }


async def toggle_product_active(session: AsyncSession, product_id: int) -> Product | None:
    """Переключить is_active у товара."""
    return await product_crud.toggle_active(session, product_id)


# ---------------------------------------------------------------------------
# Product creation (F10.4)
# ---------------------------------------------------------------------------


async def get_next_product_sort_order(session: AsyncSession, category_id: int) -> int:
    """Следующий sort_order для нового товара в категории."""
    max_order = await product_crud.get_max_sort_order(session, category_id)
    return max_order + 1


async def create_product_with_photos(
    session: AsyncSession,
    category_id: int,
    title: str,
    description: str,
    price: int,
    photo_urls: list[str],
) -> Product | None:
    """Создать товар и фото. cover_url = photo_urls[0]. Возвращает Product или None если нет фото."""
    if not photo_urls:
        return None

    from src.db.crud import product_photo as product_photo_crud

    sort_order = await get_next_product_sort_order(session, category_id)
    product = await product_crud.create_product(
        session=session,
        category_id=category_id,
        title=title,
        description=description,
        price=price,
        cover_url=photo_urls[0],
        sort_order=sort_order,
        is_active=True,
    )
    await product_photo_crud.create_photos(session, product.id, photo_urls)
    await session.commit()
    return product
