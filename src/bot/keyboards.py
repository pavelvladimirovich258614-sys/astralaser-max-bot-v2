"""Универсальные клавиатуры (inline)."""

from typing import Any


def main_menu_inline_keyboard() -> list[list[dict[str, Any]]]:
    """Inline-клавиатура (под сообщением) для главного меню."""
    return [
        [{"type": "callback", "text": "📚 Каталог", "payload": "menu:catalog"}, {"type": "callback", "text": "🛒 Корзина", "payload": "menu:cart"}],
        [{"type": "callback", "text": "📦 Мои заказы", "payload": "menu:orders"}, {"type": "callback", "text": "❓ Помощь", "payload": "menu:help"}],
        [{"type": "callback", "text": "💬 Менеджер", "payload": "menu:contact"}],
        [{"type": "callback", "text": "🖼 Наши работы", "payload": "gallery_works"}],
        [{"type": "link", "text": "📍 Пункты выдачи СДЭК", "url": "https://www.cdek.ru/ru/offices/cdek"}],
        [
            {"type": "link", "text": "📦 Ozon", "url": "https://ozon.ru/s/astralaser"},
            {"type": "link", "text": "🟣 Wildberries", "url": "https://www.wildberries.ru/brands/311460915-astralaser"},
        ],
    ]


