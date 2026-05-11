from __future__ import annotations

import logging
from typing import Any, cast

import httpx

from src.config import get_settings

logger = logging.getLogger(__name__)


class MAXClient:
    """HTTP клиент MAX API. Использует Authorization header (НЕ access_token в URL)."""

    def __init__(
        self,
        token: str | None = None,
        *,
        base_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ):
        settings = get_settings()
        self._token = token or settings.max_bot_token
        self._base_url = (base_url or settings.max_api_base_url).rstrip("/")
        if not self._token:
            raise RuntimeError("MAX_BOT_TOKEN must be set")

        self._owns_client = http_client is None
        if http_client:
            self._client = http_client
            self._client.headers["Authorization"] = self._token
        else:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": self._token},
                timeout=settings.http_timeout,
            )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> MAXClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # ---- helpers ----

    @staticmethod
    def _build_inline_keyboard(buttons: list[list[dict[str, Any]]]) -> dict[str, Any]:
        """buttons = [[{"text": "...", "callback_data": "..."}], ...]"""
        return {
            "type": "inline_keyboard",
            "payload": {"buttons": buttons},
        }

    def _build_payload(
        self,
        text: str,
        reply_markup: list[list[dict[str, Any]]] | None,
        photo_url: str | None,
        photo: dict[str, Any] | None = None,
        force_attachments: bool = False,
    ) -> dict[str, Any]:
        attachments: list[dict[str, Any]] = []
        if photo:
            attachments.append({"type": "image", "payload": photo})
        elif photo_url:
            attachments.append({"type": "image", "payload": {"url": photo_url}})
        if reply_markup:
            attachments.append(self._build_inline_keyboard(reply_markup))

        payload: dict[str, Any] = {"text": text}
        if attachments or force_attachments:
            payload["attachments"] = attachments
        return payload

    # ---- methods ----

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: list[list[dict[str, Any]]] | None = None,
        photo_url: str | None = None,
        photo: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            r = await self._client.post(
                "/messages",
                params={"chat_id": chat_id},
                json=self._build_payload(text, reply_markup, photo_url, photo),
            )
            r.raise_for_status()
            return cast(dict[str, Any], r.json())
        except httpx.HTTPStatusError as e:
            logger.warning("send_message failed: status=%s body=%s", e.response.status_code, e.response.text)
            return {}

    async def edit_message(
        self,
        chat_id: int | str,
        message_id: str,
        text: str,
        reply_markup: list[list[dict[str, Any]]] | None = None,
        photo_url: str | None = None,
        photo: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            r = await self._client.put(
                "/messages",
                params={"message_id": message_id},
                json=self._build_payload(text, reply_markup, photo_url, photo, force_attachments=True),
            )
            r.raise_for_status()
            return cast(dict[str, Any], r.json())
        except httpx.HTTPStatusError as e:
            logger.warning("edit_message failed: status=%s body=%s", e.response.status_code, e.response.text)
            return {}

    async def delete_message(self, chat_id: int | str, message_id: str) -> bool:
        logger.info("delete_message request message_id=%s chat_id=%s", message_id, chat_id)
        try:
            r = await self._client.delete(
                "/messages",
                params={"message_id": message_id},
            )
            body = r.text
            logger.info("delete_message response status=%s body=%s", r.status_code, body)
            r.raise_for_status()
            try:
                data = r.json()
            except Exception:
                logger.info("delete_message non-JSON success body=%s", body)
                return True
            if isinstance(data, dict) and "success" in data:
                if data["success"] is False:
                    logger.warning("delete_message success=false body=%s", body)
                    return False
                return True
            return True
        except httpx.HTTPStatusError as e:
            logger.warning("delete_message failed: status=%s body=%s", e.response.status_code, e.response.text)
            return False

    async def answer_callback_query(
        self,
        callback_id: str,
        notification: str | None = None,
        message: dict[str, Any] | None = None,
    ) -> bool | None:
        body: dict[str, Any] = {}
        if notification:
            body["notification"] = notification
        if message:
            body["message"] = message
        if not body:
            return None

        try:
            r = await self._client.post(
                "/answers",
                params={"callback_id": callback_id},
                json=body,
            )
            r.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.warning("answer_callback_query failed: status=%s", e.response.status_code)
            return False

    async def subscribe_webhook(self, url: str) -> bool:
        try:
            r = await self._client.post("/subscriptions", json={"url": url})
            r.raise_for_status()
            logger.info("Webhook subscribed: %s", url)
            return True
        except httpx.HTTPStatusError as e:
            logger.error("subscribe_webhook failed: status=%s body=%s", e.response.status_code, e.response.text)
            return False

    async def unsubscribe_webhook(self, url: str) -> bool:
        try:
            r = await self._client.delete("/subscriptions", params={"url": url})
            r.raise_for_status()
            return True
        except httpx.HTTPStatusError:
            return False

    async def get_chat_member(self, chat_id: int | str, user_id: int | str) -> dict[str, Any] | None:
        try:
            r = await self._client.get(f"/chats/{chat_id}/members", params={"user_ids": str(user_id)})
            r.raise_for_status()
            return cast(dict[str, Any], r.json())
        except httpx.HTTPStatusError:
            return None

    async def set_bot_commands(self, commands: list[dict[str, str]]) -> bool:
        """Регистрация slash-команд бота через PATCH /me."""
        try:
            r = await self._client.patch("/me", json={"commands": commands})
            r.raise_for_status()
            logger.info("Bot commands registered: %d commands", len(commands))
            return True
        except httpx.HTTPStatusError as e:
            logger.warning("set_bot_commands failed: status=%s body=%s", e.response.status_code, e.response.text)
            return False

    async def get_image_upload_url(self) -> str | None:
        try:
            r = await self._client.post("/uploads", params={"type": "image"})
            r.raise_for_status()
            data = cast(dict[str, Any], r.json())
            return data.get("url")
        except httpx.HTTPStatusError as e:
            logger.warning("get_image_upload_url failed: status=%s body=%s", e.response.status_code, e.response.text)
            return None
