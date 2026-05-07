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


def catalog_categories_keyboard(categories: list[Any]) -> list[list[dict[str, Any]]]:
    """Кнопки категорий + кнопка назад в главное меню."""
    buttons: list[list[dict[str, Any]]] = [
        [{"type": "callback", "text": cat.title, "payload": f"cat:{cat.slug}"}]
        for cat in categories
    ]
    buttons.append([{"type": "callback", "text": "🏠 Главная", "payload": "home"}])
    return buttons


def category_products_keyboard(products: list[Any], category_slug: str) -> list[list[dict[str, Any]]]:
    """Кнопки товаров в категории + назад к категориям/главная."""
    buttons: list[list[dict[str, Any]]] = [
        [{"type": "callback", "text": f"{i + 1}. {p.title}", "payload": f"prod:{p.id}"}]
        for i, p in enumerate(products)
    ]
    buttons.append(
        [
            {"type": "callback", "text": "🔙 К категориям", "payload": "catalog"},
            {"type": "callback", "text": "🏠 Главная", "payload": "home"},
        ]
    )
    return buttons


def product_card_keyboard(product_id: int, photo_index: int, photo_count: int, category_slug: str) -> list[list[dict[str, Any]]]:
    """Пагинация фото + в корзину + назад + главная."""
    next_index = (photo_index + 1) % photo_count
    return [
        [{"type": "callback", "text": f"◀️ Фото {photo_index + 1}/{photo_count} ▶️", "payload": f"photo:{product_id}:{next_index}"}],
        [{"type": "callback", "text": "🛒 В корзину", "payload": f"add:{product_id}"}],
        [
            {"type": "callback", "text": "🔙 К категории", "payload": f"cat:{category_slug}"},
            {"type": "callback", "text": "🏠 Главная", "payload": "home"},
        ],
    ]


def added_to_cart_keyboard() -> list[list[dict[str, Any]]]:
    """После добавления в корзину: к корзине / назад / главная."""
    return [
        [{"type": "callback", "text": "🛒 К корзине", "payload": "menu:cart"}],
        [{"type": "callback", "text": "← Назад к товару", "payload": "noop"}],
        [{"type": "callback", "text": "🏠 Главная", "payload": "home"}],
    ]
