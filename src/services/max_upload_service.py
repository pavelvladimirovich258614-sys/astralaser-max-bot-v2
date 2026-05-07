from __future__ import annotations

import logging
from typing import Any, cast

import httpx

from src.bot.max_client import MAXClient

logger = logging.getLogger(__name__)


async def upload_image_from_url(client: MAXClient, source_url: str) -> str | None:
    """Загружает изображение из внешнего URL в MAX API.
    Возвращает token или None при ошибке.
    """
    # Шаг 1: получить upload URL
    upload_url = await client.get_image_upload_url()
    if not upload_url:
        logger.warning("No upload URL received from MAX")
        return None

    # Шаг 2: скачать исходное фото
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            download = await http.get(source_url)
            download.raise_for_status()
            image_bytes = download.content
    except httpx.HTTPStatusError as e:
        logger.warning("Failed to download image from %s: status=%s", source_url, e.response.status_code)
        return None
    except httpx.RequestError as e:
        logger.warning("Request error downloading image from %s: %s", source_url, e)
        return None

    # Шаг 3: загрузить на upload URL
    try:
        async with httpx.AsyncClient(timeout=60) as http:
            files = {"data": ("image", image_bytes, "application/octet-stream")}
            upload = await http.post(upload_url, files=files)
            upload.raise_for_status()
            data = cast(dict[str, Any], upload.json())
            photos = data.get("photos")
            if not isinstance(photos, dict) or not photos:
                logger.warning("Upload response missing photos: %s", data)
                return None
            # Берём первое (и единственное) значение из словаря photos
            first_photo = next(iter(photos.values()))
            token = first_photo.get("token") if isinstance(first_photo, dict) else None
            if not token:
                logger.warning("Upload response missing token: %s", data)
                return None
            return str(token)
    except httpx.HTTPStatusError as e:
        logger.warning("Upload failed: status=%s body=%s", e.response.status_code, e.response.text)
        return None
    except httpx.RequestError as e:
        logger.warning("Upload request error: %s", e)
        return None
