import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.bot.handlers import start
from src.bot.keyboards import consent_keyboard, main_menu_inline_keyboard
from src.db.models import Base


class RecordingClient:
    """Мок MAXClient, который запоминает все вызовы."""

    def __init__(self):
        self.calls: list[dict] = []

    async def send_message(self, chat_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({
            "method": "send_message",
            "chat_id": chat_id,
            "text": text,
            "reply_markup": reply_markup,
            "photo_url": photo_url,
            "photo": photo,
        })
        return {}

    async def edit_message(self, chat_id, message_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({
            "method": "edit_message",
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "reply_markup": reply_markup,
            "photo_url": photo_url,
            "photo": photo,
        })
        return {}

    async def delete_message(self, chat_id, message_id):
        self.calls.append({
            "method": "delete_message",
            "chat_id": chat_id,
            "message_id": message_id,
        })
        return True

    async def answer_callback_query(self, callback_id, notification=None, message=None):
        self.calls.append({"method": "answer_callback_query", "callback_id": callback_id, "notification": notification, "message": message})
        return True


@pytest.fixture(autouse=True)
def set_token(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "test_token")


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


@pytest.fixture
async def override_session_maker(monkeypatch, async_engine):
    """Переопределяет async_session_maker в handlers/start.py для тестов."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_maker = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(start, "async_session_maker", test_session_maker)

    yield

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_start_new_user_shows_privacy(override_session_maker):
    client = RecordingClient()
    await start.handle_start(client, chat_id=1, user_id=100, user_info={"name": "Test"})

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "send_message"
    assert "🔒 Перед тем как продолжить" in call["text"]
    assert call["reply_markup"] == consent_keyboard()
    assert call["photo_url"] is None


@pytest.mark.asyncio
async def test_start_existing_user_with_consent_shows_menu(override_session_maker):
    client = RecordingClient()
    # Первый /start — создание пользователя
    await start.handle_start(client, chat_id=1, user_id=101, user_info={"name": "Test"})
    # Принимаем согласие
    await start.handle_consent_accept(client, chat_id=1, user_id=101, message_id="msg_1")
    client.calls.clear()

    # Второй /start — показываем меню
    await start.handle_start(client, chat_id=1, user_id=101, user_info={"name": "Test"})

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "send_message"
    assert "🌟 Astralaser" in call["text"]
    assert call["reply_markup"] == main_menu_inline_keyboard()
    assert call["photo_url"] == start.MAIN_MENU_PHOTO


@pytest.mark.asyncio
async def test_consent_accept_records_and_shows_menu(override_session_maker):
    client = RecordingClient()
    # Создаём пользователя
    await start.handle_start(client, chat_id=1, user_id=102, user_info={"name": "Test"})
    client.calls.clear()

    # Нажимаем "Принимаю"
    await start.handle_consent_accept(client, chat_id=1, user_id=102, message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert "🌟 Astralaser" in call["text"]
    assert call["reply_markup"] == main_menu_inline_keyboard()
    assert call["photo_url"] == start.MAIN_MENU_PHOTO



@pytest.mark.asyncio
async def test_main_menu_caption_no_url_in_text(override_session_maker):
    """Главное меню: caption НЕ содержит URL картинки внутри текста."""
    client = RecordingClient()
    # Создаём и соглашаем
    await start.handle_start(client, chat_id=1, user_id=103, user_info={"name": "Test"})
    await start.handle_consent_accept(client, chat_id=1, user_id=103, message_id="msg_1")
    client.calls.clear()

    # Стартуем снова — меню
    await start.handle_start(client, chat_id=1, user_id=103, user_info={"name": "Test"})

    call = client.calls[0]
    assert "postimg.cc" not in call["text"]
    assert "https://" not in call["text"]
    assert call["photo_url"] == start.MAIN_MENU_PHOTO


@pytest.mark.asyncio
async def test_show_main_menu_delete_and_send_when_flag_enabled(monkeypatch):
    """При USE_PHOTO_URL_IN_EDIT=1 show_main_menu использует delete_message + send_message."""
    monkeypatch.setattr(start, "_USE_PHOTO_URL_IN_EDIT", True)

    client = RecordingClient()
    await start.show_main_menu(client, chat_id=1, message_id="msg_1")

    assert len(client.calls) == 2
    assert client.calls[0]["method"] == "delete_message"
    assert client.calls[0]["message_id"] == "msg_1"

    assert client.calls[1]["method"] == "send_message"
    assert "🌟 Astralaser" in client.calls[1]["text"]
    assert client.calls[1]["reply_markup"] == main_menu_inline_keyboard()
    assert client.calls[1]["photo_url"] == start.MAIN_MENU_PHOTO


@pytest.mark.asyncio
async def test_show_main_menu_edit_message_when_flag_disabled(monkeypatch):
    """При USE_PHOTO_URL_IN_EDIT=0 show_main_menu использует edit_message."""
    monkeypatch.setattr(start, "_USE_PHOTO_URL_IN_EDIT", False)

    client = RecordingClient()
    await start.show_main_menu(client, chat_id=1, message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert call["message_id"] == "msg_1"
    assert "🌟 Astralaser" in call["text"]
    assert call["reply_markup"] == main_menu_inline_keyboard()
    assert call["photo_url"] == start.MAIN_MENU_PHOTO
