from __future__ import annotations

import logging
import time
from collections import OrderedDict
from typing import Any

from src.bot.handlers import catalog as catalog_handler
from src.bot.handlers import start as start_handler
from src.bot.max_client import MAXClient

logger = logging.getLogger(__name__)


class UpdateRouter:
    def __init__(self, client: MAXClient) -> None:
        self.client = client
        self._callback_dedup: OrderedDict[tuple[str, str, str], float] = OrderedDict()
        self._dedup_ttl = 1.0
        self._dedup_max_size = 256

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
        elif text.startswith("/catalog"):
            await catalog_handler.show_catalog(self.client, chat_id)

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

        dedup_key = (str(user_id), str(message_id), str(data))
        now = time.monotonic()

        expired = [k for k, t in self._callback_dedup.items() if now - t > self._dedup_ttl]
        for k in expired:
            del self._callback_dedup[k]

        if dedup_key in self._callback_dedup:
            logger.debug("duplicate callback skipped: %s", dedup_key)
            return

        if len(self._callback_dedup) >= self._dedup_max_size:
            self._callback_dedup.popitem(last=False)

        self._callback_dedup[dedup_key] = now

        if data == "consent:accept":
            await start_handler.handle_consent_accept(self.client, chat_id, user_id, message_id)
            return

        if data == "catalog" or data == "menu:catalog":
            await catalog_handler.show_catalog(self.client, chat_id, message_id)
            return

        if data == "home":
            await start_handler.show_main_menu(self.client, chat_id, message_id)
            return

        # Заглушки для не реализованных разделов главного меню
        if data in ("menu:cart", "menu:orders", "menu:help", "menu:contact"):
            stub_text = {
                "menu:cart": "🛒 Корзина — скоро.",
                "menu:orders": "📦 Мои заказы — скоро.",
                "menu:help": "❓ Помощь — скоро.",
                "menu:contact": "💬 Менеджер — скоро.",
            }.get(data, "Раздел в разработке.")
            await self.client.edit_message(chat_id, message_id, stub_text)
            return

        # callback patterns с аргументами
        parts = data.split(":")
        if len(parts) < 2:
            return

        cmd = parts[0]

        if cmd == "cat" and len(parts) == 2:
            slug = parts[1]
            await catalog_handler.show_category(self.client, chat_id, message_id, slug)
            return

        if cmd == "prod" and len(parts) == 2:
            try:
                product_id = int(parts[1])
            except ValueError:
                return
            await catalog_handler.show_product_card(self.client, chat_id, message_id, product_id)
            return

        if cmd == "photo" and len(parts) == 3:
            try:
                product_id = int(parts[1])
                photo_index = int(parts[2])
            except ValueError:
                return
            await catalog_handler.show_product_card(self.client, chat_id, message_id, product_id, photo_index)
            return

        if cmd == "add" and len(parts) == 2:
            try:
                product_id = int(parts[1])
            except ValueError:
                return
            await catalog_handler.add_to_cart(self.client, chat_id, user_id, message_id, product_id)
            return
