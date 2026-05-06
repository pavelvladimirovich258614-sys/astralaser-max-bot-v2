"""Универсальные клавиатуры (inline)."""

from typing import Any


def main_menu_reply_keyboard() -> list[list[dict[str, Any]]]:
    return [
        [{"text": "📚 Каталог", "callback_data": "catalog"}, {"text": "🛒 Корзина", "callback_data": "cart"}],
        [{"text": "📦 Мои заказы", "callback_data": "orders"}, {"text": "❓ Помощь", "callback_data": "help"}],
        [{"text": "💬 Менеджер", "callback_data": "contact"}],
    ]


def consent_keyboard() -> list[list[dict[str, Any]]]:
    return [
        [{"text": "✅ Принимаю", "callback_data": "consent:accept"}],
        [{"text": "❌ Отклонить", "callback_data": "consent:decline"}],
    ]
