import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.bot.handlers import cart as cart_handler
from src.bot.handlers import order as order_handler
from src.db.crud import cart as cart_crud
from src.db.crud import order as order_crud
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
    def __init__(self, delete_returns=True):
        self.calls = []
        self.delete_returns = delete_returns

    async def edit_message(self, chat_id, message_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "edit_message", "chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    async def send_message(self, chat_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "send_message", "chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    async def delete_message(self, chat_id, message_id):
        self.calls.append({"method": "delete_message", "chat_id": chat_id, "message_id": message_id})
        return self.delete_returns

    async def get_chat_member(self, chat_id, user_id):
        return {"members": [{"user_id": int(user_id)}]}


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


# ---------------------------------------------------------------------------
# F07.2 — FSM data collection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_name_valid_moves_to_phone(db_session):
    """Валидное ФИО сохраняется, state переходит на order:waiting_phone."""
    user = User(max_user_id="700", full_name="Test")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_waiting_name(db_session, user.id)

    client = RecordingClient()
    handled = await order_handler.handle_fsm_message(client, chat_id=1, user_id="700", message_id="m1", text="Иван Иванов")
    assert handled is True

    async with order_handler.async_session_maker() as fresh:
        state, data = await fsm_service.get_state(fresh, user.id)
    assert state == "order:waiting_phone"
    assert data["customer_name"] == "Иван Иванов"
    assert any("Шаг 2/4" in c["text"] for c in client.calls if c["method"] == "send_message")


@pytest.mark.asyncio
async def test_handle_name_invalid_stays_waiting_name(db_session):
    """Невалидное имя не меняет state."""
    user = User(max_user_id="701", full_name="Test")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_waiting_name(db_session, user.id)

    client = RecordingClient()
    handled = await order_handler.handle_fsm_message(client, chat_id=1, user_id="701", message_id="m1", text="И")
    assert handled is True

    state, _ = await fsm_service.get_state(db_session, user.id)
    assert state == "order:waiting_name"
    assert any("Пожалуйста, напишите ФИО полностью" in c["text"] for c in client.calls)


@pytest.mark.asyncio
async def test_handle_phone_valid_moves_to_address(db_session):
    """Валидный телефон сохраняется, state переходит на order:waiting_address."""
    user = User(max_user_id="702", full_name="Test")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(db_session, user.id, "order:waiting_phone", {"customer_name": "Иван"})

    client = RecordingClient()
    handled = await order_handler.handle_fsm_message(client, chat_id=1, user_id="702", message_id="m1", text="+7 903 348 92 05")
    assert handled is True

    async with order_handler.async_session_maker() as fresh:
        state, data = await fsm_service.get_state(fresh, user.id)
    assert state == "order:waiting_address"
    assert data["phone"] == "+7 903 348 92 05"
    assert any("Шаг 3/4" in c["text"] for c in client.calls if c["method"] == "send_message")


@pytest.mark.asyncio
async def test_handle_phone_invalid_stays_waiting_phone(db_session):
    """Невалидный телефон не меняет state."""
    user = User(max_user_id="703", full_name="Test")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(db_session, user.id, "order:waiting_phone", {})

    client = RecordingClient()
    handled = await order_handler.handle_fsm_message(client, chat_id=1, user_id="703", message_id="m1", text="abc")
    assert handled is True

    state, _ = await fsm_service.get_state(db_session, user.id)
    assert state == "order:waiting_phone"
    assert any("Не похоже на телефон" in c["text"] for c in client.calls)


@pytest.mark.asyncio
async def test_handle_address_valid_moves_to_notes(db_session):
    """Валидный адрес сохраняется, state переходит на order:waiting_notes."""
    user = User(max_user_id="704", full_name="Test")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(db_session, user.id, "order:waiting_address", {})

    client = RecordingClient()
    handled = await order_handler.handle_fsm_message(client, chat_id=1, user_id="704", message_id="m1", text="Москва, ул. Ленина 1")
    assert handled is True

    async with order_handler.async_session_maker() as fresh:
        state, data = await fsm_service.get_state(fresh, user.id)
    assert state == "order:waiting_notes"
    assert data["address"] == "Москва, ул. Ленина 1"
    assert any("Шаг 4/4" in c["text"] for c in client.calls if c["method"] == "send_message")


@pytest.mark.asyncio
async def test_handle_notes_valid_moves_to_ready_confirm(db_session):
    """Валидные notes сохраняются, state переходит на order:ready_confirm."""
    user = User(max_user_id="705", full_name="Test")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(db_session, user.id, "order:waiting_notes", {})

    client = RecordingClient()
    handled = await order_handler.handle_fsm_message(client, chat_id=1, user_id="705", message_id="m1", text="Гравировка: Love")
    assert handled is True

    async with order_handler.async_session_maker() as fresh:
        state, data = await fsm_service.get_state(fresh, user.id)
    assert state == "order:ready_confirm"
    assert data["notes"] == "Гравировка: Love"
    assert any("Данные для заказа собраны" in c["text"] for c in client.calls if c["method"] == "send_message")


@pytest.mark.asyncio
async def test_handle_notes_empty_uses_default(db_session):
    """Пустой комментарий заменяется на дефолтный текст."""
    user = User(max_user_id="706", full_name="Test")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(db_session, user.id, "order:waiting_notes", {})

    client = RecordingClient()
    handled = await order_handler.handle_fsm_message(client, chat_id=1, user_id="706", message_id="m1", text="   ")
    assert handled is True

    async with order_handler.async_session_maker() as fresh:
        _, data = await fsm_service.get_state(fresh, user.id)
    assert data["notes"] == "Обсудим с менеджером"


@pytest.mark.asyncio
async def test_handle_notes_too_long_stays_waiting_notes(db_session):
    """Слишком длинный комментарий не меняет state."""
    user = User(max_user_id="707", full_name="Test")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(db_session, user.id, "order:waiting_notes", {})

    client = RecordingClient()
    long_text = "x" * 501
    handled = await order_handler.handle_fsm_message(client, chat_id=1, user_id="707", message_id="m1", text=long_text)
    assert handled is True

    state, _ = await fsm_service.get_state(db_session, user.id)
    assert state == "order:waiting_notes"
    assert any("Слишком длинный комментарий" in c["text"] for c in client.calls)


@pytest.mark.asyncio
async def test_valid_fsm_message_best_effort_deletes_user_message(db_session):
    """После валидного сообщения вызывается delete_message с message_id пользователя."""
    user = User(max_user_id="708", full_name="Test")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_waiting_name(db_session, user.id)

    client = RecordingClient()
    await order_handler.handle_fsm_message(client, chat_id=1, user_id="708", message_id="user_msg_42", text="Иван Иванов")

    delete_calls = [c for c in client.calls if c["method"] == "delete_message"]
    assert len(delete_calls) == 1
    assert delete_calls[0]["message_id"] == "user_msg_42"


@pytest.mark.asyncio
async def test_delete_message_failure_does_not_break_fsm(db_session):
    """Если delete_message возвращает False, state всё равно переходит дальше."""
    user = User(max_user_id="709", full_name="Test")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_waiting_name(db_session, user.id)

    client = RecordingClient(delete_returns=False)
    await order_handler.handle_fsm_message(client, chat_id=1, user_id="709", message_id="m1", text="Иван Иванов")

    async with order_handler.async_session_maker() as fresh:
        state, _ = await fsm_service.get_state(fresh, user.id)
    assert state == "order:waiting_phone"


# ---------------------------------------------------------------------------
# F07.3 — Summary заказа
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_show_order_summary_with_ready_state_shows_cart_items(db_session):
    """При state order:ready_confirm summary содержит товары из корзины."""
    user = User(max_user_id="800", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P1", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=2)
    db_session.add(cart)
    await db_session.commit()

    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван", "phone": "+7", "address": "Москва", "notes": "Гравировка"}
    )

    client = RecordingClient()
    await order_handler.show_order_summary(client, chat_id=1, user_id="800", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert "P1" in call["text"]
    assert "200 ₽" in call["text"]  # 100 × 2


@pytest.mark.asyncio
async def test_show_order_summary_shows_customer_data(db_session):
    """Summary содержит ФИО, телефон, адрес, notes."""
    user = User(max_user_id="801", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван Иванов", "phone": "+7 999", "address": "Москва", "notes": "Гравировка"}
    )

    client = RecordingClient()
    await order_handler.show_order_summary(client, chat_id=1, user_id="801", message_id="msg_1")

    call = client.calls[0]
    assert "Иван Иванов" in call["text"]
    assert "+7 999" in call["text"]
    assert "Москва" in call["text"]
    assert "Гравировка" in call["text"]


@pytest.mark.asyncio
async def test_show_order_summary_shows_total(db_session):
    """Summary содержит итог."""
    user = User(max_user_id="802", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=250, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=3)
    db_session.add(cart)
    await db_session.commit()

    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван", "phone": "+7", "address": "М", "notes": "N"}
    )

    client = RecordingClient()
    await order_handler.show_order_summary(client, chat_id=1, user_id="802", message_id="msg_1")

    call = client.calls[0]
    assert "Итого: 750 ₽" in call["text"]


@pytest.mark.asyncio
async def test_show_order_summary_uses_edit_message_when_message_id(db_session):
    """При message_id используется edit_message."""
    user = User(max_user_id="803", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван", "phone": "+7", "address": "М", "notes": "N"}
    )

    client = RecordingClient()
    await order_handler.show_order_summary(client, chat_id=1, user_id="803", message_id="msg_1")
    assert client.calls[0]["method"] == "edit_message"


@pytest.mark.asyncio
async def test_show_order_summary_empty_cart_returns_cart(db_session):
    """Если корзина пустая, показывается пустая корзина."""
    user = User(max_user_id="804", full_name="Test")
    db_session.add(user)
    await db_session.commit()
    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван", "phone": "+7", "address": "М", "notes": "N"}
    )

    client = RecordingClient()
    await order_handler.show_order_summary(client, chat_id=1, user_id="804", message_id="msg_1")

    call = client.calls[0]
    assert "Корзина пуста" in call["text"]


