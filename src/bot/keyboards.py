"""Универсальные клавиатуры (inline)."""

from typing import Any


def main_menu_inline_keyboard() -> list[list[dict[str, Any]]]:
    """Inline-клавиатура (под сообщением) для главного меню."""
    return [
        [{"type": "callback", "text": "📚 Каталог", "payload": "menu:catalog"}, {"type": "callback", "text": "🛒 Корзина", "payload": "menu:cart"}],
        [{"type": "callback", "text": "📦 Мои заказы", "payload": "menu:orders"}, {"type": "callback", "text": "❓ Помощь", "payload": "menu:help"}],
        [{"type": "callback", "text": "💬 Менеджер", "payload": "menu:contact"}],
    ]


def consent_keyboard() -> list[list[dict[str, Any]]]:
    """Inline-клавиатура. MAX API требует type=callback + payload."""
    return [
        [{"type": "callback", "text": "✅ Принимаю", "payload": "consent:accept"}],
    ]
