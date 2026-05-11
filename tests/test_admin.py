from typing import Any

import pytest

from src.bot.handlers import admin as admin_handler
from src.bot.handlers import start as start_handler
from src.bot.keyboards import admin_menu_keyboard


class RecordingClient:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    async def edit_message(self, chat_id, message_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "edit_message", "chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": reply_markup})

    async def send_message(self, chat_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "send_message", "chat_id": chat_id, "text": text, "reply_markup": reply_markup})


@pytest.fixture(autouse=True)
def set_token(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "test_token")


def _make_settings(admin_ids: list[str]):
    return type("S", (), {"admin_ids_list": admin_ids})()


# ---------------------------------------------------------------------------
# Access tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_access_denied_for_regular_user(monkeypatch):
    """Обычный пользователь получает 'Команда не найдена.' при /admin."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()
    await admin_handler.handle_admin_command(client, chat_id=1, user_id="99999")

    assert len(client.calls) == 1
    assert client.calls[0]["method"] == "send_message"
    assert "Команда не найдена" in client.calls[0]["text"]


@pytest.mark.asyncio
async def test_admin_access_granted_for_admin(monkeypatch):
    """Админ получает экран '🛠 Админ-панель'."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()
    await admin_handler.handle_admin_command(client, chat_id=1, user_id="4147438")

    assert len(client.calls) == 1
    assert client.calls[0]["method"] == "send_message"
    assert "🛠 Админ-панель" in client.calls[0]["text"]
    assert client.calls[0]["reply_markup"] == admin_menu_keyboard()


# ---------------------------------------------------------------------------
# Menu keyboard test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_menu_has_all_buttons():
    """Клавиатура содержит все 6 кнопок с правильными payload."""
    kb = admin_menu_keyboard()
    payloads = [b["payload"] for row in kb for b in row]
    assert "admin:orders" in payloads
    assert "admin:products" in payloads
    assert "admin:categories" in payloads
    assert "admin:stats" in payloads
    assert "admin:broadcast" in payloads
    assert "admin:exit" in payloads


# ---------------------------------------------------------------------------
# Skeleton callback tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_skeleton_callbacks_require_admin_access(monkeypatch):
    """Обычный пользователь не видит placeholder при admin:* callback."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()
    await admin_handler.admin_orders(client, chat_id=1, user_id="99999", message_id="msg_1")
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_admin_skeleton_callbacks_show_placeholders(monkeypatch):
    """Админ видит placeholder-экраны для всех skeleton callbacks."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()

    await admin_handler.admin_orders(client, chat_id=1, user_id="4147438", message_id="msg_1")
    assert any("📦 Заказы" in c["text"] for c in client.calls)

    await admin_handler.admin_products(client, chat_id=1, user_id="4147438", message_id="msg_1")
    assert any("📚 Товары" in c["text"] for c in client.calls)

    await admin_handler.admin_categories(client, chat_id=1, user_id="4147438", message_id="msg_1")
    assert any("🏷 Категории" in c["text"] for c in client.calls)

    await admin_handler.admin_stats(client, chat_id=1, user_id="4147438", message_id="msg_1")
    assert any("📊 Статистика" in c["text"] for c in client.calls)

    await admin_handler.admin_broadcast(client, chat_id=1, user_id="4147438", message_id="msg_1")
    assert any("📤 Рассылка" in c["text"] for c in client.calls)


# ---------------------------------------------------------------------------
# Exit test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_exit_returns_to_main_menu(monkeypatch):
    """admin:exit вызывает show_main_menu."""
    calls = []

    async def fake_show_main_menu(client, chat_id, message_id=None):
        calls.append({"method": "show_main_menu", "chat_id": chat_id, "message_id": message_id})

    monkeypatch.setattr(start_handler, "show_main_menu", fake_show_main_menu)
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()

    await admin_handler.admin_exit(client, chat_id=1, user_id="4147438", message_id="msg_1")

    assert len(calls) == 1
    assert calls[0]["method"] == "show_main_menu"
    assert calls[0]["chat_id"] == 1
    assert calls[0]["message_id"] == "msg_1"


# ---------------------------------------------------------------------------
# _is_admin edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_admin_numeric_string_match(monkeypatch):
    """_is_admin корректно сравнивает numeric user_id как строку."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438", "73412011"]))
    assert admin_handler._is_admin(4147438) is True
    assert admin_handler._is_admin("4147438") is True
    assert admin_handler._is_admin("73412011") is True
    assert admin_handler._is_admin("99999") is False
    assert admin_handler._is_admin(99999) is False


@pytest.mark.asyncio
async def test_admin_placeholder_back_returns_to_menu(monkeypatch):
    """admin:back возвращает в меню админ-панели через edit_message."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()
    await admin_handler.admin_back_to_menu(client, chat_id=1, user_id="4147438", message_id="msg_1")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["method"] == "edit_message"
    assert "🛠 Админ-панель" in call["text"]
    assert call["reply_markup"] == admin_menu_keyboard()


@pytest.mark.asyncio
async def test_admin_back_to_menu_denied_for_regular_user(monkeypatch):
    """Обычный пользователь не может использовать admin:back."""
    monkeypatch.setattr(admin_handler, "get_settings", lambda: _make_settings(["4147438"]))
    client = RecordingClient()
    await admin_handler.admin_back_to_menu(client, chat_id=1, user_id="99999", message_id="msg_1")
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_admin_back_keyboard_payload():
    """admin_back_keyboard использует payload admin:back."""
    from src.bot.keyboards import admin_back_keyboard
    kb = admin_back_keyboard()
    payloads = [b["payload"] for row in kb for b in row]
    assert "admin:back" in payloads
    assert "admin:exit" not in payloads
