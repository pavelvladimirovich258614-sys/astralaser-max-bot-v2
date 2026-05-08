import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.bot.handlers import catalog as catalog_handler
from src.db.models import Base, Category, Product
from src.services import catalog_service
from src.services.catalog_service import ProductCardDTO


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


@pytest.mark.asyncio
async def test_show_category_single_product_shows_product_list(monkeypatch, async_engine, db_session):
    category = Category(title="Test Category", slug="test-category", sort_order=1)
    db_session.add(category)
    await db_session.flush()
    product = Product(
        category_id=category.id,
        title="Solo Product",
        description="Desc",
        price=100,
        cover_url="url",
        sort_order=1,
    )
    db_session.add(product)
    await db_session.commit()

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(catalog_handler, "async_session_maker", test_session_maker)

    async def fail_show_product_card(*args, **kwargs):
        raise AssertionError("show_category must render a list, not auto-open product card")

    monkeypatch.setattr(catalog_handler, "show_product_card", fail_show_product_card)

    class RecordingClient:
        def __init__(self):
            self.calls = []

        async def edit_message(self, chat_id, message_id, text, reply_markup=None, photo_url=None, photo=None):
            self.calls.append(
                {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                    "reply_markup": reply_markup,
                    "photo_url": photo_url,
                    "photo": photo,
                }
            )

    client = RecordingClient()
    await catalog_handler.show_category(client, chat_id=1, message_id="msg_1", slug="test-category")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert "✨ Выберите товар из списка" in call["text"]
    assert call["photo_url"] is None
    assert call["photo"] is None
    assert call["reply_markup"][0][0]["text"] == "1. Solo Product"
    assert call["reply_markup"][0][0]["payload"] == f"prod:{product.id}"


@pytest.mark.asyncio
async def test_show_product_card_short_description(monkeypatch):
    """Карточка показывает только заголовок, цену и первую строку описания."""

    class RecordingClient:
        def __init__(self):
            self.calls = []

        async def edit_message(self, chat_id, message_id, text, reply_markup=None, photo_url=None, photo=None):
            self.calls.append(
                {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                    "reply_markup": reply_markup,
                    "photo_url": photo_url,
                    "photo": photo,
                }
            )

    full_desc = (
        "Открывающийся кулон с секретным посланием внутри.\n"
        "Идеальный подарок дочке, маме, любимому человеку или подруге.\n\n"
        "✨ Особенности:\n"
        "- Гравировка всех 4 граней включена в цену\n"
        "- Ювелирная сталь — не темнеет, не ржавеет\n\n"
        "⏱ Срок изготовления: 1–2 рабочих дня\n"
        "📦 Доставка только СДЭК\n"
        "💝 Макет и гравировка — бесплатно"
    )

    async def mock_get_product_card(session, product_id, photo_index=0):
        return ProductCardDTO(
            title="Кулон-столбик",
            price=840,
            description=full_desc,
            photo_url="url",
            photo=None,
            photo_count=3,
            photo_index=0,
            category_slug="kole-i-kulony",
        )

    monkeypatch.setattr(catalog_service, "get_product_card", mock_get_product_card)

    client = RecordingClient()
    await catalog_handler.show_product_card(client, chat_id=1, message_id="msg_1", product_id=1)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert "Кулон-столбик" in call["text"]
    assert "💰 840 ₽" in call["text"]
    assert "Открывающийся кулон с секретным посланием внутри." in call["text"]
    assert "✨ Особенности" not in call["text"]
    assert "Срок" not in call["text"]
    assert "Доставка" not in call["text"]