def shop_instruction_keyboard() -> list[list[dict[str, Any]]]:
    """Кнопка закрытия визуальной инструкции по Mini App."""
    return [
        [{"type": "callback", "text": "✅ Прочитано", "payload": "instruction:close"}],
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


def added_to_cart_keyboard(product_id: int) -> list[list[dict[str, Any]]]:
    """После добавления в корзину: к корзине / назад к товару / главная."""
    return [
        [{"type": "callback", "text": "🛒 Перейти в корзину", "payload": "menu:cart"}],
        [{"type": "callback", "text": "🔙 К товару", "payload": f"prod:{product_id}"}],
        [{"type": "callback", "text": "🏠 Главная", "payload": "home"}],
    ]


def empty_cart_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура для пустой корзины."""
    return [
        [{"type": "callback", "text": "📚 В каталог", "payload": "menu:catalog"}],
        [{"type": "callback", "text": "🏠 Главная", "payload": "home"}],
    ]


def cart_view_keyboard(items: list[Any]) -> list[list[dict[str, Any]]]:
    """Клавиатура для экрана корзины с управлением количеством."""
    buttons: list[list[dict[str, Any]]] = []
    for item in items:
        buttons.append(
            [
                {"type": "callback", "text": "➖", "payload": f"qty:{item.product_id}:dec"},
                {"type": "callback", "text": "➕", "payload": f"qty:{item.product_id}:inc"},
                {"type": "callback", "text": "❌", "payload": f"rm:{item.product_id}"},
            ]
        )
    buttons.append([{"type": "callback", "text": "✅ Оформить заказ", "payload": "checkout"}])
    buttons.append([{"type": "callback", "text": "🗑 Очистить", "payload": "clear"}])
    buttons.append(
        [
            {"type": "callback", "text": "📚 В каталог", "payload": "menu:catalog"},
            {"type": "callback", "text": "🏠 Главная", "payload": "home"},
        ]
    )
    return buttons


def clear_confirm_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура подтверждения очистки корзины."""
    return [
        [{"type": "callback", "text": "✅ Да, очистить", "payload": "clear:yes"}],
        [{"type": "callback", "text": "↩️ Нет, оставить", "payload": "clear:no"}],
    ]


def checkout_stub_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура placeholder-экрана оформления заказа."""
    return [
        [{"type": "callback", "text": "🛒 Вернуться в корзину", "payload": "menu:cart"}],
        [{"type": "callback", "text": "🏠 Главная", "payload": "home"}],
    ]


def order_cancel_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура для экранов оформления заказа с кнопкой отмены."""
    return [
        [{"type": "callback", "text": "❌ Отменить оформление", "payload": "order:cancel"}],
    ]


def order_ready_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура для экрана готовности заказа (до F07.3 — только отмена)."""
    return [
        [{"type": "callback", "text": "📋 Перейти к подтверждению", "payload": "order:summary"}],
        [{"type": "callback", "text": "❌ Отменить оформление", "payload": "order:cancel"}],
    ]


def order_summary_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура экрана подтверждения заказа."""
    return [
        [{"type": "callback", "text": "✅ Подтвердить заказ", "payload": "order:confirm"}],
        [{"type": "callback", "text": "❌ Отменить оформление", "payload": "order:cancel"}],
    ]


def order_confirmed_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура после успешного оформления заказа."""
    return [
        [{"type": "callback", "text": "🏠 Главная", "payload": "home"}],
    ]


def user_orders_keyboard(orders: list[Any]) -> list[list[dict[str, Any]]]:
    """Клавиатура списка заказов пользователя."""
    buttons: list[list[dict[str, Any]]] = []
    for order in orders:
        buttons.append(
            [
                {
                    "type": "callback",
                    "text": f"#{order.id} — {_user_order_status_label(order.status)}",
                    "payload": f"order_details:{order.id}",
                }
            ]
        )
    buttons.append([{"type": "callback", "text": "🏠 Главная", "payload": "home"}])
    return buttons


def user_order_detail_keyboard(order_id: int, status: str) -> list[list[dict[str, Any]]]:
    """Клавиатура деталей заказа пользователя."""
    buttons: list[list[dict[str, Any]]] = []
    if status == "pending":
        buttons.append(
            [{"type": "callback", "text": "❌ Отменить заказ", "payload": f"order_cancel_confirm:{order_id}"}]
        )
    buttons.append([{"type": "callback", "text": "🔙 К заказам", "payload": "menu:orders"}])
    buttons.append([{"type": "callback", "text": "🏠 Главная", "payload": "home"}])
    return buttons


def user_order_cancel_confirm_keyboard(order_id: int) -> list[list[dict[str, Any]]]:
    """Клавиатура подтверждения отмены пользовательского заказа."""
    return [
        [{"type": "callback", "text": "✅ Да", "payload": f"order_cancel_execute:{order_id}"}],
        [{"type": "callback", "text": "↩️ Нет", "payload": f"order_details:{order_id}"}],
    ]


def contact_keyboard(phone: str = "", vk_link: str = "", max_link: str = "") -> list[list[dict[str, Any]]]:
    """Клавиатура экрана контактов. Ссылки показаны текстом, навигация — callback."""
    return [
        [{"type": "callback", "text": "🏠 Главная", "payload": "home"}],
    ]


def help_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура экрана помощи."""
    return [
        [
            {"type": "callback", "text": "📚 Каталог", "payload": "menu:catalog"},
            {"type": "callback", "text": "🛒 Корзина", "payload": "menu:cart"},
        ],
        [{"type": "callback", "text": "🏠 Главная", "payload": "home"}],
    ]


def subscription_gate_keyboard(channel_url: str = "") -> list[list[dict[str, Any]]]:
    """Клавиатура экрана подписки на канал."""
    return [
        [{"type": "callback", "text": "✅ Я подписался", "payload": "sub:check"}],
        [{"type": "callback", "text": "🔙 Назад", "payload": "menu:cart"}],
    ]


def admin_menu_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура главного меню админ-панели."""
    return [
        [{"type": "callback", "text": "📦 Заказы", "payload": "admin:orders"}, {"type": "callback", "text": "📚 Товары", "payload": "admin:products"}],
        [{"type": "callback", "text": "📊 Статистика", "payload": "admin:stats"}, {"type": "callback", "text": "📤 Рассылка", "payload": "admin:broadcast"}],
        [{"type": "callback", "text": "🚪 Выход", "payload": "admin:exit"}],
    ]


def _user_order_status_label(status: str) -> str:
    labels = {
        "pending": "⏳ Ожидает подтверждения",
        "confirmed": "✅ Подтверждён",
        "completed": "🏁 Завершён",
        "cancelled": "❌ Отменён",
    }
    return labels.get(status, status)


def admin_back_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура для skeleton экранов админ-панели с кнопкой назад."""
    return [
        [{"type": "callback", "text": "🔙 Назад", "payload": "admin:back"}],
    ]


def admin_orders_keyboard(orders: list[Any]) -> list[list[dict[str, Any]]]:
    """Клавиатура списка заказов: каждый заказ — кнопка + назад в админ-панель."""
    from src.services.admin_service import status_emoji

    buttons: list[list[dict[str, Any]]] = []
    for order in orders:
        text = f"#{order.id} {status_emoji(order.status)} {order.total_amount} ₽"
        buttons.append([{"type": "callback", "text": text, "payload": f"admin:order:{order.id}"}])
    buttons.append([{"type": "callback", "text": "🔙 Назад", "payload": "admin:back"}])
    return buttons


def admin_order_detail_keyboard(order_id: int, status: str) -> list[list[dict[str, Any]]]:
    """Клавиатура карточки заказа: кнопки смены статуса + назад к списку."""
    buttons: list[list[dict[str, Any]]] = []

    if status == "pending":
        buttons.append([
            {"type": "callback", "text": "✅ Подтвердить", "payload": f"admin:order_status:{order_id}:confirmed"},
            {"type": "callback", "text": "❌ Отменить", "payload": f"admin:order_status:{order_id}:cancelled"},
        ])
    elif status == "confirmed":
        buttons.append([
            {"type": "callback", "text": "🏁 Завершить", "payload": f"admin:order_status:{order_id}:completed"},
            {"type": "callback", "text": "❌ Отменить", "payload": f"admin:order_status:{order_id}:cancelled"},
        ])

    buttons.append([{"type": "callback", "text": "🔙 Назад", "payload": "admin:orders"}])
    return buttons


def admin_orders_back_keyboard() -> list[list[dict[str, Any]]]:
    """Кнопка назад к списку заказов."""
    return [
        [{"type": "callback", "text": "🔙 Назад", "payload": "admin:orders"}],
    ]


def admin_categories_keyboard(categories: list[Any]) -> list[list[dict[str, Any]]]:
    """Клавиатура списка категорий для админа."""
    buttons: list[list[dict[str, Any]]] = []
    for item in categories:
        cat = item["category"]
        count = item["product_count"]
        text = f"{cat.title} — {count}"
        buttons.append([{"type": "callback", "text": text, "payload": f"admin:cat:{cat.slug}"}])
    buttons.append([{"type": "callback", "text": "🔙 Назад", "payload": "admin:back"}])
    return buttons


def admin_products_keyboard(products: list[Any], category_slug: str) -> list[list[dict[str, Any]]]:
    """Клавиатура списка товаров категории для админа."""
    buttons: list[list[dict[str, Any]]] = []
    for product in products:
        status_icon = "👁" if product.is_active else "🚫"
        text = f"{status_icon} {product.title} — {product.price} ₽"
        buttons.append([{"type": "callback", "text": text, "payload": f"admin:product:{product.id}"}])
    buttons.append([{"type": "callback", "text": "🔙 Назад", "payload": "admin:products"}])
    return buttons


def admin_product_detail_keyboard(product_id: int, is_active: bool, category_slug: str) -> list[list[dict[str, Any]]]:
    """Клавиатура карточки товара для админа: toggle + назад."""
    if is_active:
        toggle_text = "🚫 Скрыть"
    else:
        toggle_text = "👁 Включить"
    return [
        [{"type": "callback", "text": toggle_text, "payload": f"admin:product_toggle:{product_id}"}],
        [{"type": "callback", "text": "🔙 Назад", "payload": f"admin:cat:{category_slug}"}],
    ]


def admin_add_start_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура добавления товара в экране категорий."""
    return [
        [{"type": "callback", "text": "➕ Добавить товар", "payload": "admin:add:start"}],
    ]


def admin_add_categories_keyboard(categories: list[Any]) -> list[list[dict[str, Any]]]:
    """Клавиатура выбора категории при добавлении товара."""
    buttons: list[list[dict[str, Any]]] = []
    for item in categories:
        cat = item["category"] if isinstance(item, dict) else item
        cat_id = cat.id
        buttons.append([{"type": "callback", "text": cat.title, "payload": f"admin:add:cat:{cat_id}"}])
    buttons.append([{"type": "callback", "text": "🔙 Назад", "payload": "admin:products"}])
    return buttons


def admin_add_photos_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура шага сбора фото: Готово / Отмена."""
    return [
        [{"type": "callback", "text": "✅ Готово", "payload": "admin:add:photos_done"}],
        [{"type": "callback", "text": "❌ Отмена", "payload": "admin:add:cancel"}],
    ]


def admin_add_preview_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура превью товара: Сохранить / Отмена."""
    return [
        [{"type": "callback", "text": "✅ Сохранить", "payload": "admin:add:save"}],
        [{"type": "callback", "text": "❌ Отмена", "payload": "admin:add:cancel"}],
    ]


def admin_broadcast_text_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура шага ввода текста рассылки: Отмена."""
    return [
        [{"type": "callback", "text": "❌ Отмена", "payload": "admin:broadcast:cancel"}],
    ]


def admin_broadcast_preview_keyboard() -> list[list[dict[str, Any]]]:
    """Клавиатура превью рассылки: Отправить / Отмена."""
    return [
        [{"type": "callback", "text": "✅ Отправить", "payload": "admin:broadcast:send"}],
        [{"type": "callback", "text": "❌ Отмена", "payload": "admin:broadcast:cancel"}],
    ]
