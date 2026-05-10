from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.bot.handlers import cart as cart_handler
from src.bot.handlers import order as order_handler
from src.bot.handlers import subscription as subscription_handler
from src.db.models import Base, CartItem, Product, User
from src.services import subscription_service


class FakeClient:
    def __init__(self, member_response: dict[str, Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._member_response = member_response

    async def get_chat_member(self, chat_id, user_id):
        return self._member_response

    async def edit_message(self, chat_id, message_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "edit_message", "chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    async def send_message(self, chat_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "send_message", "chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    async def delete_message(self, chat_id, message_id):
        self.calls.append({"method": "delete_message", "chat_id": chat_id, "message_id": message_id})
        return True


@pytest.fixture(scope="session")
def async_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        future=True,
    )
    return engine


@pytest.fixture(autouse=True)
def set_token(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "test_token")


@pytest.fixture(autouse=True)
async def override_session_makers(monkeypatch, async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(order_handler, "async_session_maker", test_session_maker)
    monkeypatch.setattr(cart_handler, "async_session_maker", test_session_maker)

    yield

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _make_user_with_cart(async_engine, max_user_id="900"):
    async def _create():
        sm = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
        async with sm() as session:
            user = User(max_user_id=max_user_id, full_name="Test Sub")
            session.add(user)
            await session.flush()
            product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
            session.add(product)
            await session.flush()
            cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
            session.add(cart)
            await session.commit()
            return user.id
    return _create()


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_member_status_member():
    assert subscription_service.is_member_status({"status": "member"}) is True


@pytest.mark.asyncio
async def test_is_member_status_admin():
    assert subscription_service.is_member_status({"status": "administrator"}) is True


@pytest.mark.asyncio
async def test_is_member_status_creator():
    assert subscription_service.is_member_status({"status": "creator"}) is True


@pytest.mark.asyncio
async def test_is_member_status_owner():
    assert subscription_service.is_member_status({"status": "owner"}) is True


@pytest.mark.asyncio
async def test_is_member_status_left():
    assert subscription_service.is_member_status({"status": "left"}) is False


@pytest.mark.asyncio
async def test_is_member_status_kicked():
    assert subscription_service.is_member_status({"status": "kicked"}) is False


@pytest.mark.asyncio
async def test_is_member_status_none():
    assert subscription_service.is_member_status(None) is False


@pytest.mark.asyncio
async def test_is_member_status_empty_dict():
    assert subscription_service.is_member_status({}) is False


@pytest.mark.asyncio
async def test_is_member_status_unknown_status():
    assert subscription_service.is_member_status({"status": "something_else"}) is False


# ---------------------------------------------------------------------------
# Handler tests: gate disabled
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscription_gate_disabled_starts_checkout(async_engine, monkeypatch):
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL", "")
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL_URL", "")

    await _make_user_with_cart(async_engine, "901")
    client = FakeClient()
    await order_handler.start_checkout(client, chat_id=1, user_id="901", message_id="msg_1")

    assert len(client.calls) == 1
    assert "Шаг 1/4" in client.calls[0]["text"]


# ---------------------------------------------------------------------------
# Handler tests: subscribed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscription_subscribed_starts_checkout(async_engine, monkeypatch):
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL", "@test_channel")
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL_URL", "https://max.ru/channel")

    await _make_user_with_cart(async_engine, "902")
    client = FakeClient(member_response={"status": "member"})
    await order_handler.start_checkout(client, chat_id=1, user_id="902", message_id="msg_1")

    assert len(client.calls) == 1
    assert "Шаг 1/4" in client.calls[0]["text"]


@pytest.mark.asyncio
async def test_subscription_admin_status_starts_checkout(async_engine, monkeypatch):
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL", "@test_channel")
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL_URL", "")

    await _make_user_with_cart(async_engine, "903")
    client = FakeClient(member_response={"status": "administrator"})
    await order_handler.start_checkout(client, chat_id=1, user_id="903", message_id="msg_1")

    assert len(client.calls) == 1
    assert "Шаг 1/4" in client.calls[0]["text"]


# ---------------------------------------------------------------------------
# Handler tests: not subscribed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscription_not_subscribed_shows_gate(async_engine, monkeypatch):
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL", "@test_channel")
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL_URL", "https://max.ru/channel")

    await _make_user_with_cart(async_engine, "904")
    client = FakeClient(member_response={"status": "left"})
    await order_handler.start_checkout(client, chat_id=1, user_id="904", message_id="msg_1")

    assert len(client.calls) == 1
    assert "Шаг 1/4" not in client.calls[0]["text"]
    assert "подпишитесь на наш канал" in client.calls[0]["text"]
    assert "sub:check" in str(client.calls[0]["reply_markup"])


@pytest.mark.asyncio
async def test_subscription_none_response_shows_gate(async_engine, monkeypatch):
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL", "@test_channel")
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL_URL", "")

    await _make_user_with_cart(async_engine, "905")
    client = FakeClient(member_response=None)
    await order_handler.start_checkout(client, chat_id=1, user_id="905", message_id="msg_1")

    assert len(client.calls) == 1
    assert "подпишитесь на наш канал" in client.calls[0]["text"]


# ---------------------------------------------------------------------------
# Handler tests: retry (sub:check callback)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscription_check_retry_subscribed_starts_checkout(async_engine, monkeypatch):
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL", "@test_channel")
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL_URL", "")

    await _make_user_with_cart(async_engine, "906")
    client = FakeClient(member_response={"status": "member"})
    await subscription_handler.check_subscription(client, chat_id=1, user_id="906", message_id="msg_1")

    assert any("Шаг 1/4" in c.get("text", "") for c in client.calls)


@pytest.mark.asyncio
async def test_subscription_check_retry_not_subscribed_keeps_gate(async_engine, monkeypatch):
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL", "@test_channel")
    monkeypatch.setenv("MAX_REQUIRED_CHANNEL_URL", "")

    await _make_user_with_cart(async_engine, "907")
    client = FakeClient(member_response={"status": "left"})
    await subscription_handler.check_subscription(client, chat_id=1, user_id="907", message_id="msg_1")

    assert any("пока не видим подписку" in c.get("text", "") for c in client.calls)
    assert any("sub:check" in str(c.get("reply_markup", "")) for c in client.calls)


# ---------------------------------------------------------------------------
# Keyboard tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscription_gate_keyboard_has_sub_check_and_back():
    from src.bot.keyboards import subscription_gate_keyboard
    kb = subscription_gate_keyboard("https://max.ru/channel")
    payloads = [b["payload"] for row in kb for b in row]
    assert "sub:check" in payloads
    assert "menu:cart" in payloads


@pytest.mark.asyncio
async def test_subscription_gate_keyboard_empty_url():
    from src.bot.keyboards import subscription_gate_keyboard
    kb = subscription_gate_keyboard("")
    payloads = [b["payload"] for row in kb for b in row]
    assert "sub:check" in payloads
    assert "menu:cart" in payloads
