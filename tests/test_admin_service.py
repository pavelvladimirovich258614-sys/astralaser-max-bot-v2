import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.models import Base, Category, Order, OrderItem, Product, ProductPhoto, User
from src.services import admin_service


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


# ---------------------------------------------------------------------------
# get_recent_orders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_recent_orders_returns_latest_first(db_session):
    """get_recent_orders возвращает заказы по убыванию created_at."""
    user = User(max_user_id="100", full_name="Test")
    db_session.add(user)
    await db_session.flush()

    order1 = Order(
        user_id=user.id,
        customer_name="A",
        customer_phone="+7",
        delivery_address="Addr",
        total_amount=100,
        status="pending",
    )
    order2 = Order(
        user_id=user.id,
        customer_name="B",
        customer_phone="+7",
        delivery_address="Addr",
        total_amount=200,
        status="confirmed",
    )
    db_session.add_all([order1, order2])
    await db_session.commit()

    orders = await admin_service.get_recent_orders(db_session, limit=10)
    assert len(orders) == 2
    # SQLite может не отличать created_at без flush между add, но порядок desc должен работать
    ids = [o.id for o in orders]
    assert ids == sorted(ids, reverse=True)


@pytest.mark.asyncio
async def test_get_recent_orders_respects_limit(db_session):
    """get_recent_orders возвращает не больше limit заказов."""
    user = User(max_user_id="101", full_name="Test")
    db_session.add(user)
    await db_session.flush()

    for i in range(5):
        db_session.add(
            Order(
                user_id=user.id,
                customer_name=f"User{i}",
                customer_phone="+7",
                delivery_address="Addr",
                total_amount=100,
                status="pending",
            )
        )
    await db_session.commit()

    orders = await admin_service.get_recent_orders(db_session, limit=3)
    assert len(orders) == 3


# ---------------------------------------------------------------------------
# get_order_detail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_order_detail_loads_items(db_session):
    """get_order_detail загружает Order со связанными OrderItem."""
    user = User(max_user_id="200", full_name="Test")
    db_session.add(user)
    await db_session.flush()

    order = Order(
        user_id=user.id,
        customer_name="Иван",
        customer_phone="+7 999",
        delivery_address="Москва",
        total_amount=840,
        status="pending",
        notes="Гравировка",
    )
    db_session.add(order)
    await db_session.flush()

    item = OrderItem(
        order_id=order.id,
        product_id=1,
        product_title_snapshot="Кулон",
        price_snapshot=840,
        quantity=1,
    )
    db_session.add(item)
    await db_session.commit()

    result = await admin_service.get_order_detail(db_session, order.id)
    assert result is not None
    assert result.id == order.id
    assert result.customer_name == "Иван"
    assert len(result.items) == 1
    assert result.items[0].product_title_snapshot == "Кулон"


@pytest.mark.asyncio
async def test_get_order_detail_returns_none_for_missing(db_session):
    """get_order_detail возвращает None для несуществующего ID."""
    result = await admin_service.get_order_detail(db_session, 99999)
    assert result is None


# ---------------------------------------------------------------------------
# update_order_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_order_status_changes_status(db_session):
    """update_order_status меняет статус заказа."""
    user = User(max_user_id="300", full_name="Test")
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

    updated = await admin_service.update_order_status(db_session, order.id, "confirmed")
    assert updated is not None
    assert updated.status == "confirmed"


@pytest.mark.asyncio
async def test_update_order_status_returns_none_for_missing_order(db_session):
    """update_order_status возвращает None если заказ не найден."""
    result = await admin_service.update_order_status(db_session, 99999, "confirmed")
    assert result is None


@pytest.mark.asyncio
async def test_update_order_status_rejects_unknown_status(db_session):
    """update_order_status возвращает None для неизвестного статуса."""
    user = User(max_user_id="301", full_name="Test")
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

    result = await admin_service.update_order_status(db_session, order.id, "bogus")
    assert result is None

    # Убедиться, что статус не изменился
    fresh = await admin_service.get_order_detail(db_session, order.id)
    assert fresh is not None
    assert fresh.status == "pending"


# ---------------------------------------------------------------------------
# status helpers
# ---------------------------------------------------------------------------