@pytest.mark.asyncio
async def test_show_order_summary_wrong_state_shows_warning(db_session):
    """Если state не ready_confirm, показывается предупреждение."""
    user = User(max_user_id="805", full_name="Test")
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
    await order_handler.show_order_summary(client, chat_id=1, user_id="805", message_id="msg_1")

    call = client.calls[0]
    assert "Данные заказа ещё не заполнены" in call["text"]


@pytest.mark.asyncio
async def test_order_summary_keyboard_has_confirm_and_cancel():
    """Клавиатура содержит order:confirm и order:cancel."""
    from src.bot.keyboards import order_summary_keyboard
    kb = order_summary_keyboard()
    payloads = [b["payload"] for row in kb for b in row]
    assert "order:confirm" in payloads
    assert "order:cancel" in payloads


@pytest.mark.asyncio
async def test_show_order_summary_does_not_create_order(db_session):
    """Убедиться, что Order не создаётся в F07.3."""
    user = User(max_user_id="806", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван", "phone": "+7", "address": "М", "notes": "N"}
    )

    client = RecordingClient()
    await order_handler.show_order_summary(client, chat_id=1, user_id="806", message_id="msg_1")

    order = await order_crud.get_by_id(db_session, 1)
    assert order is None


# ---------------------------------------------------------------------------
# F07.4 — Создание заказа и очистка корзины
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_confirm_order_creates_order_and_items(db_session):
    """При state order:ready_confirm и непустой корзине создаётся Order и OrderItem."""
    user = User(max_user_id="900", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P1", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=2)
    db_session.add(cart)
    await db_session.commit()

    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван", "phone": "+7", "address": "Москва", "notes": "Гравировка"}
    )

    client = RecordingClient()
    await order_handler.confirm_order(client, chat_id=1, user_id="900", message_id="msg_1")

    async with order_handler.async_session_maker() as fresh:
        order = await order_crud.get_by_id(fresh, 1)
    assert order is not None
    assert order.customer_name == "Иван"
    assert order.customer_phone == "+7"
    assert order.delivery_address == "Москва"
    assert order.total_amount == 200
    assert order.notes == "Гравировка"
    assert order.status == "pending"
    assert len(order.items) == 1
    item = order.items[0]
    assert item.product_id == product.id
    assert item.quantity == 2
    assert item.price_snapshot == 100


