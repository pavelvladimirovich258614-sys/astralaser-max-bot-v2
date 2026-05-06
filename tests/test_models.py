import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from src.db.models import Base, Category, Product, ProductPhoto


@pytest.fixture(scope="session")
def sync_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(sync_engine):
    session_local = sessionmaker(bind=sync_engine)
    session = session_local()
    yield session
    session.rollback()
    session.close()


def test_all_tables_exist(sync_engine):
    inspector = inspect(sync_engine)
    tables = inspector.get_table_names()
    expected = {"users", "categories", "products", "product_photos", "cart_items", "orders", "order_items", "user_states"}
    assert expected.issubset(set(tables))


def test_product_columns(sync_engine):
    inspector = inspect(sync_engine)
    columns = {col["name"] for col in inspector.get_columns("products")}
    assert {"id", "category_id", "title", "description", "price", "cover_url", "is_active", "sort_order", "created_at"}.issubset(columns)


def test_product_photo_cascade(db_session):
    # Создаём категорию и продукт
    category = Category(title="Test", slug="test", sort_order=1)
    db_session.add(category)
    db_session.commit()

    product = Product(category_id=category.id, title="Test Product", description="Desc", price=100, cover_url="url")
    db_session.add(product)
    db_session.commit()

    photo = ProductPhoto(product_id=product.id, url="http://example.com/photo.jpg", sort_order=0)
    db_session.add(photo)
    db_session.commit()

    # Удаляем продукт
    db_session.delete(product)
    db_session.commit()

    # Фото должно быть удалено каскадно
    result = db_session.query(ProductPhoto).filter_by(id=photo.id).first()
    assert result is None


def test_cart_item_unique_constraint(sync_engine):
    inspector = inspect(sync_engine)
    constraints = inspector.get_unique_constraints("cart_items")
    constraint_names = {c["name"] for c in constraints}
    assert "uix_user_product" in constraint_names


def test_user_state_columns(sync_engine):
    inspector = inspect(sync_engine)
    columns = {col["name"] for col in inspector.get_columns("user_states")}
    assert {"user_id", "state", "data", "updated_at"}.issubset(columns)
    # user_id — primary key
    pk = inspector.get_pk_constraint("user_states")
    assert "user_id" in pk["constrained_columns"]
