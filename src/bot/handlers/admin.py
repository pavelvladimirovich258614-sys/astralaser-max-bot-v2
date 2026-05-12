from __future__ import annotations

import asyncio
from typing import Any, cast

from src.bot import keyboards as kb
from src.bot.handlers import start as start_handler
from src.bot.max_client import MAXClient
from src.config import get_settings
from src.db.engine import async_session_maker
from src.db.models import Category, Product
from src.services import admin_service, fsm_service, user_service

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
        keyboard = kb.admin_add_start_keyboard() + kb.admin_categories_keyboard(categories)

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
    """📤 Рассылка — начать FSM: запросить текст сообщения."""
    if not _is_admin(user_id):
        await client.send_message(chat_id, NOT_FOUND_TEXT)
        return

    async with async_session_maker() as session:
        user_obj = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        await fsm_service.set_state(session, user_obj.id, fsm_service.ADMIN_BROADCAST_TEXT, {})

    text = "📤 Рассылка\n\nВведите текст сообщения для пользователей:"
    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_broadcast_text_keyboard())
    else:
        await client.send_message(chat_id, text, reply_markup=kb.admin_broadcast_text_keyboard())


async def admin_broadcast_cancel(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Отменить рассылку и вернуться в админ-панель."""
    if not _is_admin(user_id):
        await client.send_message(chat_id, NOT_FOUND_TEXT)
        return

    async with async_session_maker() as session:
        user_obj = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        await fsm_service.clear_state(session, user_obj.id)

    await show_admin_menu(client, chat_id, message_id)


async def admin_broadcast_send(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Отправить рассылку (F10.5.2)."""
    if not _is_admin(user_id):
        await client.send_message(chat_id, NOT_FOUND_TEXT)
        return

    async with async_session_maker() as session:
        user_obj = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        state, data = await fsm_service.get_state(session, user_obj.id)
        broadcast_text = data.get("broadcast_text") if data else None

        if not broadcast_text:
            await fsm_service.clear_state(session, user_obj.id)
            text = "❌ Текст рассылки не найден. Начните заново через /admin → 📤 Рассылка."
            if message_id:
                await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_back_keyboard())
            else:
                await client.send_message(chat_id, text, reply_markup=kb.admin_back_keyboard())
            return

        plan = await admin_service.prepare_broadcast_plan(session, broadcast_text)

        if not plan.enabled:
            await fsm_service.clear_state(session, user_obj.id)
            text = (
                "📤 Рассылка не отправлена.\n\n"
                "Рассылка отключена настройкой BROADCAST_ENABLED=false.\n"
                f"Потенциальных получателей: {plan.total_recipients}.\n"
                "Для реальной отправки нужен отдельный approve."
            )
            if message_id:
                await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_back_keyboard())
            else:
                await client.send_message(chat_id, text, reply_markup=kb.admin_back_keyboard())
            return

        # enabled=True — выполняем отправку
        sent_count = 0
        failed_count = 0
        for recipient in plan.recipients:
            try:
                await client.send_message(recipient.max_user_id, plan.text)
                sent_count += 1
            except Exception:
                failed_count += 1
            if plan.throttle_ms > 0:
                await asyncio.sleep(plan.throttle_ms / 1000)

        await fsm_service.clear_state(session, user_obj.id)

    text = f"📤 Рассылка завершена: отправлено {sent_count}, ошибок {failed_count}."
    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_back_keyboard())
    else:
        await client.send_message(chat_id, text, reply_markup=kb.admin_back_keyboard())


# ---------------------------------------------------------------------------
# Admin add product FSM (F10.4)
# ---------------------------------------------------------------------------


