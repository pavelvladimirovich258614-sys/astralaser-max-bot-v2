from __future__ import annotations

import logging
import os

from src.bot.keyboards import (
    added_to_cart_keyboard,
    catalog_categories_keyboard,
    category_products_keyboard,
    product_card_keyboard,
)
from src.bot.max_client import MAXClient
from src.db.engine import async_session_maker
from src.services import cart_service, catalog_service, user_service

logger = logging.getLogger(__name__)

_USE_PHOTO_URL_IN_EDIT: bool = os.getenv("USE_PHOTO_URL_IN_EDIT", "1") == "1"


def _short_description(text: str, max_length: int = 120) -> str:
    """Берёт только первое предложение/строку описания, без блоков Особенности/Сроки/Доставка."""
    first_para = text.split("\n\n")[0].strip()
    first_line = first_para.split("\n")[0].strip()
    if len(first_line) <= max_length:
        return first_line
    return first_line[: max_length - 1].rstrip() + "…"


async def show_catalog(
    client: MAXClient, chat_id: int | str, message_id: str | None = None,
) -> None:
    """Показывает список категорий. edit_message если message_id, иначе send."""
    async with async_session_maker() as session:
        categories = await catalog_service.get_categories_with_count(session)

    text = (
        "💎 Выберите категорию украшений\n\n"
        "В каждом разделе — актуальные модели с гравировкой.\n"
        "Можно посмотреть варианты для себя или в подарок.\n\n"
        "👇 Нажмите на нужную кнопку"
    )
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

    text = (
        "✨ Выберите товар из списка\n\n"
        "Каждое изделие можно сделать с вашей гравировкой.\n"
        "Нажмите на нужный вариант, чтобы посмотреть детали.\n\n"
        "🔙 Для возврата используйте кнопку «К категориям»"
    )
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

    description_text = card.description if _USE_PHOTO_URL_IN_EDIT else _short_description(card.description)
    text = f"{card.title}\n💰 {card.price} ₽\n\n{description_text}"
    keyboard = product_card_keyboard(product_id, card.photo_index, card.photo_count, card.category_slug)
    if _USE_PHOTO_URL_IN_EDIT:
        logger.info(
            "product_card replacing message old_message_id=%s product_id=%s photo_index=%s",
            message_id, product_id, photo_index,
        )
        deleted = await client.delete_message(chat_id, message_id)
        logger.info("product_card delete result old_message_id=%s deleted=%s", message_id, deleted)
        send_result = await client.send_message(
            chat_id, text, reply_markup=keyboard, photo_url=card.photo_url,
        )
        new_msg_id: str | None = None
        if isinstance(send_result, dict):
            new_msg_id = (
                send_result.get("mid")
                or send_result.get("id")
                or send_result.get("message", {}).get("body", {}).get("mid")
            )
        if new_msg_id:
            logger.info("product_card new message_id=%s", new_msg_id)
        else:
            logger.info("product_card new message_id=unknown")
    elif card.photo:
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
