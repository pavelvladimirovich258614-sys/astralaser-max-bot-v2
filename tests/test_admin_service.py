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


# ---------------------------------------------------------------------------
# Product creation (F10.4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_product_saves_fields(db_session):
    """create_product сохраняет все поля корректно."""
    from src.db.crud import product as product_crud

    cat = Category(title="Test", slug="test", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    product = await product_crud.create_product(
        session=db_session,
        category_id=cat.id,
        title="Кулон",
        description="Описание",
        price=840,
        cover_url="https://example.com/cover.jpg",
        sort_order=1,
        is_active=True,
    )
    await db_session.commit()

    assert product.id is not None
    assert product.title == "Кулон"
    assert product.description == "Описание"
    assert product.price == 840
    assert product.cover_url == "https://example.com/cover.jpg"
    assert product.sort_order == 1
    assert product.is_active is True


@pytest.mark.asyncio
async def test_create_product_photos_saves_urls(db_session):
    """create_photos сохраняет URL с правильным sort_order."""
    from src.db.crud import product as product_crud
    from src.db.crud import product_photo as product_photo_crud

    cat = Category(title="Test", slug="test", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    product = await product_crud.create_product(
        session=db_session,
        category_id=cat.id,
        title="Кулон",
        description="Desc",
        price=100,
        cover_url="url1",
        sort_order=1,
    )
    await db_session.flush()

    photos = await product_photo_crud.create_photos(db_session, product.id, ["url1", "url2", "url3"])
    await db_session.commit()

    assert len(photos) == 3
    assert photos[0].url == "url1"
    assert photos[0].sort_order == 0
    assert photos[1].url == "url2"
    assert photos[1].sort_order == 1
    assert photos[2].max_photo_token is None


@pytest.mark.asyncio
async def test_get_max_sort_order_returns_max(db_session):
    """get_max_sort_order возвращает максимальный sort_order в категории."""
    from src.db.crud import product as product_crud

    cat = Category(title="Test", slug="test", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    assert await product_crud.get_max_sort_order(db_session, cat.id) == 0

    p1 = Product(category_id=cat.id, title="A", description="D", price=100, cover_url="url", sort_order=3)
    p2 = Product(category_id=cat.id, title="B", description="D", price=200, cover_url="url", sort_order=7)
    db_session.add_all([p1, p2])
    await db_session.commit()

    assert await product_crud.get_max_sort_order(db_session, cat.id) == 7


@pytest.mark.asyncio
async def test_create_product_with_photos_sets_cover_url_and_sort_order(db_session):
    """create_product_with_photos создаёт товар и фото, cover_url = первый URL."""
    cat = Category(title="Test", slug="test", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    product = await admin_service.create_product_with_photos(
        session=db_session,
        category_id=cat.id,
        title="Кулон",
        description="Desc",
        price=500,
        photo_urls=["https://example.com/1.jpg", "https://example.com/2.jpg"],
    )

    assert product is not None
    assert product.title == "Кулон"
    assert product.cover_url == "https://example.com/1.jpg"
    assert product.sort_order == 1

    from src.db.crud import product_photo as product_photo_crud

    photos = await product_photo_crud.get_by_product_id(db_session, product.id)
    assert len(photos) == 2
    assert photos[0].url == "https://example.com/1.jpg"
    assert photos[1].url == "https://example.com/2.jpg"


@pytest.mark.asyncio
async def test_create_product_with_photos_requires_at_least_one_photo(db_session):
    """create_product_with_photos возвращает None если photo_urls пустой."""
    cat = Category(title="Test", slug="test", sort_order=1)
    db_session.add(cat)
    await db_session.flush()

    product = await admin_service.create_product_with_photos(
        session=db_session,
        category_id=cat.id,
        title="Кулон",
        description="Desc",
        price=500,
        photo_urls=[],
    )
    assert product is None


# ---------------------------------------------------------------------------
# Broadcast plan (F10.5.2a)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_broadcast_recipients_only_consented_users(db_session):
    """get_broadcast_recipients возвращает только пользователей с consent_at."""
    from src.db.crud import user as user_crud

    consented = User(max_user_id="c1", full_name="Consented")
    db_session.add(consented)
    await db_session.flush()
    await user_crud.update_consent(db_session, consented)

    unconsented = User(max_user_id="u1", full_name="Unconsented")
    db_session.add(unconsented)
    await db_session.commit()

    recipients = await user_crud.get_broadcast_recipients(db_session)
    ids = {u.max_user_id for u in recipients}
    assert "c1" in ids
    assert "u1" not in ids


@pytest.mark.asyncio
async def test_get_broadcast_recipients_respects_limit(db_session):
    """get_broadcast_recipients с limit ограничивает количество."""
    from src.db.crud import user as user_crud

    for i in range(5):
        user = User(max_user_id=f"u{i}", full_name=f"User{i}")
        db_session.add(user)
        await db_session.flush()
        await user_crud.update_consent(db_session, user)

    await db_session.commit()

    recipients = await user_crud.get_broadcast_recipients(db_session, limit=2)
    assert len(recipients) == 2


@pytest.mark.asyncio
async def test_prepare_broadcast_plan_disabled_by_default(monkeypatch, db_session):
    """По умолчанию BROADCAST_ENABLED=false — план disabled, но recipients считаются."""
    from src.db.crud import user as user_crud

    user = User(max_user_id="u1", full_name="User")
    db_session.add(user)
    await db_session.flush()
    await user_crud.update_consent(db_session, user)
    await db_session.commit()

    monkeypatch.setenv("BROADCAST_ENABLED", "false")
    plan = await admin_service.prepare_broadcast_plan(db_session, "Hello")

    assert plan.enabled is False
    assert plan.reason == "disabled"
    assert len(plan.recipients) == 1
    assert plan.recipients[0].max_user_id == "u1"
    assert plan.total_recipients == 1


@pytest.mark.asyncio
async def test_prepare_broadcast_plan_disabled_still_counts_recipients(monkeypatch, db_session):
    """При BROADCAST_ENABLED=false recipients всё равно заполняются с учётом max_recipients."""
    from src.db.crud import user as user_crud

    for i in range(5):
        user = User(max_user_id=f"u{i}", full_name=f"User{i}")
        db_session.add(user)
        await db_session.flush()
        await user_crud.update_consent(db_session, user)

    await db_session.commit()

    monkeypatch.setenv("BROADCAST_ENABLED", "false")
    monkeypatch.setenv("BROADCAST_MAX_RECIPIENTS", "3")
    plan = await admin_service.prepare_broadcast_plan(db_session, "Hello")

    assert plan.enabled is False
    assert plan.reason == "disabled"
    assert len(plan.recipients) == 3
    assert plan.total_recipients == 3
    assert plan.recipients[0].max_user_id == "u0"


@pytest.mark.asyncio
async def test_prepare_broadcast_plan_respects_max_recipients(monkeypatch, db_session):
    """BROADCAST_MAX_RECIPIENTS ограничивает список получателей."""
    from src.db.crud import user as user_crud

    for i in range(5):
        user = User(max_user_id=f"u{i}", full_name=f"User{i}")
        db_session.add(user)
        await db_session.flush()
        await user_crud.update_consent(db_session, user)

    await db_session.commit()

    monkeypatch.setenv("BROADCAST_ENABLED", "true")
    monkeypatch.setenv("BROADCAST_MAX_RECIPIENTS", "2")
    plan = await admin_service.prepare_broadcast_plan(db_session, "Hello")

    assert plan.enabled is True
    assert len(plan.recipients) == 2
    assert plan.total_recipients == 2


@pytest.mark.asyncio
async def test_prepare_broadcast_plan_uses_throttle_ms(monkeypatch, db_session):
    """BROADCAST_THROTTLE_MS передаётся в план."""
    monkeypatch.setenv("BROADCAST_ENABLED", "false")
    monkeypatch.setenv("BROADCAST_THROTTLE_MS", "750")
    plan = await admin_service.prepare_broadcast_plan(db_session, "Hello")

    assert plan.throttle_ms == 750


@pytest.mark.asyncio
async def test_prepare_broadcast_plan_does_not_send_messages(monkeypatch, db_session):
    """prepare_broadcast_plan не отправляет сообщения (нет сетевых вызовов)."""
    from src.db.crud import user as user_crud

    user = User(max_user_id="u1", full_name="User")
    db_session.add(user)
    await db_session.flush()
    await user_crud.update_consent(db_session, user)
    await db_session.commit()

    monkeypatch.setenv("BROADCAST_ENABLED", "true")
    plan = await admin_service.prepare_broadcast_plan(db_session, "Hello")

    assert plan.enabled is True
    assert len(plan.recipients) == 1
    assert plan.recipients[0].max_user_id == "u1"
    # Если бы были сетевые вызовы, тест упал бы из-за отсутствия mock — но их нет