async def admin_add_start(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Начать добавление товара: показать выбор категории."""
    if not _is_admin(user_id):
        await client.send_message(chat_id, NOT_FOUND_TEXT)
        return

    async with async_session_maker() as session:
        categories = await admin_service.get_admin_categories(session)

    if not categories:
        text = "📚 Категории товаров пока не созданы."
        keyboard = kb.admin_back_keyboard()
    else:
        text = "➕ Добавление товара\n\nВыберите категорию:"
        keyboard = kb.admin_add_categories_keyboard(categories)

    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
    else:
        await client.send_message(chat_id, text, reply_markup=keyboard)


async def admin_add_category_selected(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    category_id: int,
    message_id: str | None = None,
) -> None:
    """Категория выбрана — сохранить и перейти к вводу названия."""
    if not _is_admin(user_id):
        await client.send_message(chat_id, NOT_FOUND_TEXT)
        return

    async with async_session_maker() as session:
        cat = await admin_service.get_admin_category_by_id(session, category_id)
        if cat is None:
            text = "Категория не найдена."
            if message_id:
                await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_back_keyboard())
            else:
                await client.send_message(chat_id, text, reply_markup=kb.admin_back_keyboard())
            return

        user_obj = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        await fsm_service.set_state(
            session,
            user_obj.id,
            fsm_service.ADMIN_ADD_TITLE,
            {"category_id": category_id, "category_title": cat.title},
        )

    text = "Введите название товара (2–256 символов):"
    if message_id:
        await client.edit_message(chat_id, message_id, text)
    else:
        await client.send_message(chat_id, text)


async def handle_admin_fsm_message(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None,
    text: str,
) -> bool:
    """Обработать текстовое сообщение в admin FSM. Возвращает True если обработано."""
    if not _is_admin(user_id):
        await client.send_message(chat_id, NOT_FOUND_TEXT)
        return True

    async with async_session_maker() as session:
        user_obj = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        state, data = await fsm_service.get_state(session, user_obj.id)

        if state == fsm_service.ADMIN_ADD_TITLE:
            return await _handle_admin_add_title(client, chat_id, user_id, message_id, text, session, user_obj.id, data)
        if state == fsm_service.ADMIN_ADD_PRICE:
            return await _handle_admin_add_price(client, chat_id, user_id, message_id, text, session, user_obj.id, data)
        if state == fsm_service.ADMIN_ADD_DESCRIPTION:
            return await _handle_admin_add_description(client, chat_id, user_id, message_id, text, session, user_obj.id, data)
        if state == fsm_service.ADMIN_ADD_PHOTOS:
            return await _handle_admin_add_photos(client, chat_id, user_id, message_id, text, session, user_obj.id, data)
        if state == fsm_service.ADMIN_BROADCAST_TEXT:
            return await _handle_admin_broadcast_text(client, chat_id, user_id, message_id, text, session, user_obj.id, data)

    return False


async def _handle_admin_add_title(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None,
    text: str,
    session: Any,
    user_db_id: int,
    data: dict[str, Any],
) -> bool:
    title = text.strip()
    if len(title) < 2 or len(title) > 256:
        err = "Название должно быть от 2 до 256 символов. Попробуйте ещё раз:"
        await client.send_message(chat_id, err)
        return True

    await fsm_service.update_data(session, user_db_id, {"title": title}, fsm_service.ADMIN_ADD_PRICE)
    prompt = "Введите цену товара целым числом в рублях (1–1 000 000):"
    await client.send_message(chat_id, prompt)
    return True


async def _handle_admin_add_price(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None,
    text: str,
    session: Any,
    user_db_id: int,
    data: dict[str, Any],
) -> bool:
    try:
        price = int(text.strip())
    except ValueError:
        err = "Цена должна быть целым числом. Попробуйте ещё раз:"
        await client.send_message(chat_id, err)
        return True

    if price <= 0 or price > 1_000_000:
        err = "Цена должна быть от 1 до 1 000 000 ₽. Попробуйте ещё раз:"
        await client.send_message(chat_id, err)
        return True

    await fsm_service.update_data(session, user_db_id, {"price": price}, fsm_service.ADMIN_ADD_DESCRIPTION)
    prompt = "Введите описание товара (до 1000 символов):"
    await client.send_message(chat_id, prompt)
    return True


async def _handle_admin_add_description(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None,
    text: str,
    session: Any,
    user_db_id: int,
    data: dict[str, Any],
) -> bool:
    description = text.strip()
    if not description:
        err = "Описание не может быть пустым. Попробуйте ещё раз:"
        await client.send_message(chat_id, err)
        return True

    if len(description) > 1000:
        err = "Описание слишком длинное (максимум 1000 символов). Попробуйте ещё раз:"
        await client.send_message(chat_id, err)
        return True

    await fsm_service.update_data(
        session, user_db_id, {"description": description, "photo_urls": []}, fsm_service.ADMIN_ADD_PHOTOS
    )
    prompt = (
        "Отправьте URL фото товара.\n\n"
        "Можно отправить один или несколько URL (каждый с новой строки).\n"
        "Минимум одно фото обязательно.\n"
        "После добавления фото нажмите ✅ Готово."
    )
    await client.send_message(chat_id, prompt, reply_markup=kb.admin_add_photos_keyboard())
    return True


async def _handle_admin_add_photos(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None,
    text: str,
    session: Any,
    user_db_id: int,
    data: dict[str, Any],
) -> bool:
    lines = [line.strip() for line in text.splitlines()]
    valid_urls = [line for line in lines if line.startswith(("http://", "https://"))]

    if not valid_urls:
        err = "Не найдено валидных URL. Отправьте ссылки, начинающиеся с http:// или https://"
        await client.send_message(chat_id, err, reply_markup=kb.admin_add_photos_keyboard())
        return True

    current_urls: list[str] = data.get("photo_urls", [])
    current_urls.extend(valid_urls)
    await fsm_service.set_state(session, user_db_id, fsm_service.ADMIN_ADD_PHOTOS, {**data, "photo_urls": current_urls})

    count = len(current_urls)
    msg = f"Добавлено фото: {count}\n\nОтправьте ещё URL или нажмите ✅ Готово."
    await client.send_message(chat_id, msg, reply_markup=kb.admin_add_photos_keyboard())
    return True


async def _handle_admin_broadcast_text(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None,
    text: str,
    session: Any,
    user_db_id: int,
    data: dict[str, Any],
) -> bool:
    broadcast_text = text.strip()
    if not broadcast_text:
        err = "Текст рассылки не может быть пустым. Попробуйте ещё раз:"
        await client.send_message(chat_id, err, reply_markup=kb.admin_broadcast_text_keyboard())
        return True

    if len(broadcast_text) > 4000:
        err = "Текст рассылки слишком длинный (максимум 4000 символов). Попробуйте ещё раз:"
        await client.send_message(chat_id, err, reply_markup=kb.admin_broadcast_text_keyboard())
        return True

    await fsm_service.set_state(session, user_db_id, fsm_service.ADMIN_BROADCAST_TEXT, {**data, "broadcast_text": broadcast_text})
    preview = (
        "📤 Предпросмотр рассылки\n\n"
        f"{broadcast_text}\n\n"
        "Отправить это сообщение всем пользователям?"
    )
    await client.send_message(chat_id, preview, reply_markup=kb.admin_broadcast_preview_keyboard())
    return True


async def admin_add_photos_done(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Завершить сбор фото и показать превью."""
    if not _is_admin(user_id):
        await client.send_message(chat_id, NOT_FOUND_TEXT)
        return

    async with async_session_maker() as session:
        user_obj = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        state, data = await fsm_service.get_state(session, user_obj.id)

        if state != fsm_service.ADMIN_ADD_PHOTOS:
            return

        photo_urls: list[str] = data.get("photo_urls", [])
        if not photo_urls:
            err = "Нужно добавить минимум одно фото. Отправьте URL или нажмите ❌ Отмена."
            if message_id:
                await client.edit_message(chat_id, message_id, err, reply_markup=kb.admin_add_photos_keyboard())
            else:
                await client.send_message(chat_id, err, reply_markup=kb.admin_add_photos_keyboard())
            return

        await fsm_service.set_state(session, user_obj.id, fsm_service.ADMIN_ADD_PREVIEW, data)
        await _show_admin_add_preview(client, chat_id, message_id, data)


async def _show_admin_add_preview(
    client: MAXClient,
    chat_id: int | str,
    message_id: str | None,
    data: dict[str, Any],
) -> None:
    text = _build_preview_text(data)
    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_add_preview_keyboard())
    else:
        await client.send_message(chat_id, text, reply_markup=kb.admin_add_preview_keyboard())


