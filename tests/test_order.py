import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.bot.handlers import cart as cart_handler
from src.bot.handlers import order as order_handler
from src.db.models import Base, CartItem, Product, User
from src.services import fsm_service


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
def set_token(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "test_token")


@pytest.fixture(autouse=True)
async def override_order_session_maker(monkeypatch, async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(order_handler, "async_session_maker", test_session_maker)
    monkeypatch.setattr(cart_handler, "async_session_maker", test_session_maker)

    yield

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


class RecordingClient:
    def __init__(self):
        self.calls = []

    async def edit_message(self, chat_id, message_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "edit_message", "chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    async def send_message(self, chat_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "send_message", "chat_id": chat_id, "text": text, "reply_markup": reply_markup})


@pytest.mark.asyncio
async def test_fsm_service_set_waiting_name(db_session):
    """set_waiting_name сохраняет state order:waiting_name и пустые data."""
    user = User(max_user_id="111", full_name="Test")
    db_session.add(user)
    await db_session.commit()

    await fsm_service.set_waiting_name(db_session, user.id)

    state, data = await fsm_service.get_state(db_session, user.id)
    assert state == "order:waiting_name"
    assert data == {}


@pytest.mark.asyncio
async def test_fsm_service_clear_state(db_session):
    """clear_state удаляет state пользователя."""
    user = User(max_user_id="222", full_name="Test")
    db_session.add(user)
    await db_session.commit()

    await fsm_service.set_waiting_name(db_session, user.id)
    await fsm_service.clear_state(db_session, user.id)

    state, data = await fsm_service.get_state(db_session, user.id)
    assert state is None
    assert data == {}


@pytest.mark.asyncio
async def test_start_checkout_empty_cart_shows_empty_cart(db_session):
    """checkout при пустой корзине показывает пустую корзину, state не ставится."""
    user = User(max_user_id="333", full_name="Test")
    db_session.add(user)
    await db_session.commit()

    client = RecordingClient()
    await order_handler.start_checkout(client, chat_id=1, user_id="333", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert "Корзина пуста" in call["text"]

    state, _ = await fsm_service.get_state(db_session, user.id)
    assert state is None


@pytest.mark.asyncio
async def test_start_checkout_non_empty_sets_waiting_name(db_session):
    """checkout при непустой корзине устанавливает state order:waiting_name."""
    user = User(max_user_id="444", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    client = RecordingClient()
    await order_handler.start_checkout(client, chat_id=1, user_id="444", message_id="msg_1")

    async with order_handler.async_session_maker() as fresh_session:
        state, _ = await fsm_service.get_state(fresh_session, user.id)
    assert state == "order:waiting_name"


@pytest.mark.asyncio
async def test_start_checkout_non_empty_shows_step_1(db_session):
    """checkout при непустой корзине показывает экран Шаг 1/4 с кнопкой отмены."""
    user = User(max_user_id="555", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    client = RecordingClient()
    await order_handler.start_checkout(client, chat_id=1, user_id="555", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert "Шаг 1/4" in call["text"]
    assert any(b["payload"] == "order:cancel" for row in call["reply_markup"] for b in row)


@pytest.mark.asyncio
async def test_cancel_checkout_clears_state_and_returns_cart(db_session):
    """order:cancel очищает state и возвращает корзину."""
    user = User(max_user_id="666", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    await fsm_service.set_waiting_name(db_session, user.id)

    client = RecordingClient()
    await order_handler.cancel_checkout(client, chat_id=1, user_id="666", message_id="msg_1")

    async with order_handler.async_session_maker() as fresh_session:
        state, _ = await fsm_service.get_state(fresh_session, user.id)
    assert state is None

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert "Ваша корзина" in call["text"]
