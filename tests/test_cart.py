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


@pytest.mark.asyncio
async def test_cart_view_keyboard_has_management_buttons():
    """cart_view_keyboard для непустой корзины содержит кнопки управления."""
    from src.bot.keyboards import cart_view_keyboard
    from src.services.cart_service import CartItemDTO

    items = [
        CartItemDTO(product_id=1, title="A", price=100, quantity=2, line_total=200),
        CartItemDTO(product_id=2, title="B", price=200, quantity=1, line_total=200),
    ]
    keyboard = cart_view_keyboard(items)

    # Для каждого товара — ряд с ➖ ➕ ❌
    assert keyboard[0][0]["payload"] == "qty:1:dec"
    assert keyboard[0][1]["payload"] == "qty:1:inc"
    assert keyboard[0][2]["payload"] == "rm:1"
    assert keyboard[1][0]["payload"] == "qty:2:dec"
    assert keyboard[1][1]["payload"] == "qty:2:inc"
    assert keyboard[1][2]["payload"] == "rm:2"

    # clear, catalog, home
    assert any(b["payload"] == "clear" for row in keyboard for b in row)
    assert any(b["payload"] == "menu:catalog" for row in keyboard for b in row)
    assert any(b["payload"] == "home" for row in keyboard for b in row)


@pytest.mark.asyncio
async def test_cart_service_change_quantity_inc(db_session):
    """change_quantity +1 увеличивает quantity и пересчитывает total."""
    user = User(max_user_id="111", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    view = await cart_service.change_quantity(db_session, user.id, product.id, 1)
    assert len(view.items) == 1
    assert view.items[0].quantity == 2
    assert view.total == 200


@pytest.mark.asyncio
async def test_cart_service_change_quantity_dec(db_session):
    """change_quantity -1 уменьшает quantity и пересчитывает total."""
    user = User(max_user_id="222", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=3)
    db_session.add(cart)
    await db_session.commit()

    view = await cart_service.change_quantity(db_session, user.id, product.id, -1)
    assert len(view.items) == 1
    assert view.items[0].quantity == 2
    assert view.total == 200


@pytest.mark.asyncio
async def test_cart_service_change_quantity_dec_to_zero_removes(db_session):
    """change_quantity -1 с quantity 1 удаляет позицию."""
    user = User(max_user_id="333", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    view = await cart_service.change_quantity(db_session, user.id, product.id, -1)
    assert len(view.items) == 0
    assert view.total == 0


@pytest.mark.asyncio
async def test_cart_service_remove_item(db_session):
    """remove_item удаляет позицию из корзины."""
    user = User(max_user_id="444", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=2)
    db_session.add(cart)
    await db_session.commit()

    view = await cart_service.remove_item(db_session, user.id, product.id)
    assert len(view.items) == 0
    assert view.total == 0


@pytest.mark.asyncio
async def test_cart_service_clear_cart(db_session):
    """clear_cart очищает корзину."""
    user = User(max_user_id="555", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=2)
    db_session.add(cart)
    await db_session.commit()

    view = await cart_service.clear_cart(db_session, user.id)
    assert len(view.items) == 0
    assert view.total == 0


@pytest.mark.asyncio
async def test_confirm_clear_cart_shows_confirmation(db_session):
    """confirm_clear_cart показывает подтверждение с clear:yes и clear:no."""
    user = User(max_user_id="666", full_name="Test")
    db_session.add(user)
    await db_session.commit()

    client = RecordingClient()
    await cart_handler.confirm_clear_cart(client, chat_id=1, user_id="666", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert "Очистить корзину" in call["text"]
    assert any(b["payload"] == "clear:yes" for row in call["reply_markup"] for b in row)
    assert any(b["payload"] == "clear:no" for row in call["reply_markup"] for b in row)


@pytest.mark.asyncio
async def test_clear_cart_clears_and_shows_empty(db_session):
    """clear_cart очищает корзину и показывает пустую корзину."""
    user = User(max_user_id="777", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    client = RecordingClient()
    await cart_handler.clear_cart(client, chat_id=1, user_id="777", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert "Корзина пуста" in call["text"]


@pytest.mark.asyncio
async def test_cancel_clear_cart_returns_to_cart(db_session):
    """cancel_clear_cart возвращает экран корзины без очистки."""
    user = User(max_user_id="888", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    client = RecordingClient()
    await cart_handler.cancel_clear_cart(client, chat_id=1, user_id="888", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert "Ваша корзина" in call["text"]
