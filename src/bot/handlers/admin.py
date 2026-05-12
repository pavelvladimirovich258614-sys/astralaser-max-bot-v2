from __future__ import annotations

from typing import cast

from src.bot import keyboards as kb
from src.bot.handlers import start as start_handler
from src.bot.max_client import MAXClient
from src.config import get_settings
from src.db.engine import async_session_maker
from src.db.models import Category, Product
from src.services import admin_service

ADMIN_MENU_TEXT = """🛠 Админ-панель

Выберите раздел для управления.

📦 Заказы — просмотр и обработка заказов
📚 Товары — управление товарами
🏷 Категории — управление категориями
📊 Статистика — краткие показатели
📤 Рассылка — сообщения пользователям
🚪 Выход — вернуться в главное меню"""

NOT_FOUND_TEXT = "Команда не найдена."


async def handle_admin_command(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    user_info: dict[str, str] | None = None,
) -> None:
    """Обработка команды /admin. Доступ только для MAX_ADMIN_USER_IDS."""
    if not _is_admin(user_id):
        await client.send_message(chat_id, NOT_FOUND_TEXT)
        return
    await show_admin_menu(client, chat_id)


async def show_admin_menu(
    client: MAXClient,
    chat_id: int | str,
    message_id: str | None = None,
) -> None:
    """Показать главное меню админ-панели."""
    if message_id:
        await client.edit_message(chat_id, message_id, ADMIN_MENU_TEXT, reply_markup=kb.admin_menu_keyboard())
    else:
        await client.send_message(chat_id, ADMIN_MENU_TEXT, reply_markup=kb.admin_menu_keyboard())