@pytest.mark.asyncio
async def test_confirm_order_uses_snapshots(db_session):
    """OrderItem содержит snapshot названия, цены и количества."""
    user = User(max_user_id="901", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="UniqueName", description="D", price=555, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=3)
    db_session.add(cart)
    await db_session.commit()

    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван", "phone": "+7", "address": "М", "notes": "N"}
    )

    client = RecordingClient()
    await order_handler.confirm_order(client, chat_id=1, user_id="901", message_id="msg_1")

    async with order_handler.async_session_maker() as fresh:
        order = await order_crud.get_by_id(fresh, 1)
    assert order is not None
    item = order.items[0]
    assert item.product_title_snapshot == "UniqueName"
    assert item.price_snapshot == 555
    assert item.quantity == 3


@pytest.mark.asyncio
async def test_confirm_order_clears_cart(db_session):
    """После подтверждения корзина пустая."""
    user = User(max_user_id="902", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван", "phone": "+7", "address": "М", "notes": "N"}
    )

    client = RecordingClient()
    await order_handler.confirm_order(client, chat_id=1, user_id="902", message_id="msg_1")

    async with order_handler.async_session_maker() as fresh:
        cart_items = await cart_crud.get_user_cart(fresh, user.id)
    assert cart_items == []


@pytest.mark.asyncio
async def test_confirm_order_clears_user_state(db_session):
    """После подтверждения UserState очищен."""
    user = User(max_user_id="903", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван", "phone": "+7", "address": "М", "notes": "N"}
    )

    client = RecordingClient()
    await order_handler.confirm_order(client, chat_id=1, user_id="903", message_id="msg_1")

    async with order_handler.async_session_maker() as fresh:
        state, _ = await fsm_service.get_state(fresh, user.id)
    assert state is None


