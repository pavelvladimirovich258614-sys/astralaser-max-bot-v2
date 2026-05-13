from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config import get_settings
from src.db.crud import category as category_crud
from src.db.crud import order as order_crud
from src.db.crud import product as product_crud
from src.db.crud import user as user_crud
from src.db.models import Category, Order, Product, ProductPhoto, User

VALID_STATUSES = {"pending", "confirmed", "completed", "cancelled"}

_STATUS_EMOJI = {
    "pending": "🟡",
    "confirmed": "🔵",
    "completed": "✅",
    "cancelled": "❌",
}


async def get_recent_orders(session: AsyncSession, limit: int = 10) -> list[Order]:
    """Получить последние N заказов (все статусы), сортировка по убыванию created_at."""
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
# Short stats
# ---------------------------------------------------------------------------


async def get_short_stats(session: AsyncSession) -> dict[str, int]:
    """Короткая сводка по заказам, товарам и пользователям."""
    order_total_result = await session.execute(select(func.count(Order.id)))
    order_total = int(order_total_result.scalar_one() or 0)

    order_counts: dict[str, int] = {}
    for st in VALID_STATUSES:
        r = await session.execute(select(func.count(Order.id)).where(Order.status == st))
        order_counts[st] = int(r.scalar_one() or 0)

    product_total_result = await session.execute(select(func.count(Product.id)))
    product_total = int(product_total_result.scalar_one() or 0)

    product_active_result = await session.execute(select(func.count(Product.id)).where(Product.is_active.is_(True)))
    product_active = int(product_active_result.scalar_one() or 0)

    # consented users = consent_at IS NOT NULL
    user_result = await session.execute(select(func.count(User.id)).where(User.consent_at.is_not(None)))
    user_consented = int(user_result.scalar_one() or 0)

    return {
        "order_total": order_total,
        "order_pending": order_counts.get("pending", 0),
        "order_confirmed": order_counts.get("confirmed", 0),
        "order_completed": order_counts.get("completed", 0),
        "product_total": product_total,
        "product_active": product_active,
        "product_hidden": product_total - product_active,
        "user_consented": user_consented,
    }


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


# ---------------------------------------------------------------------------
# Broadcast plan (F10.5.2a)
# ---------------------------------------------------------------------------


@dataclass
class BroadcastRecipientDTO:
    user_id: int
    max_user_id: str
    max_chat_id: str | None
    username: str | None
    full_name: str | None


@dataclass
class BroadcastPlanDTO:
    enabled: bool
    text: str
    recipients: list[BroadcastRecipientDTO]
    total_recipients: int
    throttle_ms: int
    max_recipients: int
    reason: str | None = None


async def prepare_broadcast_plan(session: AsyncSession, text: str) -> BroadcastPlanDTO:
    """Подготовить план рассылки без фактической отправки.

    Возвращает потенциальных получателей даже когда BROADCAST_ENABLED=false,
    чтобы админ видел количество до активации.
    """
    settings = get_settings()
    enabled = settings.broadcast_enabled
    max_recipients = settings.broadcast_max_recipients
    throttle_ms = settings.broadcast_throttle_ms

    all_users = await user_crud.get_broadcast_recipients(session)

    users = all_users
    if max_recipients > 0:
        users = users[:max_recipients]

    recipients = [
        BroadcastRecipientDTO(
            user_id=user.id,
            max_user_id=user.max_user_id,
            max_chat_id=user.max_chat_id,
            username=user.username,
            full_name=user.full_name,
        )
        for user in users
    ]

    if not enabled:
        return BroadcastPlanDTO(
            enabled=False,
            text=text,
            recipients=recipients,
            total_recipients=len(recipients),
            throttle_ms=throttle_ms,
            max_recipients=max_recipients,
            reason="disabled",
        )

    return BroadcastPlanDTO(
        enabled=True,
        text=text,
        recipients=recipients,
        total_recipients=len(recipients),
        throttle_ms=throttle_ms,
        max_recipients=max_recipients,
        reason=None,
    )
