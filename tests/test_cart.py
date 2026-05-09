import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.bot.handlers import cart as cart_handler
from src.db.models import Base, CartItem, Product, User
from src.services import cart_service


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
async def override_cart_session_maker(monkeypatch, async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
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
async def test_show_cart_empty(db_session):
    """Пустая корзина: текст и клавиатура empty_cart_keyboard."""
    user = User(max_user_id="123", full_name="Test")
    db_session.add(user)
    await db_session.commit()

    client = RecordingClient()
    await cart_handler.show_cart(client, chat_id=1, user_id="123", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert "Корзина пуста" in call["text"]
    assert call["reply_markup"][0][0]["payload"] == "menu:catalog"
    assert call["reply_markup"][1][0]["payload"] == "home"


@pytest.mark.asyncio
async def test_show_cart_with_items(db_session):
    """Непустая корзина: список товаров, цены, количество, итог."""
    user = User(max_user_id="456", full_name="Test")
    db_session.add(user)
    await db_session.flush()

    product1 = Product(category_id=1, title="Кулон-столбик", description="Desc", price=840, cover_url="url1")
    product2 = Product(category_id=1, title="Браслет", description="Desc", price=940, cover_url="url2")
    db_session.add_all([product1, product2])
    await db_session.flush()

    cart1 = CartItem(user_id=user.id, product_id=product1.id, quantity=1)
    cart2 = CartItem(user_id=user.id, product_id=product2.id, quantity=2)
    db_session.add_all([cart1, cart2])
    await db_session.commit()

    client = RecordingClient()
    await cart_handler.show_cart(client, chat_id=1, user_id="456", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert "🛒 Ваша корзина" in call["text"]
    assert "Кулон-столбик" in call["text"]
    assert "Браслет" in call["text"]
    assert "840 ₽ × 1 = 840 ₽" in call["text"]
    assert "940 ₽ × 2 = 1880 ₽" in call["text"]
    assert "Итого: 2720 ₽" in call["text"]


@pytest.mark.asyncio
async def test_show_cart_uses_send_message_without_message_id(db_session):
    """Без message_id используется send_message."""
    user = User(max_user_id="789", full_name="Test")
    db_session.add(user)
    await db_session.commit()

    client = RecordingClient()
    await cart_handler.show_cart(client, chat_id=1, user_id="789")

    assert len(client.calls) == 1
    assert client.calls[0]["method"] == "send_message"
    assert "Корзина пуста" in client.calls[0]["text"]


@pytest.mark.asyncio
async def test_get_cart_view_calculates_total(db_session):
    """get_cart_view правильно считает line_total и total."""
    user = User(max_user_id="999", full_name="Test")
    db_session.add(user)
    await db_session.flush()

    product1 = Product(category_id=1, title="A", description="Desc", price=100, cover_url="url")
    product2 = Product(category_id=1, title="B", description="Desc", price=200, cover_url="url")
    db_session.add_all([product1, product2])
    await db_session.flush()

    cart1 = CartItem(user_id=user.id, product_id=product1.id, quantity=3)
    cart2 = CartItem(user_id=user.id, product_id=product2.id, quantity=1)
    db_session.add_all([cart1, cart2])
    await db_session.commit()

    view = await cart_service.get_cart_view(db_session, user.id)

    assert len(view.items) == 2
    assert view.total == 500
    item_a = next(i for i in view.items if i.title == "A")
    item_b = next(i for i in view.items if i.title == "B")
    assert item_a.line_total == 300
    assert item_b.line_total == 200
