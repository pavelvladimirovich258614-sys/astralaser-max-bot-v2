import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.models import Base
from src.services import catalog_service


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


@pytest.mark.asyncio
async def test_get_categories_with_count_empty(db_session):
    cats = await catalog_service.get_categories_with_count(db_session)
    assert cats == []


@pytest.mark.asyncio
async def test_get_product_card_not_found(db_session):
    card = await catalog_service.get_product_card(db_session, product_id=999)
    assert card is None


@pytest.mark.asyncio
async def test_get_products_by_slug_unknown(db_session):
    prods = await catalog_service.get_products_by_slug(db_session, "unknown")
    assert prods == []
