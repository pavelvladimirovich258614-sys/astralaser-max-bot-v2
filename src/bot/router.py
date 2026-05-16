from __future__ import annotations

import logging
import time
from collections import OrderedDict
from typing import Any

from src.bot.handlers import admin as admin_handler
from src.bot.handlers import cart as cart_handler
from src.bot.handlers import catalog as catalog_handler
from src.bot.handlers import info as info_handler
from src.bot.handlers import order as order_handler
from src.bot.handlers import start as start_handler
from src.bot.handlers import subscription as subscription_handler
from src.bot.keyboards import main_menu_inline_keyboard
from src.bot.max_client import MAXClient
from src.db.engine import async_session_maker
from src.services import fsm_service, user_service

logger = logging.getLogger(__name__)

GALLERY_WORKS_PLACEHOLDER_TEXT = (
    "✨ Раздел с нашими работами сейчас находится в разработке. "
    "Совсем скоро мы представим вам лучшие примеры гравировок!"
)


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
            elif update_type == "bot_started":
                await self._handle_bot_started(payload)
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
        message_id = msg.get("body", {}).get("mid")

        if not chat_id or not user_id:
            return

        # Проверить FSM-состояние перед обычными командами
        async with async_session_maker() as session:
            user_obj = await user_service.get_or_create_user(session, max_user_id=str(user_id), max_chat_id=str(chat_id))
            await session.commit()
            state, _ = await fsm_service.get_state(session, user_obj.id)

        if fsm_service.is_order_state(state):
            handled = await order_handler.handle_fsm_message(
                self.client, chat_id, user_id, message_id, text
            )
            if handled:
                return

        if fsm_service.is_admin_state(state):
            handled = await admin_handler.handle_admin_fsm_message(
                self.client, chat_id, user_id, message_id, text
            )
            if handled:
                return

        if text.startswith("/start"):
            await start_handler.handle_start(self.client, chat_id, user_id, user)
        elif text.startswith("/catalog"):
            await catalog_handler.show_catalog(self.client, chat_id)
        elif text.startswith("/cart"):
            await cart_handler.show_cart(self.client, chat_id, user_id)
        elif text.startswith("/contact"):
            await info_handler.show_contact(self.client, chat_id)
        elif text.startswith("/help"):
            await info_handler.show_help(self.client, chat_id)
        elif text.startswith("/admin"):
            await admin_handler.handle_admin_command(self.client, chat_id, user_id, user)
            return

    async def _handle_bot_started(self, payload: dict[str, Any]) -> None:
        """Обработка события 'Начать' в MAX (bot_started)."""
        user = payload.get("user", {})
        user_id = payload.get("user_id") or user.get("user_id") or user.get("id")
        chat_id = payload.get("chat_id")
        if not chat_id or not user_id:
            logger.warning("bot_started missing user_id or chat_id")
            return

        # Сохранить dialog chat_id для рассылки (F10.5.2d)
        async with async_session_maker() as session:
            await user_service.get_or_create_user(session, max_user_id=str(user_id), max_chat_id=str(chat_id))
            await session.commit()

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

        # Сохранить dialog chat_id для рассылки (F10.5.2d)
        async with async_session_maker() as session:
            await user_service.get_or_create_user(session, max_user_id=str(user_id), max_chat_id=str(chat_id))
            await session.commit()

        if data == "consent:accept":
            await start_handler.handle_consent_accept(self.client, chat_id, user_id, message_id)
            return

        if data == "instruction:close":
            await self.client.delete_message(chat_id, message_id)
            return

        if data == "catalog" or data == "menu:catalog":
            await catalog_handler.show_catalog(self.client, chat_id, message_id)
            return

        if data == "home":
            await start_handler.show_main_menu(self.client, chat_id, message_id)
            return

        if data == "menu:cart":
            await cart_handler.show_cart(self.client, chat_id, user_id, message_id)
            return

        if data == "menu:contact":
            await info_handler.show_contact(self.client, chat_id, message_id)
            return

        if data == "menu:help":
            await info_handler.show_help(self.client, chat_id, message_id)
            return

        if data == "menu:orders":
            await order_handler.show_my_orders(self.client, chat_id, user_id, message_id)
            return

        if data == "gallery_works":
            await self.client.edit_message(
                chat_id,
                message_id,
                GALLERY_WORKS_PLACEHOLDER_TEXT,
                reply_markup=main_menu_inline_keyboard(),
            )
            return

        if data == "sub:check":
            await subscription_handler.check_subscription(self.client, chat_id, user_id, message_id)
            return

        if data == "checkout":
            await order_handler.start_checkout(self.client, chat_id, user_id, message_id)
            return

        if data == "order:cancel":
            await order_handler.cancel_checkout(self.client, chat_id, user_id, message_id)
            return

        if data == "order:summary":
            await order_handler.show_order_summary(self.client, chat_id, user_id, message_id)
            return

        if data == "order:confirm":
            await order_handler.confirm_order(self.client, chat_id, user_id, message_id)
            return

        if data == "clear":
            await cart_handler.confirm_clear_cart(self.client, chat_id, user_id, message_id)
            return

        if data == "clear:yes":
            await cart_handler.clear_cart(self.client, chat_id, user_id, message_id)
            return

        if data == "clear:no":
            await cart_handler.cancel_clear_cart(self.client, chat_id, user_id, message_id)
            return

        # admin callbacks
        if data.startswith("admin:"):
            if data == "admin:orders":
                await admin_handler.admin_orders(self.client, chat_id, user_id, message_id)
            elif data.startswith("admin:order_status:"):
                parts = data.split(":")
                if len(parts) == 4:
                    try:
                        order_id = int(parts[2])
                        status = parts[3]
                    except ValueError:
                        return
                    await admin_handler.admin_order_status(
                        self.client, chat_id, user_id, order_id, status, message_id
                    )
            elif data.startswith("admin:order:"):
                parts = data.split(":")
                if len(parts) == 3:
                    try:
                        order_id = int(parts[2])
                    except ValueError:
                        return
                    await admin_handler.show_order_detail(
                        self.client, chat_id, user_id, order_id, message_id
                    )
            elif data == "admin:products":
                await admin_handler.admin_products(self.client, chat_id, user_id, message_id)
            elif data.startswith("admin:cat:"):
                parts = data.split(":")
                if len(parts) == 3:
                    slug = parts[2]
                    await admin_handler.show_admin_products_list(
                        self.client, chat_id, user_id, slug, message_id
                    )
            elif data.startswith("admin:product_toggle:"):
                parts = data.split(":")
                if len(parts) == 3:
                    try:
                        product_id = int(parts[2])
                    except ValueError:
                        return
                    await admin_handler.admin_product_toggle(
                        self.client, chat_id, user_id, product_id, message_id
                    )
            elif data.startswith("admin:product:"):
                parts = data.split(":")
                if len(parts) == 3:
                    try:
                        product_id = int(parts[2])
                    except ValueError:
                        return
                    await admin_handler.show_admin_product_detail(
                        self.client, chat_id, user_id, product_id, message_id
                    )
            elif data == "admin:stats":
                await admin_handler.admin_stats(self.client, chat_id, user_id, message_id)
            elif data == "admin:broadcast":
                await admin_handler.admin_broadcast(self.client, chat_id, user_id, message_id)
            elif data == "admin:broadcast:cancel":
                await admin_handler.admin_broadcast_cancel(self.client, chat_id, user_id, message_id)
            elif data == "admin:broadcast:send":
                await admin_handler.admin_broadcast_send(self.client, chat_id, user_id, message_id)
            elif data == "admin:exit":
                await admin_handler.admin_exit(self.client, chat_id, user_id, message_id)
            elif data == "admin:back":
                await admin_handler.admin_back_to_menu(self.client, chat_id, user_id, message_id)
            elif data == "admin:add:start":
                await admin_handler.admin_add_start(self.client, chat_id, user_id, message_id)
            elif data.startswith("admin:add:cat:"):
                parts = data.split(":")
                if len(parts) == 4:
                    try:
                        category_id = int(parts[3])
                    except ValueError:
                        return
                    await admin_handler.admin_add_category_selected(
                        self.client, chat_id, user_id, category_id, message_id
                    )
            elif data == "admin:add:photos_done":
                await admin_handler.admin_add_photos_done(self.client, chat_id, user_id, message_id)
            elif data == "admin:add:save":
                await admin_handler.admin_add_save(self.client, chat_id, user_id, message_id)
            elif data == "admin:add:cancel":
                await admin_handler.admin_add_cancel(self.client, chat_id, user_id, message_id)
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

        if cmd == "qty" and len(parts) == 3:
            try:
                product_id = int(parts[1])
                action = parts[2]
            except ValueError:
                return
            if action in ("inc", "dec"):
                delta = 1 if action == "inc" else -1
                await cart_handler.change_quantity(self.client, chat_id, user_id, message_id, product_id, delta)
            return

        if cmd == "rm" and len(parts) == 2:
            try:
                product_id = int(parts[1])
            except ValueError:
                return
            await cart_handler.remove_item(self.client, chat_id, user_id, message_id, product_id)
            return
