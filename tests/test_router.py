from typing import Any

import pytest

from src.bot.router import UpdateRouter


class FakeClient:
    """Минимальный мок MAXClient для router-тестов."""

    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    async def edit_message(self, chat_id, message_id, text, reply_markup=None, photo_url=None):
        self.calls.append({"method": "edit_message", "chat_id": chat_id, "text": text})

    async def send_message(self, chat_id, text, reply_markup=None, photo_url=None):
        self.calls.append({"method": "send_message", "chat_id": chat_id, "text": text})

    async def close(self):
        pass


@pytest.fixture(autouse=True)
def set_token(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "test_token")


@pytest.fixture
def router(set_token):
    client = FakeClient()
    return UpdateRouter(client), client


def _make_callback_payload(payload: str) -> dict[str, Any]:
    return {
        "update_type": "message_callback",
        "callback": {
            "callback_id": "cb_1",
            "user": {"user_id": "123"},
            "payload": payload,
        },
        "message": {
            "recipient": {"chat_id": "456"},
            "body": {"mid": "msg_1"},
        },
    }


@pytest.mark.asyncio
async def test_router_callback_catalog(router):
    r, client = router
    await r.process(_make_callback_payload("catalog"))
    assert any("edit_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_menu_catalog(router):
    r, client = router
    await r.process(_make_callback_payload("menu:catalog"))
    assert any("edit_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_home(router):
    r, client = router
    await r.process(_make_callback_payload("home"))
    assert any("edit_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_stub_menu_cart(router):
    r, client = router
    await r.process(_make_callback_payload("menu:cart"))
    assert any(c.get("text") == "🛒 Корзина — скоро." for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_cat_slug(router):
    r, client = router
    await r.process(_make_callback_payload("cat:kole-i-kulony"))
    # show_category вызывает edit_message (даже если товаров нет)
    assert any("edit_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_prod_id(router):
    r, client = router
    await r.process(_make_callback_payload("prod:1"))
    # show_product_card вызывает edit_message
    assert any("edit_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_photo_id_idx(router):
    r, client = router
    await r.process(_make_callback_payload("photo:1:2"))
    # show_product_card вызывает edit_message
    assert any("edit_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_callback_add_id(router):
    r, client = router
    await r.process(_make_callback_payload("add:1"))
    # add_to_cart создаёт пользователя и пытается добавить; при отсутствии продукта — всё равно edit_message
    assert any("edit_message" == c["method"] for c in client.calls)


@pytest.mark.asyncio
async def test_router_message_catalog_command(router):
    r, client = router
    payload = {
        "update_type": "message_created",
        "message": {
            "recipient": {"chat_id": "456"},
            "sender": {"user_id": "123"},
            "body": {"text": "/catalog"},
        },
    }
    await r.process(payload)
    assert any("send_message" == c["method"] for c in client.calls)
