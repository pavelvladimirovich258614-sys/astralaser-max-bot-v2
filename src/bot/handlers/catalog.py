from __future__ import annotations

from src.bot.keyboards import (
    added_to_cart_keyboard,
    catalog_categories_keyboard,
    category_products_keyboard,
    product_card_keyboard,
)
from src.bot.max_client import MAXClient
from src.db.engine import async_session_maker
from src.services import cart_service, catalog_service, user_service


def _truncate(text: str, length: int = 250) -> str:
    if len(text) <= length:
        return text
    return text[: length - 1].rstrip() + "…"


async def show_catalog(
    client: MAXClient, chat_id: int | str, message_id: str | None = None,
) -> None:
    """Показывает список категорий. edit_message если message_id, иначе send."""
    async with async_session_maker() as session:
        categories = await catalog_service.get_categories_with_count(session)

    text = "📚 Выберите категорию:"
    keyboard = catalog_categories_keyboard(categories)

    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
    else:
        await client.send_message(chat_id, text, reply_markup=keyboard)


async def show_category(
    client: MAXClient, chat_id: int | str, message_id: str, slug: str,
) -> None:
    """Показывает товары категории. Если 1 товар — сразу карточка."""
    async with async_session_maker() as session:
        products = await catalog_service.get_products_by_slug(session, slug)

    if not products:
        await client.edit_message(
            chat_id, message_id, "В этой категории пока нет товаров.", reply_markup=category_products_keyboard([], slug),
        )
        return

    if len(products) == 1:
        await show_product_card(client, chat_id, message_id, products[0].id)
        return

    text = "📚 Выберите товар:"
    keyboard = category_products_keyboard(products, slug)
    await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)


async def show_product_card(
    client: MAXClient,
    chat_id: int | str,
    message_id: str,
    product_id: int,
    photo_index: int = 0,
) -> None:
    """Карточка товара с пагинацией фото."""
    async with async_session_maker() as session:
        card = await catalog_service.get_product_card(session, product_id, photo_index)

    if not card:
        await client.edit_message(chat_id, message_id, "Товар не найден.")
        return

    text = f"{card.title}\n💰 {card.price} ₽\n\n{_truncate(card.description)}"
    keyboard = product_card_keyboard(product_id, card.photo_index, card.photo_count, card.category_slug)
    if card.photo:
        await client.edit_message(
            chat_id, message_id, text, reply_markup=keyboard, photo=card.photo,
        )
    else:
        await client.edit_message(
            chat_id, message_id, text, reply_markup=keyboard, photo_url=card.photo_url,
        )


async def add_to_cart(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str,
    product_id: int,
) -> None:
    """Добавить товар в корзину. edit_message с уведомлением."""
    async with async_session_maker() as session:
        user = await user_service.get_or_create_user(session, max_user_id=str(user_id))
        await session.commit()
        await cart_service.add_item(session, user, product_id, quantity=1)

    text = "✅ Товар добавлен в корзину."
    keyboard = added_to_cart_keyboard()
    await client.edit_message(chat_id, message_id, text, reply_markup=keyboard)
