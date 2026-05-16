import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.crud.cart import add_item, get_user_cart, remove_item, update_quantity
from src.db.crud.category import get_active_categories, get_by_slug
from src.db.crud.order import create_order, get_by_user
from src.db.crud.order import get_by_id as get_order_by_id
from src.db.crud.product import get_by_category
from src.db.crud.user import (
    create_user,
    get_user_by_max_id,
    get_users_by_max_ids,
    update_consent,
    update_max_chat_id,
)
from src.db.crud.user_state import clear_state, get_state, set_state
from src.db.models import Base, Category, Product


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


@pytest.mark.asyncio
async def test_user_create_and_get(db_session: AsyncSession):
    user = await create_user(db_session, max_user_id="12345", username="testuser", full_name="Test User")
    assert user.id is not None
    assert user.max_user_id == "12345"

    found = await get_user_by_max_id(db_session, "12345")
    assert found is not None
    assert found.username == "testuser"


@pytest.mark.asyncio
async def test_user_not_found(db_session: AsyncSession):
    found = await get_user_by_max_id(db_session, "nonexistent")
    assert found is None


@pytest.mark.asyncio
async def test_get_users_by_max_ids(db_session: AsyncSession):
    user1 = await create_user(db_session, max_user_id="admin_1", max_chat_id="chat_1")
    user2 = await create_user(db_session, max_user_id="admin_2", max_chat_id="chat_2")
    await create_user(db_session, max_user_id="regular", max_chat_id="chat_3")

    found = await get_users_by_max_ids(db_session, ["admin_2", "missing", "admin_1"])

    assert found == [user1, user2]


@pytest.mark.asyncio
async def test_update_consent(db_session: AsyncSession):
    user = await create_user(db_session, max_user_id="99999")
    assert user.consent_at is None

    updated = await update_consent(db_session, user)
    assert updated.consent_at is not None


@pytest.mark.asyncio
async def test_category_get_by_slug(db_session: AsyncSession):
    category = Category(title="Колье", slug="kole", sort_order=1)
    db_session.add(category)
    await db_session.commit()

    found = await get_by_slug(db_session, "kole")
    assert found is not None
    assert found.title == "Колье"

    not_found = await get_by_slug(db_session, "missing")
    assert not_found is None


@pytest.mark.asyncio
async def test_get_active_categories(db_session: AsyncSession):
    cat1 = Category(title="A", slug="a", sort_order=1, is_active=True)
    cat2 = Category(title="B", slug="b", sort_order=2, is_active=False)
    db_session.add_all([cat1, cat2])
    await db_session.commit()

    active = await get_active_categories(db_session)
    assert len(active) == 1
    assert active[0].slug == "a"


@pytest.mark.asyncio
async def test_product_get_by_category(db_session: AsyncSession):
    category = Category(title="Test", slug="test-cat", sort_order=1)
    db_session.add(category)
    await db_session.commit()

    product = Product(
        category_id=category.id,
        title="Test Product",
        description="Desc",
        price=100,
        cover_url="url",
        sort_order=1,
    )
    db_session.add(product)
    await db_session.commit()

    products = await get_by_category(db_session, category.id)
    assert len(products) == 1
    assert products[0].title == "Test Product"


@pytest.mark.asyncio
async def test_cart_add_and_get(db_session: AsyncSession):
    user = await create_user(db_session, max_user_id="cart_user")
    category = Category(title="Cat", slug="cat", sort_order=1)
    db_session.add(category)
    await db_session.commit()

    product = Product(category_id=category.id, title="Item", description="Desc", price=50, cover_url="url")
    db_session.add(product)
    await db_session.commit()

    item = await add_item(db_session, user.id, product.id, quantity=2)
    assert item.quantity == 2

    cart = await get_user_cart(db_session, user.id)
    assert len(cart) == 1
    assert cart[0].quantity == 2