def _build_preview_text(data: dict[str, Any]) -> str:
    lines = [
        "📋 Превью товара",
        "",
        f"Название: {data.get('title', '')}",
        f"Категория: {data.get('category_title', '')}",
        f"Цена: {data.get('price', 0)} ₽",
        f"Описание: {data.get('description', '')}",
        f"Фото: {len(data.get('photo_urls', []))} шт.",
        "",
        "Первое фото будет обложкой.",
    ]
    return "\n".join(lines)


async def admin_add_save(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Сохранить товар и фото."""
    if not _is_admin(user_id):
        await client.send_message(chat_id, NOT_FOUND_TEXT)
        return

    async with async_session_maker() as session:
        user_obj = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        state, data = await fsm_service.get_state(session, user_obj.id)

        if state != fsm_service.ADMIN_ADD_PREVIEW:
            return

        required = ["category_id", "title", "description", "price", "photo_urls"]
        if not all(data.get(k) for k in required):
            err = "Не хватает данных для создания товара. Начните заново."
            if message_id:
                await client.edit_message(chat_id, message_id, err, reply_markup=kb.admin_back_keyboard())
            else:
                await client.send_message(chat_id, err, reply_markup=kb.admin_back_keyboard())
            return

        product = await admin_service.create_product_with_photos(
            session=session,
            category_id=data["category_id"],
            title=data["title"],
            description=data["description"],
            price=data["price"],
            photo_urls=data["photo_urls"],
        )

        await fsm_service.clear_state(session, user_obj.id)

    if product is None:
        err = "Ошибка создания товара. Начните заново."
        if message_id:
            await client.edit_message(chat_id, message_id, err, reply_markup=kb.admin_back_keyboard())
        else:
            await client.send_message(chat_id, err, reply_markup=kb.admin_back_keyboard())
        return

    # Показать карточку созданного товара через существующий flow
    await show_admin_product_detail(client, chat_id, user_id, product.id, message_id)


async def admin_add_cancel(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Отменить добавление товара и вернуться к списку категорий."""
    if not _is_admin(user_id):
        await client.send_message(chat_id, NOT_FOUND_TEXT)
        return

    async with async_session_maker() as session:
        user_obj = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        await fsm_service.clear_state(session, user_obj.id)

    await show_admin_categories(client, chat_id, message_id)


def _is_admin(user_id: int | str) -> bool:
    """Проверить, что user_id входит в список администраторов."""
    return str(user_id) in get_settings().admin_ids_list
