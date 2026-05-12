import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.models import Base
from src.services import user_service


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
async def test_get_or_create_user_creates_with_max_chat_id(db_session: AsyncSession):
    user = await user_service.get_or_create_user(db_session, max_user_id="new_user", max_chat_id="chat_1")
    assert user.id is not None
    assert user.max_user_id == "new_user"
    assert user.max_chat_id == "chat_1"


@pytest.mark.asyncio
async def test_get_or_create_user_updates_existing_user_chat_id(db_session: AsyncSession):
    user = await user_service.get_or_create_user(db_session, max_user_id="exist_user")
    assert user.max_chat_id is None

    same = await user_service.get_or_create_user(db_session, max_user_id="exist_user", max_chat_id="chat_2")
    assert same.id == user.id
    assert same.max_chat_id == "chat_2"


@pytest.mark.asyncio
async def test_get_or_create_user_leaves_chat_id_unchanged_if_same(db_session: AsyncSession):
    user = await user_service.get_or_create_user(db_session, max_user_id="same_user", max_chat_id="chat_3")
    assert user.max_chat_id == "chat_3"

    same = await user_service.get_or_create_user(db_session, max_user_id="same_user", max_chat_id="chat_3")
    assert same.id == user.id
    assert same.max_chat_id == "chat_3"


@pytest.mark.asyncio
async def test_get_or_create_user_without_chat_id_does_not_clear_existing(db_session: AsyncSession):
    user = await user_service.get_or_create_user(db_session, max_user_id="keep_user", max_chat_id="chat_4")
    assert user.max_chat_id == "chat_4"

    same = await user_service.get_or_create_user(db_session, max_user_id="keep_user")
    assert same.id == user.id
    assert same.max_chat_id == "chat_4"
