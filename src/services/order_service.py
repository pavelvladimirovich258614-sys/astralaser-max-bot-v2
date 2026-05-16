from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.crud import order as order_crud
from src.db.crud import user as user_crud
from src.db.models import Order
from src.services.cart_service import CartViewDTO


@dataclass(frozen=True)
class OrderCancellationResult:
    """Результат попытки пользовательской отмены заказа."""

    order: Order | None
    cancelled: bool
    reason: str


def format_manager_notification(
    order_id: int,
    cart_view: CartViewDTO,
    customer_name: str,
    customer_phone: str,
    delivery_address: str,
    notes: str | None,
) -> str:
    """Сформировать текст уведомления менеджеру о новом заказе."""
    lines = [f"🔔 Новый заказ #{order_id}\n"]
    lines.append("Товары:")
    for idx, item in enumerate(cart_view.items, 1):
        lines.append(f"{idx}. {item.title}")
        lines.append(f"{item.price} ₽ × {item.quantity} = {item.line_total} ₽")
    lines.append(f"\nИтого: {cart_view.total} ₽\n")
    lines.append("Клиент:")
    lines.append(f"👤 {customer_name}")
    lines.append(f"📞 {customer_phone}")
    lines.append(f"📍 {delivery_address}")
    lines.append(f"✏️ {notes or '—'}")
    return "\n".join(lines)


async def get_user_orders(session: AsyncSession, user_id: int) -> list[Order]:
    """Получить последние 5 заказов пользователя (сортировка по убыванию id)."""
    orders = await order_crud.get_by_user(session, user_id)
    return orders[:5]


async def get_admin_notification_chat_ids(
    session: AsyncSession,
    configured_chat_ids: Sequence[str],
    admin_user_ids: Sequence[str],
) -> list[str]:
    """Собрать chat_id для системных уведомлений из явного конфига и admin user IDs."""
    chat_ids: list[str] = []
    seen: set[str] = set()

    for chat_id in configured_chat_ids:
        cleaned = str(chat_id).strip()
        if cleaned and cleaned not in seen:
            chat_ids.append(cleaned)
            seen.add(cleaned)

    admin_users = await user_crud.get_users_by_max_ids(session, admin_user_ids)
    for user in admin_users:
        cleaned = user.max_chat_id.strip() if user.max_chat_id else ""
        if cleaned and cleaned not in seen:
            chat_ids.append(cleaned)
            seen.add(cleaned)

    return chat_ids


async def get_user_order_detail(session: AsyncSession, user_id: int, order_id: int) -> Order | None:
    """Получить заказ пользователя по ID, не раскрывая чужие заказы."""
    order = await order_crud.get_by_id(session, order_id)
    if order is None or order.user_id != user_id:
        return None
    return order


async def cancel_user_order(session: AsyncSession, user_id: int, order_id: int) -> OrderCancellationResult:
    """Отменить заказ пользователя, если он ещё ожидает подтверждения."""
    order = await get_user_order_detail(session, user_id, order_id)
    if order is None:
        return OrderCancellationResult(order=None, cancelled=False, reason="not_found")
    if order.status != "pending":
        return OrderCancellationResult(order=order, cancelled=False, reason="not_cancelable")

    cancelled_order = await order_crud.update_status(session, order, "cancelled")
    return OrderCancellationResult(order=cancelled_order, cancelled=True, reason="cancelled")


def format_order_cancellation_notification(order_id: int, max_user_id: str, user_name: str | None) -> str:
    """Сформировать уведомление администратору об отмене заказа пользователем."""
    display_name = user_name.strip() if user_name else ""
    user_text = f"{max_user_id} / {display_name}" if display_name else max_user_id
    return f"⚠️ Пользователь {user_text} отменил заказ №{order_id}"


async def create_order_from_cart(
    session: AsyncSession,
    user_id: int,
    customer_name: str,
    customer_phone: str,
    delivery_address: str,
    notes: str | None,
    cart_view: CartViewDTO,
) -> Order:
    """Создать Order и OrderItem из текущей корзины со snapshot данных."""
    items = [
        {
            "product_id": item.product_id,
            "product_title_snapshot": item.title,
            "price_snapshot": item.price,
            "quantity": item.quantity,
        }
        for item in cart_view.items
    ]
    return await order_crud.create_order(
        session=session,
        user_id=user_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        delivery_address=delivery_address,
        total_amount=cart_view.total,
        notes=notes,
        items=items,
    )
