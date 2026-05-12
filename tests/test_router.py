from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.bot import router as router_module
from src.bot.handlers import cart as cart_handler
from src.bot.handlers import catalog as catalog_handler
from src.bot.handlers import order as order_handler
from src.bot.router import UpdateRouter
from src.db.models import Base, CartItem, Product, User
from src.services import catalog_service, fsm_service
from src.services.catalog_service import ProductCardDTO


class FakeClient:
    """Минимальный мок MAXClient для router-тестов."""

    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    async def edit_message(self, chat_id, message_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "edit_message", "chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    async def send_message(self, chat_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "send_message", "chat_id": chat_id, "text": text})

    async def delete_message(self, chat_id, message_id):
        self.calls.append({"method": "delete_message", "chat_id": chat_id, "message_id": message_id})

    async def get_chat_member(self, chat_id, user_id):
        return {"members": [{"user_id": int(user_id)}]}

    async def close(self):
        pass


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


@pytest.fixture(autouse=True)
async def override_catalog_session_maker(monkeypatch, async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(catalog_handler, "async_session_maker", test_session_maker)

    yield

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def override_cart_session_maker(monkeypatch, async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(cart_handler, "async_session_maker", test_session_maker)

    yield

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def override_order_session_maker(monkeypatch, async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(order_handler, "async_session_maker", test_session_maker)

    yield

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
async def override_router_session_maker(monkeypatch, async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(router_module, "async_session_maker", test_session_maker)

    yield

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def router(set_token):
    client = FakeClient()
    return UpdateRouter(client), client


def _make_callback_payload(payload: str, user_id: str = "123") -> dict[str, Any]:
    return {
        "update_type": "message_callback",
        "callback": {
            "callback_id": "cb_1",
            "user": {"user_id": user_id},
            "payload": payload,
        },
        "message": {
            "recipient": {"chat_id": "456"},
            "body": {"mid": "msg_1"},
        },
    }


@pytest.mark.asyncio
async def test_router_callback_catalog(router):
    r, client = router
    await r.process(_make_callback_payload("catalog"))
    assert any("edit_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_menu_catalog(router):
    r, client = router
    await r.process(_make_callback_payload("menu:catalog"))
    assert any("edit_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_home(router):
    r, client = router
    await r.process(_make_callback_payload("home"))
    # Default flag True → delete_message + send_message
    assert any("delete_message" == c["method"] for c in client.calls)
    assert any("send_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_menu_cart(router):
    r, client = router
    await r.process(_make_callback_payload("menu:cart"))
    assert any("Корзина пуста" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_cat_slug(router):
    r, client = router
    await r.process(_make_callback_payload("cat:kole-i-kulony"))
    # show_category вызывает edit_message (даже если товаров нет)
    assert any("edit_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_prod_id(router, monkeypatch):
    r, client = router

    async def fake_get_product_card(session, product_id, photo_index=0):
        return ProductCardDTO(
            title="Test",
            price=100,
            description="Desc",
            photo_url="url",
            photo=None,
            photo_count=1,
            photo_index=0,
            category_slug="test",
        )

    monkeypatch.setattr(catalog_service, "get_product_card", fake_get_product_card)
    await r.process(_make_callback_payload("prod:1"))
    # Default flag True → delete_message + send_message
    assert any("delete_message" == c["method"] for c in client.calls)
    assert any("send_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_photo_id_idx(router, monkeypatch):
    r, client = router

    async def fake_get_product_card(session, product_id, photo_index=0):
        return ProductCardDTO(
            title="Test",
            price=100,
            description="Desc",
            photo_url="url",
            photo=None,
            photo_count=3,
            photo_index=2,
            category_slug="test",
        )

    monkeypatch.setattr(catalog_service, "get_product_card", fake_get_product_card)
    await r.process(_make_callback_payload("photo:1:2"))
    # Default flag True → delete_message + send_message
    assert any("delete_message" == c["method"] for c in client.calls)
    assert any("send_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_add_id(router):
    r, client = router
    await r.process(_make_callback_payload("add:1"))
    edit_calls = [c for c in client.calls if c.get("method") == "edit_message"]
    assert len(edit_calls) == 1
    assert "Товар добавлен в корзину" in edit_calls[0]["text"]
    assert any(b.get("payload") == "prod:1" for row in edit_calls[0].get("reply_markup", []) for b in row)


@pytest.mark.asyncio
async def test_router_callback_qty_inc(router):
    r, client = router
    await r.process(_make_callback_payload("qty:1:inc"))
    assert any(c.get("method") == "edit_message" for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_qty_dec(router):
    r, client = router
    await r.process(_make_callback_payload("qty:1:dec"))
    assert any(c.get("method") == "edit_message" for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_rm(router):
    r, client = router
    await r.process(_make_callback_payload("rm:1"))
    assert any(c.get("method") == "edit_message" for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_clear(router):
    r, client = router
    await r.process(_make_callback_payload("clear"))
    assert any(c.get("method") == "edit_message" for c in client.calls)
    assert any("Очистить корзину" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_clear_yes(router):
    r, client = router
    await r.process(_make_callback_payload("clear:yes"))
    assert any(c.get("method") == "edit_message" for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_clear_no(router):
    r, client = router
    await r.process(_make_callback_payload("clear:no"))
    assert any(c.get("method") == "edit_message" for c in client.calls)


@pytest.mark.asyncio
async def test_router_message_catalog_command(router):
    r, client = router
    payload = {
        "update_type": "message_created",
        "message": {
            "recipient": {"chat_id": "456"},
            "sender": {"user_id": "123"},
            "body": {"text": "/catalog"},
        },
    }
    await r.process(payload)
    assert any("send_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_message_cart_command(router):
    r, client = router
    payload = {
        "update_type": "message_created",
        "message": {
            "recipient": {"chat_id": "456"},
            "sender": {"user_id": "123"},
            "body": {"text": "/cart"},
        },
    }
    await r.process(payload)
    assert any("send_message" == c["method"] for c in client.calls)
    assert any("Корзина пуста" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_checkout(router):
    r, client = router
    await r.process(_make_callback_payload("checkout"))
    assert any(c.get("method") == "edit_message" for c in client.calls)
    assert any("Корзина пуста" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_order_cancel(router):
    r, client = router
    await r.process(_make_callback_payload("order:cancel"))
    assert any(c.get("method") == "edit_message" for c in client.calls)
    assert any("Корзина пуста" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_duplicate_callback_ignored(router):
    r, client = router
    payload = _make_callback_payload("menu:orders")
    await r.process(payload)
    await r.process(payload)
    orders_calls = [c for c in client.calls if c.get("text") == "📦 Мои заказы — скоро."]
    assert len(orders_calls) == 1


@pytest.mark.asyncio
async def test_router_different_payload_not_blocked(router):
    r, client = router
    await r.process(_make_callback_payload("menu:cart"))
    await r.process(_make_callback_payload("menu:orders"))
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_router_duplicate_after_ttl_allowed(router, monkeypatch):
    r, client = router
    monkeypatch.setattr(r, "_dedup_ttl", 0.05)
    call_times = [0.0, 0.03, 0.06]
    idx = 0

    def fake_monotonic():
        nonlocal idx
        if idx < len(call_times):
            t = call_times[idx]
            idx += 1
            return t
        return call_times[-1] + 1.0

    monkeypatch.setattr("src.bot.router.time.monotonic", fake_monotonic)
    payload = _make_callback_payload("menu:orders")
    await r.process(payload)
    await r.process(payload)


def _make_message_payload(text: str, user_id: str = "123", chat_id: str = "456", message_id: str = "msg_1") -> dict[str, Any]:
    return {
        "update_type": "message_created",
        "message": {
            "recipient": {"chat_id": chat_id},
            "sender": {"user_id": user_id},
            "body": {"text": text, "mid": message_id},
        },
    }


@pytest.mark.asyncio
async def test_router_message_in_order_state_goes_to_order_handler(router, async_engine):
    r, client = router
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with test_session_maker() as session:
        user = User(max_user_id="800", full_name="Test")
        session.add(user)
        await session.commit()
        await fsm_service.set_waiting_name(session, user.id)

    await r.process(_make_message_payload("Иван Иванов", user_id="800"))
    assert any("Шаг 2/4" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_message_without_state_keeps_existing_behavior(router):
    r, client = router
    await r.process(_make_message_payload("/start"))
    assert any("edit_message" == c["method"] or "send_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_message_fsm_ignores_regular_command_routing(router, async_engine):
    r, client = router
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with test_session_maker() as session:
        user = User(max_user_id="801", full_name="Test")
        session.add(user)
        await session.commit()
        await fsm_service.set_waiting_name(session, user.id)

    await r.process(_make_message_payload("/catalog", user_id="801"))
    # В FSM-state текст /catalog должен обрабатываться как FSM (имя), а не как команда
    assert any("Пожалуйста, напишите ФИО полностью" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_order_summary_routes_to_order_handler(router, async_engine):
    r, client = router
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with test_session_maker() as session:
        user = User(max_user_id="802", full_name="Test")
        session.add(user)
        await session.flush()
        product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
        session.add(product)
        await session.flush()
        cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
        session.add(cart)
        await session.commit()
        await fsm_service.set_state(
            session, user.id, "order:ready_confirm",
            {"customer_name": "Иван", "phone": "+7", "address": "М", "notes": "N"}
        )

    await r.process(_make_callback_payload("order:summary", user_id="802"))
    assert any("Проверьте заказ" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_order_confirm_routes_to_order_handler(router, async_engine):
    r, client = router
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with test_session_maker() as session:
        user = User(max_user_id="803", full_name="Test")
        session.add(user)
        await session.flush()
        product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
        session.add(product)
        await session.flush()
        cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
        session.add(cart)
        await session.commit()
        await fsm_service.set_state(
            session, user.id, "order:ready_confirm",
            {"customer_name": "Иван", "phone": "+7", "address": "М", "notes": "N"}
        )

    await r.process(_make_callback_payload("order:confirm", user_id="803"))
    assert any("Заказ оформлен" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_menu_contact(router):
    r, client = router
    await r.process(_make_callback_payload("menu:contact"))
    assert any("Связаться с менеджером" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_menu_help(router):
    r, client = router
    await r.process(_make_callback_payload("menu:help"))
    assert any("❓ Помощь" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_command_contact(router):
    r, client = router
    await r.process(_make_message_payload("/contact"))
    assert any("Связаться с менеджером" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_command_help(router):
    r, client = router
    await r.process(_make_message_payload("/help"))
    assert any("❓ Помощь" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_sub_check(router):
    r, client = router
    await r.process(_make_callback_payload("sub:check"))
    assert len(client.calls) >= 1


@pytest.mark.asyncio
async def test_router_command_admin(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    await r.process(_make_message_payload("/admin"))
    assert any("🛠 Админ-панель" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_command_admin_denied(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["4147438"]})())
    await r.process(_make_message_payload("/admin", user_id="99999"))
    assert any("Команда не найдена" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_orders(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    await r.process(_make_callback_payload("admin:orders", user_id="123"))
    assert any("📦 Заказы" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_order_detail(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    # Используем order_id=99999, которого точно нет в БД тестов
    await r.process(_make_callback_payload("admin:order:99999", user_id="123"))
    assert any("Заказ не найден" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_order_status(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    # Используем order_id=99999, которого точно нет в БД тестов
    await r.process(_make_callback_payload("admin:order_status:99999:confirmed", user_id="123"))
    assert any("Заказ не найден" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_order_invalid_payload(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    # Невалидный order_id — не должно вызывать handler
    await r.process(_make_callback_payload("admin:order:abc", user_id="123"))
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_router_callback_admin_order_status_invalid_status(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    await r.process(_make_callback_payload("admin:order_status:1:bogus", user_id="123"))
    assert any("Неизвестный статус" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_exit(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    await r.process(_make_callback_payload("admin:exit", user_id="123"))
    # admin:exit вызывает show_main_menu, которая в тесте делает delete_message + send_message
    assert any("delete_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_back(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    await r.process(_make_callback_payload("admin:back", user_id="123"))
    assert any("🛠 Админ-панель" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_products(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    await r.process(_make_callback_payload("admin:products", user_id="123"))
    assert any("📚 Управление товарами" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_cat_slug(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    await r.process(_make_callback_payload("admin:cat:unknown", user_id="123"))
    assert any("Категория не найдена" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_product_id(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    await r.process(_make_callback_payload("admin:product:99999", user_id="123"))
    assert any("Товар не найден" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_product_toggle(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    await r.process(_make_callback_payload("admin:product_toggle:99999", user_id="123"))
    assert any("Товар не найден" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_product_invalid_payload(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    # Невалидный product_id — не должно вызывать handler
    await r.process(_make_callback_payload("admin:product:abc", user_id="123"))
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_router_bot_started(router):
    r, client = router
    payload = {
        "update_type": "bot_started",
        "chat_id": "30782784",
        "user_id": "235277673",
        "user": {"user_id": "235277673", "name": "Test"},
    }
    await r.process(payload)
    assert any("edit_message" == c["method"] or "send_message" == c["method"] for c in client.calls)
    # Проверяем, что handle_start получил chat_id из payload["chat_id"], а не user_id
    assert any(c.get("chat_id") == "30782784" for c in client.calls)


@pytest.mark.asyncio
async def test_router_bot_started_missing_chat_id(router):
    r, client = router
    payload = {
        "update_type": "bot_started",
        "user": {"user_id": "123", "name": "Test"},
    }
    await r.process(payload)
    # Без chat_id handle_start не должен вызываться
    assert not any("edit_message" == c["method"] or "send_message" == c["method"] for c in client.calls)


# ---------------------------------------------------------------------------
# Admin add product routing tests (F10.4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_callback_admin_add_start(router, monkeypatch):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())
    await r.process(_make_callback_payload("admin:add:start", user_id="123"))
    assert any("Добавление товара" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_add_category(router, monkeypatch, async_engine):
    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with test_session_maker() as session:
        from src.db.models import Category
        cat = Category(title="Test", slug="test", sort_order=1)
        session.add(cat)
        await session.commit()

    monkeypatch.setattr(router_module, "async_session_maker", test_session_maker)
    await r.process(_make_callback_payload(f"admin:add:cat:{cat.id}", user_id="123"))
    assert any("Введите название товара" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_add_photos_done(router, monkeypatch, async_engine):
    from src.bot.handlers import admin as admin_handler

    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with test_session_maker() as session:
        from src.db.models import User
        user = User(max_user_id="123", full_name="Admin")
        session.add(user)
        await session.commit()
        await fsm_service.set_state(
            session,
            user.id,
            fsm_service.ADMIN_ADD_PHOTOS,
            {"category_id": 1, "title": "Test", "price": 100, "description": "Desc", "photo_urls": []},
        )

    monkeypatch.setattr(router_module, "async_session_maker", test_session_maker)
    monkeypatch.setattr(admin_handler, "async_session_maker", test_session_maker)
    await r.process(_make_callback_payload("admin:add:photos_done", user_id="123"))
    assert any("минимум одно фото" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_add_save(router, monkeypatch, async_engine):
    from src.bot.handlers import admin as admin_handler

    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with test_session_maker() as session:
        from src.db.models import Category, User
        cat = Category(title="Test", slug="test", sort_order=1)
        session.add(cat)
        await session.flush()
        user = User(max_user_id="123", full_name="Admin")
        session.add(user)
        await session.flush()
        await fsm_service.set_state(
            session,
            user.id,
            fsm_service.ADMIN_ADD_PREVIEW,
            {
                "category_id": cat.id,
                "category_title": "Test",
                "title": "Product",
                "price": 100,
                "description": "Desc",
                "photo_urls": ["https://example.com/1.jpg"],
            },
        )
        await session.commit()

    monkeypatch.setattr(router_module, "async_session_maker", test_session_maker)
    monkeypatch.setattr(admin_handler, "async_session_maker", test_session_maker)
    await r.process(_make_callback_payload("admin:add:save", user_id="123"))
    assert any("Product" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_add_cancel(router, monkeypatch, async_engine):
    from src.bot.handlers import admin as admin_handler

    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(router_module, "async_session_maker", test_session_maker)
    monkeypatch.setattr(admin_handler, "async_session_maker", test_session_maker)

    await r.process(_make_callback_payload("admin:add:cancel", user_id="123"))
    assert len(client.calls) == 1
    assert client.calls[0]["method"] in ("edit_message", "send_message")


@pytest.mark.asyncio
async def test_router_message_in_admin_state_routes_to_admin_handler(router, monkeypatch, async_engine):
    from src.bot.handlers import admin as admin_handler

    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["900"]})())

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with test_session_maker() as session:
        from src.db.models import User
        user = User(max_user_id="900", full_name="Admin")
        session.add(user)
        await session.commit()
        await fsm_service.set_state(session, user.id, fsm_service.ADMIN_ADD_TITLE, {"category_id": 1})

    monkeypatch.setattr(router_module, "async_session_maker", test_session_maker)
    monkeypatch.setattr(admin_handler, "async_session_maker", test_session_maker)

    await r.process(_make_message_payload("My Product Title", user_id="900"))
    assert any("Введите цену" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_message_in_order_state_still_routes_to_order_handler(router, monkeypatch, async_engine):
    r, client = router
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with test_session_maker() as session:
        from src.db.models import User
        user = User(max_user_id="901", full_name="Test")
        session.add(user)
        await session.commit()
        await fsm_service.set_waiting_name(session, user.id)

    monkeypatch.setattr(router_module, "async_session_maker", test_session_maker)

    await r.process(_make_message_payload("Иван Иванов", user_id="901"))
    assert any("Шаг 2/4" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_admin_broadcast_routes_to_handler(router, monkeypatch, async_engine):
    from src.bot.handlers import admin as admin_handler

    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(router_module, "async_session_maker", test_session_maker)
    monkeypatch.setattr(admin_handler, "async_session_maker", test_session_maker)

    await r.process(_make_callback_payload("admin:broadcast", user_id="123"))
    assert len(client.calls) == 1
    assert "Введите текст сообщения" in client.calls[0].get("text", "")


@pytest.mark.asyncio
async def test_router_callback_admin_broadcast_cancel_routes_to_handler(router, monkeypatch, async_engine):
    from src.bot.handlers import admin as admin_handler

    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(router_module, "async_session_maker", test_session_maker)
    monkeypatch.setattr(admin_handler, "async_session_maker", test_session_maker)

    await r.process(_make_callback_payload("admin:broadcast:cancel", user_id="123"))
    assert len(client.calls) == 1
    assert client.calls[0]["method"] in ("edit_message", "send_message")


@pytest.mark.asyncio
async def test_router_callback_admin_broadcast_send_routes_to_handler(router, monkeypatch, async_engine):
    from src.bot.handlers import admin as admin_handler

    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["123"]})())

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(router_module, "async_session_maker", test_session_maker)
    monkeypatch.setattr(admin_handler, "async_session_maker", test_session_maker)

    await r.process(_make_callback_payload("admin:broadcast:send", user_id="123"))
    assert len(client.calls) == 1
    assert "F10.5.2" in client.calls[0].get("text", "")


@pytest.mark.asyncio
async def test_router_message_in_broadcast_state_routes_to_admin_handler(router, monkeypatch, async_engine):
    from src.bot.handlers import admin as admin_handler

    r, client = router
    monkeypatch.setattr("src.bot.handlers.admin.get_settings", lambda: type("S", (), {"admin_ids_list": ["900"]})())

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    async with test_session_maker() as session:
        from src.db.models import User
        user = User(max_user_id="900", full_name="Admin")
        session.add(user)
        await session.commit()
        await fsm_service.set_state(session, user.id, fsm_service.ADMIN_BROADCAST_TEXT, {})

    monkeypatch.setattr(router_module, "async_session_maker", test_session_maker)
    monkeypatch.setattr(admin_handler, "async_session_maker", test_session_maker)

    await r.process(_make_message_payload("Hello broadcast", user_id="900"))
    assert any("Предпросмотр рассылки" in c.get("text", "") for c in client.calls)