def test_status_emoji_known():
    assert admin_service.status_emoji("pending") == "🟡"
    assert admin_service.status_emoji("confirmed") == "🔵"
    assert admin_service.status_emoji("completed") == "✅"
    assert admin_service.status_emoji("cancelled") == "❌"


def test_status_emoji_unknown():
    assert admin_service.status_emoji("unknown") == "⚪"


def test_status_label_known():
    assert admin_service.status_label("pending") == "В ожидании"
    assert admin_service.status_label("confirmed") == "Подтверждён"
    assert admin_service.status_label("completed") == "Завершён"
    assert admin_service.status_label("cancelled") == "Отменён"


def test_status_label_unknown():
    assert admin_service.status_label("whatever") == "whatever"


# ---------------------------------------------------------------------------
# Product management (F10.3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_admin_categories_returns_all_categories(db_session):
    """get_admin_categories возвращает все категории с количеством товаров."""
    cat = Category(title="Test", slug="test", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    product = Product(
        category_id=cat.id,
        title="Product",
        description="Desc",
        price=100,
        cover_url="url",
        sort_order=1,
    )
    db_session.add(product)
    await db_session.commit()

    result = await admin_service.get_admin_categories(db_session)
    assert len(result) == 1
    assert result[0]["category"].title == "Test"
    assert result[0]["product_count"] == 1


@pytest.mark.asyncio
async def test_get_admin_products_by_category_returns_all_products_including_inactive(db_session):
    """get_admin_products_by_category возвращает все товары, включая неактивные."""
    cat = Category(title="Test", slug="test", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    active = Product(
        category_id=cat.id,
        title="Active",
        description="Desc",
        price=100,
        cover_url="url",
        is_active=True,
        sort_order=1,
    )
    inactive = Product(
        category_id=cat.id,
        title="Inactive",
        description="Desc",
        price=200,
        cover_url="url",
        is_active=False,
        sort_order=2,
    )
    db_session.add_all([active, inactive])
    await db_session.commit()

    products = await admin_service.get_admin_products_by_category(db_session, cat.id)
    assert len(products) == 2
    titles = {p.title for p in products}
    assert "Active" in titles
    assert "Inactive" in titles


@pytest.mark.asyncio
async def test_get_admin_product_detail_loads_category_and_photo_count(db_session):
    """get_admin_product_detail загружает товар, категорию и количество фото."""
    cat = Category(title="Test", slug="test", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    product = Product(
        category_id=cat.id,
        title="Product",
        description="Desc",
        price=100,
        cover_url="url",
        sort_order=1,
    )
    db_session.add(product)
    await db_session.flush()

    photo = ProductPhoto(product_id=product.id, url="url1", sort_order=0)
    db_session.add(photo)
    await db_session.commit()

    detail = await admin_service.get_admin_product_detail(db_session, product.id)
    assert detail is not None
    assert detail["product"].title == "Product"
    assert detail["category"].title == "Test"
    assert detail["photo_count"] == 1


@pytest.mark.asyncio
async def test_toggle_product_active_true_to_false(db_session):
    """toggle_product_active меняет True на False."""
    cat = Category(title="Test", slug="test", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    product = Product(
        category_id=cat.id,
        title="Product",
        description="Desc",
        price=100,
        cover_url="url",
        is_active=True,
        sort_order=1,
    )
    db_session.add(product)
    await db_session.commit()

    updated = await admin_service.toggle_product_active(db_session, product.id)
    assert updated is not None
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_toggle_product_active_false_to_true(db_session):
    """toggle_product_active меняет False на True."""
    cat = Category(title="Test", slug="test", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    product = Product(
        category_id=cat.id,
        title="Product",
        description="Desc",
        price=100,
        cover_url="url",
        is_active=False,
        sort_order=1,
    )
    db_session.add(product)
    await db_session.commit()

    updated = await admin_service.toggle_product_active(db_session, product.id)
    assert updated is not None
    assert updated.is_active is True


@pytest.mark.asyncio
async def test_toggle_product_active_returns_none_for_missing_product(db_session):
    """toggle_product_active возвращает None для несуществующего товара."""
    result = await admin_service.toggle_product_active(db_session, 99999)
    assert result is None
