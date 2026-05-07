from typing import Any

import httpx
import pytest

from src.bot.max_client import MAXClient
from src.services import max_upload_service


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
async def test_get_image_upload_url(set_token):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"url": "https://upload.max.ru/123"})

    client = MAXClient(http_client=_make_transport(handler))
    url = await client.get_image_upload_url()
    await client.close()

    assert url == "https://upload.max.ru/123"
    assert "/uploads" in captured["url"]


@pytest.mark.asyncio
async def test_upload_image_from_url_download_failure(set_token):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/uploads":
            return httpx.Response(200, json={"url": "https://upload.max.ru/123"})
        return httpx.Response(404)

    client = MAXClient(http_client=_make_transport(handler))
    result = await max_upload_service.upload_image_from_url(client, "https://example.com/nonexistent.jpg")
    await client.close()

    assert result is None


@pytest.mark.asyncio
async def test_upload_image_from_url_upload_failure(set_token):
    """Если upload URL не возвращается — возвращается None."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = MAXClient(http_client=_make_transport(handler))
    result = await max_upload_service.upload_image_from_url(client, "https://example.com/img.jpg")
    await client.close()

    assert result is None