async def admin_exit(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Выйти из админ-панели в главное меню."""
    await start_handler.show_main_menu(client, chat_id, message_id)


async def admin_back_to_menu(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Вернуться из placeholder-экрана в меню админ-панели."""
    if not _is_admin(user_id):
        return
    await show_admin_menu(client, chat_id, message_id)


# ---------------------------------------------------------------------------
# Skeleton callbacks для подменю F10.2–F10.5
# ---------------------------------------------------------------------------


async def admin_orders(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """📦 Заказы — показать список последних заказов (F10.2)."""
    if not _is_admin(user_id):
        return
    await show_orders_list(client, chat_id, message_id)


async def show_orders_list(
    client: MAXClient,
    chat_id: int | str,
    message_id: str | None = None,
) -> None:
    """Показать список последних заказов."""
    async with async_session_maker() as session:
        orders = await admin_service.get_recent_orders(session, limit=10)

    if not orders:
        text = "📦 Заказов пока нет."
        keyboard = kb.admin_back_keyboard()
    else:
        text = "📦 Заказы\n\nВыберите заказ:"
        keyboard = kb.admin_orders_keyboard(orders)

    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
    else:
        await client.send_message(chat_id, text, reply_markup=keyboard)


async def show_order_detail(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    order_id: int,
    message_id: str | None = None,
) -> None:
    """Показать карточку заказа."""
    if not _is_admin(user_id):
        return

    async with async_session_maker() as session:
        order = await admin_service.get_order_detail(session, order_id)

    if order is None:
        text = "Заказ не найден."
        keyboard = kb.admin_orders_back_keyboard()
        if message_id:
            await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
        else:
            await client.send_message(chat_id, text, reply_markup=keyboard)
        return

    lines = [f"📦 Заказ #{order.id}\n"]
    lines.append(f"Статус: {admin_service.status_emoji(order.status)} {admin_service.status_label(order.status)}")
    lines.append(f"Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n")
    lines.append(f"👤 {order.customer_name}")
    lines.append(f"📞 {order.customer_phone}")
    lines.append(f"📍 {order.delivery_address}\n")

    if order.items:
        lines.append("🛍 Товары:")
        for item in order.items:
            lines.append(f"• {item.product_title_snapshot} × {item.quantity} — {item.price_snapshot} ₽")
        lines.append("")

    lines.append(f"💰 Итого: {order.total_amount} ₽")
    if order.notes:
        lines.append(f"✏️ Комментарий: {order.notes}")

    text = "\n".join(lines)
    keyboard = kb.admin_order_detail_keyboard(order.id, order.status)

    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
    else:
        await client.send_message(chat_id, text, reply_markup=keyboard)


async def admin_order_status(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    order_id: int,
    status: str,
    message_id: str | None = None,
) -> None:
    """Сменить статус заказа и показать обновлённую карточку."""
    if not _is_admin(user_id):
        return

    # Проверить валидность статуса
    if status not in admin_service.VALID_STATUSES:
        text = "Неизвестный статус заказа."
        keyboard = kb.admin_orders_back_keyboard()
        if message_id:
            await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
        else:
            await client.send_message(chat_id, text, reply_markup=keyboard)
        return

    async with async_session_maker() as session:
        order = await admin_service.get_order_detail(session, order_id)
        if order is None:
            text = "Заказ не найден."
            keyboard = kb.admin_orders_back_keyboard()
            if message_id:
                await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
            else:
                await client.send_message(chat_id, text, reply_markup=keyboard)
            return

        order = await admin_service.update_order_status(session, order_id, status)
        if order is None:
            text = "Заказ не найден."
            keyboard = kb.admin_orders_back_keyboard()
            if message_id:
                await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
            else:
                await client.send_message(chat_id, text, reply_markup=keyboard)
            return

    await show_order_detail(client, chat_id, user_id, order.id, message_id)


async def admin_products(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """📚 Товары — показать список категорий (F10.3)."""
    if not _is_admin(user_id):
        return
    await show_admin_categories(client, chat_id, message_id)


async def show_admin_categories(
    client: MAXClient,
    chat_id: int | str,
    message_id: str | None = None,
) -> None:
    """Показать все категории для админа."""
    async with async_session_maker() as session:
        categories = await admin_service.get_admin_categories(session)

    if not categories:
        text = "📚 Категории товаров пока не созданы."
        keyboard = kb.admin_back_keyboard()
    else:
        text = "📚 Управление товарами\n\nВыберите категорию:"
        keyboard = kb.admin_categories_keyboard(categories)

    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
    else:
        await client.send_message(chat_id, text, reply_markup=keyboard)


async def show_admin_products_list(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    slug: str,
    message_id: str | None = None,
) -> None:
    """Показать все товары категории (включая скрытые)."""
    if not _is_admin(user_id):
        return

    async with async_session_maker() as session:
        category = await admin_service.get_admin_category_by_slug(session, slug)
        if category is None:
            text = "Категория не найдена."
            keyboard = kb.admin_back_keyboard()
            if message_id:
                await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
            else:
                await client.send_message(chat_id, text, reply_markup=keyboard)
            return

        products = await admin_service.get_admin_products_by_category(session, category.id)

    if not products:
        text = f"📚 {category.title}\n\nВ этой категории пока нет товаров."
        keyboard = kb.admin_products_keyboard([], category.slug)
    else:
        text = f"📚 {category.title}\n\nВыберите товар:"
        keyboard = kb.admin_products_keyboard(products, category.slug)

    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
    else:
        await client.send_message(chat_id, text, reply_markup=keyboard)


async def show_admin_product_detail(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    product_id: int,
    message_id: str | None = None,
) -> None:
    """Показать карточку товара для админа."""
    if not _is_admin(user_id):
        return

    async with async_session_maker() as session:
        detail = await admin_service.get_admin_product_detail(session, product_id)

    if detail is None:
        text = "Товар не найден."
        keyboard = kb.admin_back_keyboard()
        if message_id:
            await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
        else:
            await client.send_message(chat_id, text, reply_markup=keyboard)
        return

    product = cast(Product, detail["product"])
    category = cast(Category | None, detail["category"])
    photo_count = cast(int, detail["photo_count"])
    status_text = "Активен" if product.is_active else "Скрыт"
    description = _short_description(product.description, max_length=300)

    lines = [
        f"📦 Товар #{product.id}",
        "",
        f"Название: {product.title}",
        f"Категория: {category.title if category else '—'}",
        f"Цена: {product.price} ₽",
        f"Статус: {status_text}",
        f"Фото: {photo_count}",
        "",
        f"Описание:\n{description}",
    ]
    text = "\n".join(lines)
    category_slug = category.slug if category else ""
    keyboard = kb.admin_product_detail_keyboard(product.id, product.is_active, category_slug)

    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
    else:
        await client.send_message(chat_id, text, reply_markup=keyboard)


async def admin_product_toggle(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    product_id: int,
    message_id: str | None = None,
) -> None:
    """Переключить is_active товара и перерисовать карточку."""
    if not _is_admin(user_id):
        return

    async with async_session_maker() as session:
        product = await admin_service.toggle_product_active(session, product_id)

    if product is None:
        text = "Товар не найден."
        keyboard = kb.admin_back_keyboard()
        if message_id:
            await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
        else:
            await client.send_message(chat_id, text, reply_markup=keyboard)
        return

    await show_admin_product_detail(client, chat_id, user_id, product.id, message_id)


def _short_description(text: str, max_length: int = 300) -> str:
    """Обрезать описание до max_length символов."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


async def admin_categories(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """🏷 Категории — placeholder (F10.3)."""
    if not _is_admin(user_id):
        return
    text = "🏷 Категории — скоро."
    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_back_keyboard())
    else:
        await client.send_message(chat_id, text, reply_markup=kb.admin_back_keyboard())


async def admin_stats(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """📊 Статистика — placeholder."""
    if not _is_admin(user_id):
        return
    text = "📊 Статистика — скоро."
    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_back_keyboard())
    else:
        await client.send_message(chat_id, text, reply_markup=kb.admin_back_keyboard())


async def admin_broadcast(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """📤 Рассылка — placeholder (F10.5)."""
    if not _is_admin(user_id):
        return
    text = "📤 Рассылка — скоро."
    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_back_keyboard())
    else:
        await client.send_message(chat_id, text, reply_markup=kb.admin_back_keyboard())


def _is_admin(user_id: int | str) -> bool:
    """Проверить, что user_id входит в список администраторов."""
    return str(user_id) in get_settings().admin_ids_list
