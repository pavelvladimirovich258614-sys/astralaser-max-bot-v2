from __future__ import annotations

import logging

from src.bot.handlers import order as order_handler
from src.bot.keyboards import subscription_gate_keyboard
from src.bot.max_client import MAXClient
from src.config import get_settings
from src.services import subscription_service

logger = logging.getLogger(__name__)

GATE_TEXT = (
    "📢 Чтобы оформить заказ, подпишитесь на наш канал в MAX\n\n"
    "Там скидки, новинки и идеи гравировок.\n\n"
    "После подписки нажмите «✅ Я подписался»."
)

RETRY_TEXT = (
    "Мы пока не видим подписку. Попробуйте через минуту.\n\n"
    "Если вы уже подписались — повторите проверку."
)


def _build_gate_text(channel_url: str) -> str:
    if channel_url:
        return GATE_TEXT + f"\n\n🌐 Канал: {channel_url}"
    return GATE_TEXT


async def check_subscription(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    settings = get_settings()
    channel = settings.max_required_channel.strip()
    if not channel:
        await order_handler.start_checkout(client, chat_id, user_id, message_id)
        return

    try:
        member = await client.get_chat_member(channel, user_id)
    except Exception:
        logger.warning("get_chat_member failed in sub:check for user=%s", user_id, exc_info=True)
        member = None

    if subscription_service.is_member_status(member):
        await order_handler.start_checkout(client, chat_id, user_id, message_id)
    else:
        text = RETRY_TEXT
        keyboard = subscription_gate_keyboard(settings.max_required_channel_url.strip())
        if message_id:
            await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
        else:
            await client.send_message(chat_id, text, reply_markup=keyboard)
