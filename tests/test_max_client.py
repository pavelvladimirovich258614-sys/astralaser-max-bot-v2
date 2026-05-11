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
async def test_edit_message_without_attachments_sends_empty_attachments(set_token):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message_id": "msg_1"})

    client = MAXClient(http_client=_make_transport(handler))
    await client.edit_message(chat_id=42, message_id="msg_1", text="Updated")
    await client.close()

    assert captured["body"]["text"] == "Updated"
    assert captured["body"]["attachments"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "expected_payload"),
    [
        ({"photo_url": "http://example.com/img.jpg"}, {"url": "http://example.com/img.jpg"}),
        ({"photo": {"token": "abc123"}}, {"token": "abc123"}),
    ],
)
async def test_edit_message_with_image_sends_image_attachment(set_token, kwargs, expected_payload):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message_id": "msg_1"})

    client = MAXClient(http_client=_make_transport(handler))
    await client.edit_message(chat_id=42, message_id="msg_1", text="Updated", **kwargs)
    await client.close()

    attachments = captured["body"]["attachments"]
    assert len(attachments) == 1
    assert attachments[0]["type"] == "image"
    assert attachments[0]["payload"] == expected_payload


@pytest.mark.asyncio
async def test_send_message_without_attachments_omits_attachments(set_token):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message_id": "123"})

    client = MAXClient(http_client=_make_transport(handler))
    await client.send_message(chat_id=42, text="Hello")
    await client.close()

    assert captured["body"] == {"text": "Hello"}


@pytest.mark.asyncio
async def test_delete_message(set_token, caplog):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"success": True})

    client = MAXClient(http_client=_make_transport(handler))
    with caplog.at_level("INFO"):
        result = await client.delete_message(chat_id=42, message_id="msg_1")
    await client.close()

    assert result is True
    assert captured["method"] == "DELETE"
    assert "/messages" in captured["url"]
    assert "message_id=msg_1" in captured["url"]
    assert "delete_message response status=200" in caplog.text


@pytest.mark.asyncio
async def test_delete_message_success_false_returns_false(set_token, caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": False, "message": "reason"})

    client = MAXClient(http_client=_make_transport(handler))
    with caplog.at_level("WARNING"):
        result = await client.delete_message(chat_id=42, message_id="msg_1")
    await client.close()

    assert result is False
    assert "delete_message success=false" in caplog.text


@pytest.mark.asyncio
async def test_delete_message_success_true_returns_true(set_token, caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True})

    client = MAXClient(http_client=_make_transport(handler))
    with caplog.at_level("INFO"):
        result = await client.delete_message(chat_id=42, message_id="msg_1")
    await client.close()

    assert result is True
    assert "delete_message response status=200" in caplog.text


@pytest.mark.asyncio
async def test_delete_message_4xx_returns_false(set_token, caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    client = MAXClient(http_client=_make_transport(handler))
    with caplog.at_level("WARNING"):
        result = await client.delete_message(chat_id=42, message_id="msg_1")
    await client.close()

    assert result is False
    assert "delete_message failed" in caplog.text


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
    result = await client.get_chat_member(chat_id=123456, user_id=789)
    await client.close()

    assert result is None


@pytest.mark.asyncio
async def test_set_bot_commands(set_token):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content) if request.content else {}
        return httpx.Response(200)

    client = MAXClient(http_client=_make_transport(handler))
    result = await client.set_bot_commands(
        [
            {"name": "start", "description": "Главное меню"},
            {"name": "help", "description": "Помощь"},
        ]
    )
    await client.close()

    assert result is True
    assert captured["method"] == "PATCH"
    assert "/me" in captured["url"]
    assert captured["body"]["commands"] == [
        {"name": "start", "description": "Главное меню"},
        {"name": "help", "description": "Помощь"},
    ]


@pytest.mark.asyncio
async def test_set_bot_commands_failure(set_token, caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Bad Request")

    client = MAXClient(http_client=_make_transport(handler))
    with caplog.at_level("WARNING"):
        result = await client.set_bot_commands([{"name": "start", "description": "Главное меню"}])
    await client.close()

    assert result is False
    assert "set_bot_commands failed" in caplog.text


@pytest.mark.asyncio
async def test_get_chat_member_uses_correct_endpoint(set_token):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        return httpx.Response(200, json={"members": [{"user_id": 789}], "marker": None})

    client = MAXClient(http_client=_make_transport(handler))
    result = await client.get_chat_member(chat_id=123456, user_id=789)
    await client.close()

    assert result is not None
    assert result["members"] == [{"user_id": 789}]
    assert captured["method"] == "GET"
    assert "/chats/123456/members" in captured["url"]
    assert "user_ids=789" in captured["url"]
