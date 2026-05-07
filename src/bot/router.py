from __future__ import annotations

import logging
from typing import Any

from src.bot.handlers import start as start_handler
from src.bot.max_client import MAXClient

logger = logging.getLogger(__name__)


class UpdateRouter:
    def __init__(self, client: MAXClient) -> None:
        self.client = client

    async def process(self, payload: dict[str, Any]) -> None:
        try:
            update_type = payload.get("update_type", "")

            if update_type == "message_created":
                await self._handle_message(payload)
            elif update_type == "message_callback":
                await self._handle_callback(payload)
            else:
                logger.debug("ignored update type: %s", update_type)
        except Exception:
            logger.exception("error processing update")

    async def _handle_message(self, payload: dict[str, Any]) -> None:
        msg = payload.get("message", {})
        chat_id = msg.get("recipient", {}).get("chat_id") or msg.get("chat_id")
        user = msg.get("sender", {})
        user_id = user.get("user_id") or user.get("id")
        text = msg.get("body", {}).get("text", "")

        if not chat_id or not user_id:
            return

        if text.startswith("/start"):
            await start_handler.handle_start(self.client, chat_id, user_id, user)

    async def _handle_callback(self, payload: dict[str, Any]) -> None:
        cb = payload.get("callback", {})
        msg = payload.get("message", {})
        callback_id = cb.get("callback_id")
        chat_id = msg.get("recipient", {}).get("chat_id")
        message_id = msg.get("body", {}).get("mid")
        user_id = cb.get("user", {}).get("user_id")
        data = cb.get("payload", "")

        if not callback_id or not chat_id or not user_id:
            return

        if data == "consent:accept":
            await start_handler.handle_consent_accept(self.client, chat_id, user_id, message_id)