@pytest.mark.asyncio
async def test_confirm_order_shows_confirmation_with_order_id(db_session, monkeypatch):
    """Пользователь получает сообщение с номером заказа."""
    monkeypatch.setattr(
        order_handler,
        "get_settings",
        lambda: type("S", (), {"admin_chat_ids_list": []})(),
    )
    user = User(max_user_id="904", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван", "phone": "+7", "address": "М", "notes": "N"}
    )

    client = RecordingClient()
    await order_handler.confirm_order(client, chat_id=1, user_id="904", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert "Заказ оформлен" in call["text"]
    assert "Номер заказа: #1" in call["text"]


@pytest.mark.asyncio
async def test_confirm_order_empty_cart_does_not_create_order(db_session):
    """Если корзина пустая, заказ не создаётся."""
    user = User(max_user_id="905", full_name="Test")
    db_session.add(user)
    await db_session.commit()

    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван", "phone": "+7", "address": "М", "notes": "N"}
    )

    client = RecordingClient()
    await order_handler.confirm_order(client, chat_id=1, user_id="905", message_id="msg_1")

    async with order_handler.async_session_maker() as fresh:
        order = await order_crud.get_by_id(fresh, 1)
    assert order is None


@pytest.mark.asyncio
async def test_confirm_order_wrong_state_does_not_create_order(db_session):
    """Если state не ready_confirm, заказ не создаётся."""
    user = User(max_user_id="906", full_name="Test")
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
    await order_handler.confirm_order(client, chat_id=1, user_id="906", message_id="msg_1")

    async with order_handler.async_session_maker() as fresh:
        order = await order_crud.get_by_id(fresh, 1)
    assert order is None


@pytest.mark.asyncio
async def test_confirm_order_no_notification_when_no_admins(db_session, monkeypatch):
    """При пустом admin_ids_list заказ оформляется, уведомления не отправляются."""
    monkeypatch.setattr(
        order_handler,
        "get_settings",
        lambda: type("S", (), {"admin_chat_ids_list": []})(),
    )
    user = User(max_user_id="907", full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="P", description="D", price=100, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()

    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван", "phone": "+7", "address": "М", "notes": "N"}
    )

    client = RecordingClient()
    await order_handler.confirm_order(client, chat_id=1, user_id="907", message_id="msg_1")

    async with order_handler.async_session_maker() as fresh:
        order = await order_crud.get_by_id(fresh, 1)
    assert order is not None

    send_calls = [c for c in client.calls if c["method"] == "send_message"]
    assert len(send_calls) == 0
    edit_calls = [c for c in client.calls if c["method"] == "edit_message"]
    assert len(edit_calls) == 1
    assert "Заказ оформлен" in edit_calls[0]["text"]


