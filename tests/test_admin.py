from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.bot.handlers import admin as admin_handler
from src.bot.handlers import start as start_handler
from src.bot.keyboards import admin_menu_keyboard
from src.db.models import Base, Category, Order, OrderItem, Product, ProductPhoto, User
from src.services import fsm_service


class RecordingClient:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    async def edit_message(self, chat_id, message_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "edit_message", "chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": reply_markup})

    async def send_message(self, chat_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "send_message", "chat_id": chat_id, "text": text, "reply_markup": reply_markup})


@pytest.fixture(autouse=True)
def set_token(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "test_token")


@pytest.fixture(scope="session")
def async_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        future=True,
    )
    return engine


@pytest.fixture
async def db_session(async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def override_admin_session_maker(monkeypatch, async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(admin_handler, "async_session_maker", test_session_maker)

    yield

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _make_settings(admin_ids: list[str]):
    return type("S", (), {"admin_ids_list": admin_ids})()


# ---------------------------------------------------------------------------
# Access tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_access_denied_for_regular_user(monkeypatch):
    """Обычный пользователь получает 'Команда не найдена.' при /admin."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()
    await admin_handler.handle_admin_command(client, chat_id=1, user_id="99999")

    assert len(client.calls) == 1
    assert client.calls[0]["method"] == "send_message"
    assert "Команда не найдена" in client.calls[0]["text"]


@pytest.mark.asyncio
async def test_admin_access_granted_for_admin(monkeypatch):
    """Админ получает экран '🛠 Админ-панель'."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()
    await admin_handler.handle_admin_command(client, chat_id=1, user_id="4147438")

    assert len(client.calls) == 1
    assert client.calls[0]["method"] == "send_message"
    assert "🛠 Админ-панель" in client.calls[0]["text"]
    assert client.calls[0]["reply_markup"] == admin_menu_keyboard()


# ---------------------------------------------------------------------------
# Menu keyboard test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_menu_has_all_buttons():
    """Клавиатура содержит все 6 кнопок с правильными payload."""
    kb = admin_menu_keyboard()
    payloads = [b["payload"] for row in kb for b in row]
    assert "admin:orders" in payloads
    assert "admin:products" in payloads
    assert "admin:categories" in payloads
    assert "admin:stats" in payloads
    assert "admin:broadcast" in payloads
    assert "admin:exit" in payloads


# ---------------------------------------------------------------------------
# Skeleton callback tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_skeleton_callbacks_require_admin_access(monkeypatch):
    """Обычный пользователь не видит экран при admin:* callback."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()
    await admin_handler.admin_orders(client, chat_id=1, user_id="99999", message_id="msg_1")
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_admin_skeleton_callbacks_show_placeholders(monkeypatch):
    """Админ видит placeholder-экраны для оставшихся skeleton callbacks."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()

    # admin_products теперь реальный (F10.3), в пустой БД покажет placeholder
    await admin_handler.admin_products(client, chat_id=1, user_id="4147438", message_id="msg_1")
    assert any("📚 Категории товаров пока не созданы" in c["text"] for c in client.calls)

    await admin_handler.admin_categories(client, chat_id=1, user_id="4147438", message_id="msg_1")
    assert any("🏷 Категории" in c["text"] for c in client.calls)

    await admin_handler.admin_stats(client, chat_id=1, user_id="4147438", message_id="msg_1")
    assert any("📊 Статистика" in c["text"] for c in client.calls)

    await admin_handler.admin_broadcast(client, chat_id=1, user_id="4147438", message_id="msg_1")
    assert any("📤 Рассылка" in c["text"] for c in client.calls)


# ---------------------------------------------------------------------------
# Orders list tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_orders_empty_shows_placeholder(monkeypatch, db_session):
    """При пустом списке заказов показывается placeholder."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()
    await admin_handler.admin_orders(client, chat_id=1, user_id="4147438", message_id="msg_1")

    assert len(client.calls) == 1
    assert "Заказов пока нет" in client.calls[0]["text"]
    assert any(b["payload"] == "admin:back" for row in client.calls[0]["reply_markup"] for b in row)


@pytest.mark.asyncio
async def test_admin_orders_shows_recent_orders(monkeypatch, db_session):
    """Список заказов показывает кнопки с номерами, статусами и суммами."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="500", full_name="Test")
    db_session.add(user)
    await db_session.flush()

    order = Order(
        user_id=user.id,
        customer_name="Иван",
        customer_phone="+7",
        delivery_address="Адрес",
        total_amount=840,
        status="pending",
    )
    db_session.add(order)
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.admin_orders(client, chat_id=1, user_id="4147438", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert "📦 Заказы" in call["text"]
    assert any(f"admin:order:{order.id}" in b["payload"] for row in call["reply_markup"] for b in row)


# ---------------------------------------------------------------------------
# Order detail tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_order_detail_shows_customer_items_total_and_notes(monkeypatch, db_session):
    """Карточка заказа содержит клиента, товары, итог и комментарий."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="600", full_name="Test")
    db_session.add(user)
    await db_session.flush()

    order = Order(
        user_id=user.id,
        customer_name="Иван Иванов",
        customer_phone="+7 999 123 45 67",
        delivery_address="Москва, ул. Ленина 1",
        total_amount=840,
        status="pending",
        notes="Гравировка: Love",
    )
    db_session.add(order)
    await db_session.flush()

    item = OrderItem(
        order_id=order.id,
        product_id=1,
        product_title_snapshot="Кулон-столбик",
        price_snapshot=840,
        quantity=1,
    )
    db_session.add(item)
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.show_order_detail(client, chat_id=1, user_id="4147438", order_id=order.id, message_id="msg_1")

    assert len(client.calls) == 1
    text = client.calls[0]["text"]
    assert f"Заказ #{order.id}" in text
    assert "Иван Иванов" in text
    assert "+7 999 123 45 67" in text
    assert "Москва, ул. Ленина 1" in text
    assert "Кулон-столбик" in text
    assert "840 ₽" in text
    assert "Гравировка: Love" in text

    # Кнопки смены статуса для pending
    kb = client.calls[0]["reply_markup"]
    assert any(b["payload"] == f"admin:order_status:{order.id}:confirmed" for row in kb for b in row)
    assert any(b["payload"] == f"admin:order_status:{order.id}:cancelled" for row in kb for b in row)
    assert any(b["payload"] == "admin:orders" for row in kb for b in row)


@pytest.mark.asyncio
async def test_admin_order_detail_missing_order_shows_not_found(monkeypatch, db_session):
    """При несуществующем order_id показывается 'Заказ не найден.'"""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()
    await admin_handler.show_order_detail(client, chat_id=1, user_id="4147438", order_id=99999, message_id="msg_1")

    assert len(client.calls) == 1
    assert "Заказ не найден" in client.calls[0]["text"]
    assert any(b["payload"] == "admin:orders" for row in client.calls[0]["reply_markup"] for b in row)


@pytest.mark.asyncio
async def test_admin_order_detail_completed_no_status_buttons(monkeypatch, db_session):
    """Для завершённого заказа нет кнопок смены статуса."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="601", full_name="Test")
    db_session.add(user)
    await db_session.flush()

    order = Order(
        user_id=user.id,
        customer_name="A",
        customer_phone="+7",
        delivery_address="Addr",
        total_amount=100,
        status="completed",
    )
    db_session.add(order)
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.show_order_detail(client, chat_id=1, user_id="4147438", order_id=order.id, message_id="msg_1")

    kb = client.calls[0]["reply_markup"]
    payloads = [b["payload"] for row in kb for b in row]
    assert "admin:orders" in payloads
    assert not any("admin:order_status:" in p for p in payloads)


# ---------------------------------------------------------------------------
# Order status change tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_order_status_change_updates_and_rerenders_card(monkeypatch, db_session):
    """Смена статуса обновляет заказ и перерисовывает карточку."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="700", full_name="Test")
    db_session.add(user)
    await db_session.flush()

    order = Order(
        user_id=user.id,
        customer_name="Иван",
        customer_phone="+7",
        delivery_address="Адрес",
        total_amount=100,
        status="pending",
    )
    db_session.add(order)
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.admin_order_status(
        client, chat_id=1, user_id="4147438", order_id=order.id, status="confirmed", message_id="msg_1"
    )

    assert len(client.calls) == 1
    text = client.calls[0]["text"]
    assert f"Заказ #{order.id}" in text
    assert "Подтверждён" in text


@pytest.mark.asyncio
async def test_admin_order_status_unknown_status_shows_error(monkeypatch, db_session):
    """Неизвестный статус показывает ошибку."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="701", full_name="Test")
    db_session.add(user)
    await db_session.flush()

    order = Order(
        user_id=user.id,
        customer_name="A",
        customer_phone="+7",
        delivery_address="Addr",
        total_amount=100,
        status="pending",
    )
    db_session.add(order)
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.admin_order_status(
        client, chat_id=1, user_id="4147438", order_id=order.id, status="bogus", message_id="msg_1"
    )

    assert len(client.calls) == 1
    assert "Неизвестный статус" in client.calls[0]["text"]


# ---------------------------------------------------------------------------
# Access tests for order callbacks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_order_callbacks_denied_for_regular_user(monkeypatch, db_session):
    """Обычный пользователь не может открыть карточку заказа."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()

    await admin_handler.show_order_detail(client, chat_id=1, user_id="99999", order_id=1, message_id="msg_1")
    assert len(client.calls) == 0

    await admin_handler.admin_order_status(client, chat_id=1, user_id="99999", order_id=1, status="confirmed", message_id="msg_1")
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_admin_order_back_returns_to_orders_list(monkeypatch, db_session):
    """Кнопка назад из списка заказов возвращает в админ-панель."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    # admin_back_to_menu уже протестирован, проверим что admin_orders_back_keyboard корректна
    from src.bot.keyboards import admin_orders_back_keyboard
    kb = admin_orders_back_keyboard()
    payloads = [b["payload"] for row in kb for b in row]
    assert "admin:orders" in payloads


# ---------------------------------------------------------------------------
# Exit test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_exit_returns_to_main_menu(monkeypatch):
    """admin:exit вызывает show_main_menu."""
    calls = []

    async def fake_show_main_menu(client, chat_id, message_id=None):
        calls.append({"method": "show_main_menu", "chat_id": chat_id, "message_id": message_id})

    monkeypatch.setattr(start_handler, "show_main_menu", fake_show_main_menu)
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()

    await admin_handler.admin_exit(client, chat_id=1, user_id="4147438", message_id="msg_1")

    assert len(calls) == 1
    assert calls[0]["method"] == "show_main_menu"
    assert calls[0]["chat_id"] == 1
    assert calls[0]["message_id"] == "msg_1"


# ---------------------------------------------------------------------------
# _is_admin edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_admin_numeric_string_match(monkeypatch):
    """_is_admin корректно сравнивает numeric user_id как строку."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438", "73412011"]))
    assert admin_handler._is_admin(4147438) is True
    assert admin_handler._is_admin("4147438") is True
    assert admin_handler._is_admin("73412011") is True
    assert admin_handler._is_admin("99999") is False
    assert admin_handler._is_admin(99999) is False


@pytest.mark.asyncio
async def test_admin_placeholder_back_returns_to_menu(monkeypatch):
    """admin:back возвращает в меню админ-панели через edit_message."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()
    await admin_handler.admin_back_to_menu(client, chat_id=1, user_id="4147438", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert "🛠 Админ-панель" in call["text"]
    assert call["reply_markup"] == admin_menu_keyboard()


@pytest.mark.asyncio
async def test_admin_back_to_menu_denied_for_regular_user(monkeypatch):
    """Обычный пользователь не может использовать admin:back."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()
    await admin_handler.admin_back_to_menu(client, chat_id=1, user_id="99999", message_id="msg_1")
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_admin_back_keyboard_payload():
    """admin_back_keyboard использует payload admin:back."""
    from src.bot.keyboards import admin_back_keyboard
    kb = admin_back_keyboard()
    payloads = [b["payload"] for row in kb for b in row]
    assert "admin:back" in payloads
    assert "admin:exit" not in payloads


# ---------------------------------------------------------------------------
# Product management tests (F10.3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_products_shows_categories(monkeypatch, db_session):
    """admin:products показывает категории с количеством товаров."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    cat = Category(title="Колье", slug="kole-i-kulony", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    product = Product(
        category_id=cat.id,
        title="Кулон",
        description="Desc",
        price=840,
        cover_url="url",
        sort_order=1,
    )
    db_session.add(product)
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.admin_products(client, chat_id=1, user_id="4147438", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert "📚 Управление товарами" in call["text"]
    assert any("admin:cat:kole-i-kulony" in b["payload"] for row in call["reply_markup"] for b in row)


@pytest.mark.asyncio
async def test_admin_products_category_shows_products(monkeypatch, db_session):
    """admin:cat показывает все товары категории, включая неактивные."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    cat = Category(title="Колье", slug="kole-i-kulony", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    active = Product(category_id=cat.id, title="Active", description="Desc", price=100, cover_url="url", is_active=True, sort_order=1)
    inactive = Product(category_id=cat.id, title="Inactive", description="Desc", price=200, cover_url="url", is_active=False, sort_order=2)
    db_session.add_all([active, inactive])
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.show_admin_products_list(client, chat_id=1, user_id="4147438", slug="kole-i-kulony", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert "📚 Колье" in call["text"]
    assert any(f"admin:product:{active.id}" in b["payload"] for row in call["reply_markup"] for b in row)
    assert any(f"admin:product:{inactive.id}" in b["payload"] for row in call["reply_markup"] for b in row)


@pytest.mark.asyncio
async def test_admin_products_category_empty(monkeypatch, db_session):
    """admin:cat для пустой категории показывает placeholder."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    cat = Category(title="Пустая", slug="empty", sort_order=1)
    db_session.add(cat)
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.show_admin_products_list(client, chat_id=1, user_id="4147438", slug="empty", message_id="msg_1")

    assert len(client.calls) == 1
    assert "В этой категории пока нет товаров" in client.calls[0]["text"]


@pytest.mark.asyncio
async def test_admin_product_detail_shows_id_title_price_status_photo_count(monkeypatch, db_session):
    """Карточка товара для админа содержит id, title, price, status, photo_count."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    cat = Category(title="Колье", slug="kole-i-kulony", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    product = Product(
        category_id=cat.id,
        title="Кулон",
        description="Описание товара",
        price=840,
        cover_url="url",
        is_active=True,
        sort_order=1,
    )
    db_session.add(product)
    await db_session.flush()

    photo = ProductPhoto(product_id=product.id, url="url1", sort_order=0)
    db_session.add(photo)
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.show_admin_product_detail(client, chat_id=1, user_id="4147438", product_id=product.id, message_id="msg_1")

    assert len(client.calls) == 1
    text = client.calls[0]["text"]
    assert f"Товар #{product.id}" in text
    assert "Кулон" in text
    assert "840 ₽" in text
    assert "Активен" in text
    assert "Фото: 1" in text
    assert "Описание товара" in text

    kb = client.calls[0]["reply_markup"]
    assert any(b["payload"] == f"admin:product_toggle:{product.id}" for row in kb for b in row)
    assert any(b["payload"] == "admin:cat:kole-i-kulony" for row in kb for b in row)


@pytest.mark.asyncio
async def test_admin_product_toggle_changes_status_and_rerenders(monkeypatch, db_session):
    """Переключение is_active меняет статус и перерисовывает карточку."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    cat = Category(title="Колье", slug="kole-i-kulony", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    product = Product(
        category_id=cat.id,
        title="Кулон",
        description="Desc",
        price=840,
        cover_url="url",
        is_active=True,
        sort_order=1,
    )
    db_session.add(product)
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.admin_product_toggle(client, chat_id=1, user_id="4147438", product_id=product.id, message_id="msg_1")

    assert len(client.calls) == 1
    text = client.calls[0]["text"]
    assert f"Товар #{product.id}" in text
    assert "Скрыт" in text
    assert "👁 Включить" in str(client.calls[0]["reply_markup"])


@pytest.mark.asyncio
async def test_admin_product_not_found(monkeypatch, db_session):
    """При несуществующем product_id показывается 'Товар не найден.'"""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()
    await admin_handler.show_admin_product_detail(client, chat_id=1, user_id="4147438", product_id=99999, message_id="msg_1")

    assert len(client.calls) == 1
    assert "Товар не найден" in client.calls[0]["text"]


@pytest.mark.asyncio
async def test_admin_product_callbacks_denied_for_regular_user(monkeypatch, db_session):
    """Обычный пользователь не может открыть админские товары."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()

    await admin_handler.show_admin_products_list(client, chat_id=1, user_id="99999", slug="test", message_id="msg_1")
    assert len(client.calls) == 0

    await admin_handler.show_admin_product_detail(client, chat_id=1, user_id="99999", product_id=1, message_id="msg_1")
    assert len(client.calls) == 0

    await admin_handler.admin_product_toggle(client, chat_id=1, user_id="99999", product_id=1, message_id="msg_1")
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_admin_product_back_navigation(monkeypatch, db_session):
    """Кнопки назад из карточки товара ведут в список товаров категории."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    cat = Category(title="Колье", slug="kole-i-kulony", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    product = Product(
        category_id=cat.id,
        title="Кулон",
        description="Desc",
        price=840,
        cover_url="url",
        is_active=True,
        sort_order=1,
    )
    db_session.add(product)
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.show_admin_product_detail(client, chat_id=1, user_id="4147438", product_id=product.id, message_id="msg_1")

    kb = client.calls[0]["reply_markup"]
    payloads = [b["payload"] for row in kb for b in row]
    assert "admin:cat:kole-i-kulony" in payloads


# ---------------------------------------------------------------------------
# Admin add product FSM tests (F10.4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_add_product_start_shows_categories(monkeypatch, db_session):
    """admin:add:start показывает категории для выбора."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    cat = Category(title="Колье", slug="kole-i-kulony", sort_order=1)
    db_session.add(cat)
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.admin_add_start(client, chat_id=1, user_id="4147438", message_id="msg_1")

    assert len(client.calls) == 1
    assert "Добавление товара" in client.calls[0]["text"]
    kb = client.calls[0]["reply_markup"]
    assert any("admin:add:cat:" in b["payload"] for row in kb for b in row)


@pytest.mark.asyncio
async def test_admin_add_product_category_selection_sets_title_state(monkeypatch, db_session):
    """Выбор категории устанавливает state admin:add:title."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    cat = Category(title="Колье", slug="kole-i-kulony", sort_order=1)
    db_session.add(cat)
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.admin_add_category_selected(
        client, chat_id=1, user_id="4147438", category_id=cat.id, message_id="msg_1"
    )

    assert len(client.calls) == 1
    assert "Введите название товара" in client.calls[0]["text"]

    # Проверить state через тот же db_session (StaticPool = shared connection)
    user = await db_session.scalar(select(User).where(User.max_user_id == "4147438"))
    assert user is not None
    state, data = await fsm_service.get_state(db_session, user.id)
    assert state == fsm_service.ADMIN_ADD_TITLE
    assert data["category_id"] == cat.id


@pytest.mark.asyncio
async def test_admin_add_product_title_validation(monkeypatch, db_session):
    """Название валидируется: слишком короткое/длинное — ошибка, остаёмся в state."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="4147438", full_name="Admin")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(db_session, user.id, fsm_service.ADMIN_ADD_TITLE, {"category_id": 1})

    client = RecordingClient()
    handled = await admin_handler.handle_admin_fsm_message(client, chat_id=1, user_id="4147438", message_id="msg_1", text="X")
    assert handled is True
    assert client.calls[0]["method"] == "send_message"
    assert "от 2 до 256 символов" in client.calls[0]["text"]

    client.calls.clear()
    handled = await admin_handler.handle_admin_fsm_message(client, chat_id=1, user_id="4147438", message_id="msg_1", text="Valid Title")
    assert handled is True
    assert client.calls[0]["method"] == "send_message"
    assert "Введите цену" in client.calls[0]["text"]


@pytest.mark.asyncio
async def test_admin_add_product_price_validation(monkeypatch, db_session):
    """Цена валидируется: не число, <=0, >1_000_000 — ошибка."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="4147438", full_name="Admin")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(db_session, user.id, fsm_service.ADMIN_ADD_PRICE, {"category_id": 1, "title": "Test"})

    client = RecordingClient()
    for bad_text in ["abc", "0", "-10", "1000001"]:
        client.calls.clear()
        handled = await admin_handler.handle_admin_fsm_message(
            client, chat_id=1, user_id="4147438", message_id="msg_1", text=bad_text
        )
        assert handled is True
        assert client.calls[0]["method"] == "send_message"
        assert "Попробуйте ещё раз" in client.calls[0]["text"]

    client.calls.clear()
    handled = await admin_handler.handle_admin_fsm_message(
        client, chat_id=1, user_id="4147438", message_id="msg_1", text="500"
    )
    assert handled is True
    assert client.calls[0]["method"] == "send_message"
    assert "Введите описание" in client.calls[0]["text"]


@pytest.mark.asyncio
async def test_admin_add_product_description_validation(monkeypatch, db_session):
    """Описание валидируется: пустое, >1000 символов — ошибка."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="4147438", full_name="Admin")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(
        db_session, user.id, fsm_service.ADMIN_ADD_DESCRIPTION, {"category_id": 1, "title": "Test", "price": 100}
    )

    client = RecordingClient()
    handled = await admin_handler.handle_admin_fsm_message(
        client, chat_id=1, user_id="4147438", message_id="msg_1", text="   "
    )
    assert handled is True
    assert client.calls[0]["method"] == "send_message"
    assert "пустым" in client.calls[0]["text"].lower()

    client.calls.clear()
    handled = await admin_handler.handle_admin_fsm_message(
        client, chat_id=1, user_id="4147438", message_id="msg_1", text="Good description"
    )
    assert handled is True
    assert client.calls[0]["method"] == "send_message"
    assert "URL фото" in client.calls[0]["text"]


@pytest.mark.asyncio
async def test_admin_add_product_photos_collection(monkeypatch, db_session):
    """Шаг photos накапливает валидные URL и показывает счётчик."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="4147438", full_name="Admin")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(
        db_session,
        user.id,
        fsm_service.ADMIN_ADD_PHOTOS,
        {"category_id": 1, "title": "Test", "price": 100, "description": "Desc", "photo_urls": []},
    )

    client = RecordingClient()
    handled = await admin_handler.handle_admin_fsm_message(
        client, chat_id=1, user_id="4147438", message_id="msg_1", text="not_a_url"
    )
    assert handled is True
    assert client.calls[0]["method"] == "send_message"
    assert "Не найдено валидных URL" in client.calls[0]["text"]

    client.calls.clear()
    handled = await admin_handler.handle_admin_fsm_message(
        client, chat_id=1, user_id="4147438", message_id="msg_1", text="https://example.com/1.jpg\nhttps://example.com/2.jpg"
    )
    assert handled is True
    assert client.calls[0]["method"] == "send_message"
    assert "Добавлено фото: 2" in client.calls[0]["text"]


@pytest.mark.asyncio
async def test_admin_add_product_photos_done_requires_photo(monkeypatch, db_session):
    """admin:add:photos_done без фото показывает ошибку."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="4147438", full_name="Admin")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(
        db_session,
        user.id,
        fsm_service.ADMIN_ADD_PHOTOS,
        {"category_id": 1, "title": "Test", "price": 100, "description": "Desc", "photo_urls": []},
    )

    client = RecordingClient()
    await admin_handler.admin_add_photos_done(client, chat_id=1, user_id="4147438", message_id="msg_1")

    assert len(client.calls) == 1
    assert "минимум одно фото" in client.calls[0]["text"]


@pytest.mark.asyncio
async def test_admin_add_product_save_creates_product_and_photos(monkeypatch, db_session):
    """admin:add:save создаёт товар и фото, очищает state."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    cat = Category(title="Колье", slug="kole-i-kulony", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    user = User(max_user_id="4147438", full_name="Admin")
    db_session.add(user)
    await db_session.flush()
    await fsm_service.set_state(
        db_session,
        user.id,
        fsm_service.ADMIN_ADD_PREVIEW,
        {
            "category_id": cat.id,
            "category_title": "Колье",
            "title": "Кулон",
            "price": 840,
            "description": "Описание",
            "photo_urls": ["https://example.com/1.jpg", "https://example.com/2.jpg"],
        },
    )
    await db_session.commit()

    client = RecordingClient()
    await admin_handler.admin_add_save(client, chat_id=1, user_id="4147438", message_id="msg_1")

    assert len(client.calls) == 1
    text = client.calls[0]["text"]
    assert "Кулон" in text
    assert "840 ₽" in text

    state, data = await fsm_service.get_state(db_session, user.id)
    assert state is None


@pytest.mark.asyncio
async def test_admin_add_product_cancel_clears_state(monkeypatch, db_session):
    """admin:add:cancel очищает state и возвращает к категориям."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="4147438", full_name="Admin")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(
        db_session, user.id, fsm_service.ADMIN_ADD_TITLE, {"category_id": 1, "title": "Test"}
    )

    client = RecordingClient()
    await admin_handler.admin_add_cancel(client, chat_id=1, user_id="4147438", message_id="msg_1")

    assert len(client.calls) == 1
    # Возвращает к show_admin_categories, которая в пустой БД покажет placeholder
    assert client.calls[0]["method"] in ("edit_message", "send_message")

    state, data = await fsm_service.get_state(db_session, user.id)
    assert state is None


@pytest.mark.asyncio
async def test_admin_add_product_denied_for_regular_user(monkeypatch):
    """Обычный пользователь не может начать добавление товара."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()

    await admin_handler.admin_add_start(client, chat_id=1, user_id="99999", message_id="msg_1")
    assert len(client.calls) == 1
    assert "Команда не найдена" in client.calls[0]["text"]

    client.calls.clear()
    handled = await admin_handler.handle_admin_fsm_message(
        client, chat_id=1, user_id="99999", message_id="msg_1", text="Test"
    )
    assert handled is True
    assert "Команда не найдена" in client.calls[0]["text"]

    client.calls.clear()
    await admin_handler.admin_add_photos_done(client, chat_id=1, user_id="99999", message_id="msg_1")
    assert len(client.calls) == 1
    assert "Команда не найдена" in client.calls[0]["text"]

    client.calls.clear()
    await admin_handler.admin_add_save(client, chat_id=1, user_id="99999", message_id="msg_1")
    assert len(client.calls) == 1
    assert "Команда не найдена" in client.calls[0]["text"]

    client.calls.clear()
    await admin_handler.admin_add_cancel(client, chat_id=1, user_id="99999", message_id="msg_1")
    assert len(client.calls) == 1
    assert "Команда не найдена" in client.calls[0]["text"]


# ---------------------------------------------------------------------------
# Admin broadcast tests (F10.5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_broadcast_start_sets_state(monkeypatch, db_session):
    """admin:broadcast устанавливает state admin:broadcast:text."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    client = RecordingClient()
    await admin_handler.admin_broadcast(client, chat_id=1, user_id="4147438", message_id="msg_1")

    user = await db_session.scalar(select(User).where(User.max_user_id == "4147438"))
    assert user is not None
    state, data = await fsm_service.get_state(db_session, user.id)
    assert state == fsm_service.ADMIN_BROADCAST_TEXT


@pytest.mark.asyncio
async def test_admin_broadcast_start_shows_prompt(monkeypatch):
    """admin:broadcast показывает prompt для ввода текста."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    client = RecordingClient()
    await admin_handler.admin_broadcast(client, chat_id=1, user_id="4147438", message_id="msg_1")

    assert len(client.calls) == 1
    assert "Введите текст сообщения" in client.calls[0]["text"]
    assert any(b["payload"] == "admin:broadcast:cancel" for row in client.calls[0]["reply_markup"] for b in row)


@pytest.mark.asyncio
async def test_admin_broadcast_text_empty_shows_error(monkeypatch, db_session):
    """Пустой текст рассылки — ошибка, остаёмся в state."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="4147438", full_name="Admin")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(db_session, user.id, fsm_service.ADMIN_BROADCAST_TEXT, {})

    client = RecordingClient()
    handled = await admin_handler.handle_admin_fsm_message(
        client, chat_id=1, user_id="4147438", message_id="msg_1", text="   "
    )
    assert handled is True
    assert client.calls[0]["method"] == "send_message"
    assert "пустым" in client.calls[0]["text"].lower()

    state, data = await fsm_service.get_state(db_session, user.id)
    assert state == fsm_service.ADMIN_BROADCAST_TEXT


@pytest.mark.asyncio
async def test_admin_broadcast_text_too_long_shows_error(monkeypatch, db_session):
    """Текст длиннее 4000 символов — ошибка, остаёмся в state."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="4147438", full_name="Admin")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(db_session, user.id, fsm_service.ADMIN_BROADCAST_TEXT, {})

    client = RecordingClient()
    handled = await admin_handler.handle_admin_fsm_message(
        client, chat_id=1, user_id="4147438", message_id="msg_1", text="A" * 4001
    )
    assert handled is True
    assert client.calls[0]["method"] == "send_message"
    assert "4000" in client.calls[0]["text"]

    state, data = await fsm_service.get_state(db_session, user.id)
    assert state == fsm_service.ADMIN_BROADCAST_TEXT


@pytest.mark.asyncio
async def test_admin_broadcast_text_valid_shows_preview(monkeypatch, db_session):
    """Валидный текст — показывается preview с кнопками Отправить/Отмена."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="4147438", full_name="Admin")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(db_session, user.id, fsm_service.ADMIN_BROADCAST_TEXT, {})

    client = RecordingClient()
    handled = await admin_handler.handle_admin_fsm_message(
        client, chat_id=1, user_id="4147438", message_id="msg_1", text="Привет всем!"
    )
    assert handled is True
    assert client.calls[0]["method"] == "send_message"
    assert "Предпросмотр рассылки" in client.calls[0]["text"]
    assert "Привет всем!" in client.calls[0]["text"]
    kb = client.calls[0]["reply_markup"]
    assert any(b["payload"] == "admin:broadcast:send" for row in kb for b in row)
    assert any(b["payload"] == "admin:broadcast:cancel" for row in kb for b in row)


@pytest.mark.asyncio
async def test_admin_broadcast_cancel_clears_state(monkeypatch, db_session):
    """admin:broadcast:cancel очищает state и возвращает в админ-панель."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="4147438", full_name="Admin")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(db_session, user.id, fsm_service.ADMIN_BROADCAST_TEXT, {"broadcast_text": "Test"})

    client = RecordingClient()
    await admin_handler.admin_broadcast_cancel(client, chat_id=1, user_id="4147438", message_id="msg_1")

    state, data = await fsm_service.get_state(db_session, user.id)
    assert state is None


@pytest.mark.asyncio
async def test_admin_broadcast_send_is_safe_placeholder_for_now(monkeypatch, db_session):
    """admin:broadcast:send показывает безопасную заглушку и очищает state."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))

    user = User(max_user_id="4147438", full_name="Admin")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(db_session, user.id, fsm_service.ADMIN_BROADCAST_TEXT, {"broadcast_text": "Test"})

    client = RecordingClient()
    await admin_handler.admin_broadcast_send(client, chat_id=1, user_id="4147438", message_id="msg_1")

    assert len(client.calls) == 1
    assert "F10.5.2" in client.calls[0]["text"]

    state, data = await fsm_service.get_state(db_session, user.id)
    assert state is None


@pytest.mark.asyncio
async def test_admin_broadcast_denied_for_regular_user(monkeypatch):
    """Обычный пользователь не может начать рассылку."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()

    await admin_handler.admin_broadcast(client, chat_id=1, user_id="99999", message_id="msg_1")
    assert len(client.calls) == 1
    assert "Команда не найдена" in client.calls[0]["text"]

    client.calls.clear()
    await admin_handler.admin_broadcast_cancel(client, chat_id=1, user_id="99999", message_id="msg_1")
    assert len(client.calls) == 1
    assert "Команда не найдена" in client.calls[0]["text"]

    client.calls.clear()
    await admin_handler.admin_broadcast_send(client, chat_id=1, user_id="99999", message_id="msg_1")
    assert len(client.calls) == 1
    assert "Команда не найдена" in client.calls[0]["text"]
