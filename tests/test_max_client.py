import json
from typing import Any

import httpx
import pytest

from src.bot.max_client import MAXClient


@pytest.fixture(autouse=True)
def set_token(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "test_token")
    monkeypatch.setenv("MAX_API_BASE_URL", "https://test-api.max.ru")


def _make_transport(handler: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://test-api.max.ru",
    )


@pytest.mark.asyncio
async def test_authorization_header(set_token):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"ok": True})

    client = MAXClient(http_client=_make_transport(handler))
    await client.send_message(chat_id=1, text="test")
    await client.close()

    assert captured.get("auth") == "test_token"


@pytest.mark.asyncio
async def test_send_message_payload(set_token):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message_id": "123"})

    client = MAXClient(http_client=_make_transport(handler))
    result = await client.send_message(
        chat_id=42,
        text="Hello",
        reply_markup=[[{"text": "OK", "callback_data": "ok"}]],
        photo_url="http://example.com/img.jpg",
    )
    await client.close()

    assert result == {"message_id": "123"}
    assert captured["body"]["text"] == "Hello"
    attachments = captured["body"]["attachments"]
    assert len(attachments) == 2
    assert attachments[0]["type"] == "image"
    assert attachments[0]["payload"]["url"] == "http://example.com/img.jpg"
    assert attachments[1]["type"] == "inline_keyboard"


@pytest.mark.asyncio
async def test_send_message_with_photo_token(set_token):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message_id": "123"})

    client = MAXClient(http_client=_make_transport(handler))
    result = await client.send_message(
        chat_id=42,
        text="Hello",
        photo={"token": "abc123"},
    )
    await client.close()

    assert result == {"message_id": "123"}
    attachments = captured["body"]["attachments"]
    assert len(attachments) == 1
    assert attachments[0]["type"] == "image"
    assert attachments[0]["payload"]["token"] == "abc123"


@pytest.mark.asyncio
async def test_send_message_4xx_logs_warning(set_token, caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Bad Request")

    client = MAXClient(http_client=_make_transport(handler))
    with caplog.at_level("WARNING"):
        result = await client.send_message(chat_id=42, text="Hello")
    await client.close()

    assert result == {}
    assert "send_message failed" in caplog.text


@pytest.mark.asyncio
async def test_edit_message(set_token):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"message_id": "msg_1"})

    client = MAXClient(http_client=_make_transport(handler))
    result = await client.edit_message(chat_id=42, message_id="msg_1", text="Updated")
    await client.close()

    assert result == {"message_id": "msg_1"}
    assert captured["method"] == "PUT"
    assert "/messages" in captured["url"]
    assert "message_id=msg_1" in captured["url"]


@pytest.mark.asyncio
async def test_delete_message(set_token):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        return httpx.Response(200)

    client = MAXClient(http_client=_make_transport(handler))
    result = await client.delete_message(chat_id=42, message_id="msg_1")
    await client.close()

    assert result is True
    assert captured["method"] == "DELETE"
    assert "/messages/msg_1" in captured["url"]


@pytest.mark.asyncio
async def test_answer_callback_query(set_token):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content) if request.content else {}
        return httpx.Response(200)

    client = MAXClient(http_client=_make_transport(handler))
    result = await client.answer_callback_query(callback_id="cb_1", notification="Done")
    await client.close()

    assert result is True
    assert captured["method"] == "POST"
    assert "/answers" in captured["url"]
    assert captured["body"]["notification"] == "Done"


@pytest.mark.asyncio
async def test_answer_callback_query_no_payload_skips_request(set_token):
    """Если notification и message не переданы — запрос не уходит."""
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200)

    client = MAXClient(http_client=_make_transport(handler))
    result = await client.answer_callback_query(callback_id="cb_1")
    await client.close()

    assert result is None
    assert request_count == 0


@pytest.mark.asyncio
async def test_subscribe_webhook(set_token):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content) if request.content else {}
        return httpx.Response(200)

    client = MAXClient(http_client=_make_transport(handler))
    result = await client.subscribe_webhook("https://example.com/webhook")
    await client.close()

    assert result is True
    assert captured["method"] == "POST"
    assert "/subscriptions" in captured["url"]
    assert captured["body"]["url"] == "https://example.com/webhook"


@pytest.mark.asyncio
async def test_get_chat_member_404_returns_none(set_token):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = MAXClient(http_client=_make_transport(handler))
    result = await client.get_chat_member(chat_id="@channel", user_id=123)
    await client.close()

    assert result is None