# ---------------------------------------------------------------------------
# F07.5 — Уведомления менеджерам
# ---------------------------------------------------------------------------


def _make_settings(admin_chat_ids: list[str]) -> object:
    return type("S", (), {"admin_chat_ids_list": admin_chat_ids})()


async def _setup_order_for_confirm(db_session, max_user_id="910"):
    user = User(max_user_id=max_user_id, full_name="Test")
    db_session.add(user)
    await db_session.flush()
    product = Product(category_id=1, title="Браслет с гравировкой", description="D", price=940, cover_url="url")
    db_session.add(product)
    await db_session.flush()
    cart = CartItem(user_id=user.id, product_id=product.id, quantity=1)
    db_session.add(cart)
    await db_session.commit()
    await fsm_service.set_state(
        db_session, user.id, "order:ready_confirm",
        {"customer_name": "Иван Иванов", "phone": "+7 999 123 45 67", "address": "Москва, ул. Тестовая, 1", "notes": "Тест F07.5"}
    )
    return user, product


@pytest.mark.asyncio
async def test_confirm_order_sends_notification_to_admins(db_session, monkeypatch):
    """При двух admin IDs отправляются уведомления обоим."""
    monkeypatch.setattr(
        order_handler, "get_settings",
        lambda: _make_settings(["196318594", "196318595"]),
    )
    await _setup_order_for_confirm(db_session)

    client = RecordingClient()
    await order_handler.confirm_order(client, chat_id=1, user_id="910", message_id="msg_1")

    admin_calls = [c for c in client.calls if c["method"] == "send_message" and c["chat_id"] in ("196318594", "196318595")]
    assert len(admin_calls) == 2
    chat_ids = {c["chat_id"] for c in admin_calls}
    assert chat_ids == {"196318594", "196318595"}


@pytest.mark.asyncio
async def test_confirm_order_notification_format(db_session, monkeypatch):
    """Текст уведомления содержит все данные заказа."""
    monkeypatch.setattr(
        order_handler, "get_settings",
        lambda: _make_settings(["196318594"]),
    )
    await _setup_order_for_confirm(db_session, max_user_id="911")

    client = RecordingClient()
    await order_handler.confirm_order(client, chat_id=1, user_id="911", message_id="msg_1")

    admin_calls = [c for c in client.calls if c["method"] == "send_message" and c["chat_id"] == "196318594"]
    assert len(admin_calls) == 1
    text = admin_calls[0]["text"]
    assert "Новый заказ" in text
    assert "Браслет с гравировкой" in text
    assert "940 ₽" in text
    assert "Итого:" in text
    assert "Иван Иванов" in text
    assert "+7 999 123 45 67" in text
    assert "Москва, ул. Тестовая, 1" in text
    assert "Тест F07.5" in text


@pytest.mark.asyncio
async def test_confirm_order_notification_failure_does_not_break_order(db_session, monkeypatch):
    """Если send_message падает для одного админа, заказ всё равно оформлен."""

    class FailingClient(RecordingClient):
        async def send_message(self, chat_id, text, reply_markup=None, photo_url=None, photo=None):
            if chat_id == "196318594":
                raise RuntimeError("network error")
            return await super().send_message(chat_id, text, reply_markup, photo_url, photo_url)

    monkeypatch.setattr(
        order_handler, "get_settings",
        lambda: _make_settings(["196318594", "196318595"]),
    )
    await _setup_order_for_confirm(db_session, max_user_id="912")

    client = FailingClient()
    await order_handler.confirm_order(client, chat_id=1, user_id="912", message_id="msg_1")

    async with order_handler.async_session_maker() as fresh:
        order = await order_crud.get_by_id(fresh, 1)
    assert order is not None
    assert order.total_amount == 940

    async with order_handler.async_session_maker() as fresh:
        cart_items = await cart_crud.get_user_cart(fresh, order.user_id)
    assert cart_items == []

    async with order_handler.async_session_maker() as fresh:
        state, _ = await fsm_service.get_state(fresh, order.user_id)
    assert state is None

    edit_calls = [c for c in client.calls if c["method"] == "edit_message"]
    assert len(edit_calls) == 1
    assert "Заказ оформлен" in edit_calls[0]["text"]

    admin_success = [c for c in client.calls if c["method"] == "send_message" and c["chat_id"] == "196318595"]
    assert len(admin_success) == 1
