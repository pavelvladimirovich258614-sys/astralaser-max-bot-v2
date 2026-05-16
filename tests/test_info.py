from typing import Any

import pytest

from src.bot.handlers import info as info_handler
from src.bot.keyboards import contact_keyboard


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def edit_message(self, chat_id, message_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "edit_message", "chat_id": chat_id, "text": text, "reply_markup": reply_markup})

    async def send_message(self, chat_id, text, reply_markup=None, photo_url=None, photo=None):
        self.calls.append({"method": "send_message", "chat_id": chat_id, "text": text, "reply_markup": reply_markup})


@pytest.fixture(autouse=True)
def set_token(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "test_token")


@pytest.mark.asyncio
async def test_contact_screen_with_all_fields(monkeypatch):
    monkeypatch.setenv("MANAGER_PHONE", "+7 960 862 77 88")
    monkeypatch.setenv("MANAGER_VK_LINK", "https://vk.com/pk_astralazer")
    monkeypatch.setenv("MAX_MANAGER_LINK", "https://max.ru/msg/manager")
    monkeypatch.setenv("WORKING_HOURS", "пн–сб 10:00–18:00 МСК")
    monkeypatch.setenv("MAX_CHANNEL_LINK", "https://max.ru/id300400568340_biz")
    monkeypatch.setenv("OZON_LINK", "https://ozon.ru/s/astralaser")
    monkeypatch.setenv("WILDBERRIES_LINK", "https://www.wildberries.ru/brands/311460915-astralaser")

    client = FakeClient()
    await info_handler.show_contact(client, "chat1")

    assert len(client.calls) == 1
    text = client.calls[0]["text"]
    assert "Связаться с менеджером" in text
    assert "+7 960 862 77 88" in text
    assert "vk.com/pk_astralazer" in text
    assert "max.ru/msg/manager" in text
    assert "пн–сб 10:00–18:00 МСК" in text
    assert "напишите сообщение здесь" in text


@pytest.mark.asyncio
async def test_contact_screen_omits_empty_fields(monkeypatch):
    monkeypatch.setenv("MANAGER_PHONE", "")
    monkeypatch.setenv("MANAGER_VK_LINK", "")
    monkeypatch.setenv("MAX_MANAGER_LINK", "")
    monkeypatch.setenv("WORKING_HOURS", "")
    monkeypatch.setenv("MAX_CHANNEL_LINK", "")
    monkeypatch.setenv("OZON_LINK", "")
    monkeypatch.setenv("WILDBERRIES_LINK", "")

    text = info_handler._build_contact_text()
    assert "📱 Телефон" not in text
    assert "🌐 ВКонтакте" not in text
    assert "💬 MAX:" not in text
    assert "🕐 Рабочие часы" not in text
    assert "Наши площадки" not in text
    assert "Связаться с менеджером" in text
    assert "напишите сообщение здесь" in text


@pytest.mark.asyncio
async def test_contact_screen_uses_edit_when_message_id(monkeypatch):
    monkeypatch.setenv("MANAGER_PHONE", "+7 900 000 00 00")
    client = FakeClient()
    await info_handler.show_contact(client, "chat1", message_id="msg_1")

    assert len(client.calls) == 1
    assert client.calls[0]["method"] == "edit_message"
    assert "Связаться с менеджером" in client.calls[0]["text"]


@pytest.mark.asyncio
async def test_contact_screen_uses_send_without_message_id(monkeypatch):
    monkeypatch.setenv("MANAGER_PHONE", "+7 900 000 00 00")
    client = FakeClient()
    await info_handler.show_contact(client, "chat1")

    assert len(client.calls) == 1
    assert client.calls[0]["method"] == "send_message"


@pytest.mark.asyncio
async def test_help_screen_contains_commands():
    client = FakeClient()
    await info_handler.show_help(client, "chat1")

    assert len(client.calls) == 1
    text = client.calls[0]["text"]
    assert "❓ Помощь" in text
    assert "/start" in text
    assert "/catalog" in text
    assert "/cart" in text
    assert "/contact" in text
    assert "/help" in text


@pytest.mark.asyncio
async def test_help_screen_contains_order_steps():
    client = FakeClient()
    await info_handler.show_help(client, "chat1")

    text = client.calls[0]["text"]
    assert "Как сделать заказ" in text
    assert "корзину" in text
    assert "Оформить заказ" in text
    assert "анкету" in text
    assert "Подтвердите заказ" in text
    assert "Срок изготовления" in text
    assert "СДЭК" in text


@pytest.mark.asyncio
async def test_help_screen_uses_edit_when_message_id():
    client = FakeClient()
    await info_handler.show_help(client, "chat1", message_id="msg_1")

    assert len(client.calls) == 1
    assert client.calls[0]["method"] == "edit_message"


@pytest.mark.asyncio
async def test_help_keyboard_has_navigation():
    kb = info_handler.help_keyboard()
    payloads = [b["payload"] for row in kb for b in row]
    assert "home" in payloads
    assert "menu:catalog" in payloads


@pytest.mark.asyncio
async def test_contact_keyboard_always_has_home():
    kb = contact_keyboard()
    payloads = [b["payload"] for row in kb for b in row]
    assert "home" in payloads

    kb_empty = contact_keyboard(phone="", vk_link="", max_link="")
    payloads_empty = [b["payload"] for row in kb_empty for b in row]
    assert "home" in payloads_empty


@pytest.mark.asyncio
async def test_contact_screen_contains_marketplace_links(monkeypatch):
    monkeypatch.setenv("MANAGER_PHONE", "+7 900 000 00 00")
    monkeypatch.setenv("MANAGER_VK_LINK", "https://vk.com/pk_astralazer")
    monkeypatch.setenv("MAX_CHANNEL_LINK", "https://max.ru/id300400568340_biz")
    monkeypatch.setenv("OZON_LINK", "https://ozon.ru/s/astralaser")
    monkeypatch.setenv("WILDBERRIES_LINK", "https://www.wildberries.ru/brands/311460915-astralaser")

    text = info_handler._build_contact_text()
    assert "🌐 Наши площадки:" in text
    assert "• MAX: https://max.ru/id300400568340_biz" in text
    assert "• ВКонтакте: https://vk.com/pk_astralazer" in text
    assert "• Ozon: https://ozon.ru/s/astralaser" in text
    assert "• Wildberries: https://www.wildberries.ru/brands/311460915-astralaser" in text


@pytest.mark.asyncio
async def test_contact_screen_omits_empty_marketplace_links(monkeypatch):
    monkeypatch.setenv("MANAGER_PHONE", "+7 900 000 00 00")
    monkeypatch.setenv("MANAGER_VK_LINK", "")
    monkeypatch.setenv("MAX_CHANNEL_LINK", "https://max.ru/id300400568340_biz")
    monkeypatch.setenv("OZON_LINK", "")
    monkeypatch.setenv("WILDBERRIES_LINK", "")

    text = info_handler._build_contact_text()
    assert "🌐 Наши площадки:" in text
    assert "• MAX:" in text
    assert "• Ozon:" not in text
    assert "• Wildberries:" not in text
    assert "• ВКонтакте:" not in text
