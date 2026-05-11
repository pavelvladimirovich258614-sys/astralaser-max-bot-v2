from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.crud import order as order_crud
from src.db.models import Order

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
