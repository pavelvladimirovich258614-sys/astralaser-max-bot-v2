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