@pytest.mark.asyncio
async def test_cart_remove(db_session: AsyncSession):
    user = await create_user(db_session, max_user_id="rm_user")
    category = Category(title="Cat", slug="cat2", sort_order=1)
    db_session.add(category)
    await db_session.commit()

    product = Product(category_id=category.id, title="Item", description="Desc", price=50, cover_url="url")
    db_session.add(product)
    await db_session.commit()

    await add_item(db_session, user.id, product.id)
    await remove_item(db_session, user.id, product.id)

    cart = await get_user_cart(db_session, user.id)
    assert len(cart) == 0


@pytest.mark.asyncio
async def test_cart_update_quantity_to_zero(db_session: AsyncSession):
    user = await create_user(db_session, max_user_id="qty_user")
    category = Category(title="Cat", slug="cat3", sort_order=1)
    db_session.add(category)
    await db_session.commit()

    product = Product(category_id=category.id, title="Item", description="Desc", price=50, cover_url="url")
    db_session.add(product)
    await db_session.commit()

    await add_item(db_session, user.id, product.id, quantity=3)
    result = await update_quantity(db_session, user.id, product.id, 0)
    assert result is None

    cart = await get_user_cart(db_session, user.id)
    assert len(cart) == 0


@pytest.mark.asyncio
async def test_order_create_and_get(db_session: AsyncSession):
    user = await create_user(db_session, max_user_id="order_user")
    category = Category(title="Cat", slug="cat4", sort_order=1)
    db_session.add(category)
    await db_session.commit()

    product = Product(category_id=category.id, title="Item", description="Desc", price=100, cover_url="url")
    db_session.add(product)
    await db_session.commit()

    order = await create_order(
        db_session,
        user_id=user.id,
        customer_name="Иванов Иван",
        customer_phone="+7 999 123 45 67",
        delivery_address="Москва",
        total_amount=100,
        notes="Тест",
        items=[
            {
                "product_id": product.id,
                "product_title_snapshot": product.title,
                "price_snapshot": product.price,
                "quantity": 1,
            }
        ],
    )

    assert order.id is not None
    assert order.total_amount == 100

    found = await get_order_by_id(db_session, order.id)
    assert found is not None
    assert found.customer_name == "Иванов Иван"

    user_orders = await get_by_user(db_session, user.id)
    assert len(user_orders) == 1


@pytest.mark.asyncio
async def test_user_state_set_get_clear(db_session: AsyncSession):
    user = await create_user(db_session, max_user_id="state_user")

    state = await set_state(db_session, user.id, "order:waiting_name", '{"name": ""}')
    assert state.state == "order:waiting_name"

    found = await get_state(db_session, user.id)
    assert found is not None
    assert found.data == '{"name": ""}'

    await clear_state(db_session, user.id)
    cleared = await get_state(db_session, user.id)
    assert cleared is None


@pytest.mark.asyncio
async def test_create_user_with_max_chat_id(db_session: AsyncSession):
    user = await create_user(db_session, max_user_id="chat_user", max_chat_id="123456")
    assert user.max_chat_id == "123456"

    found = await get_user_by_max_id(db_session, "chat_user")
    assert found is not None
    assert found.max_chat_id == "123456"


@pytest.mark.asyncio
async def test_update_max_chat_id_sets_value(db_session: AsyncSession):
    user = await create_user(db_session, max_user_id="upd_user")
    assert user.max_chat_id is None

    updated = await update_max_chat_id(db_session, user, "789012")
    assert updated.max_chat_id == "789012"

    found = await get_user_by_max_id(db_session, "upd_user")
    assert found is not None
    assert found.max_chat_id == "789012"


@pytest.mark.asyncio
async def test_update_max_chat_id_ignores_none(db_session: AsyncSession):
    user = await create_user(db_session, max_user_id="none_user", max_chat_id="111")
    assert user.max_chat_id == "111"

    updated = await update_max_chat_id(db_session, user, None)
    assert updated.max_chat_id == "111"

    found = await get_user_by_max_id(db_session, "none_user")
    assert found is not None
    assert found.max_chat_id == "111"
