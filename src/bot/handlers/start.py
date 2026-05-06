from __future__ import annotations

from typing import Any

from src.bot.keyboards import consent_keyboard, main_menu_reply_keyboard
from src.bot.max_client import MAXClient
from src.db.engine import async_session_maker
from src.services import user_service

PRIVACY_TEXT = """🔒 Перед тем как продолжить

Мы храним только данные, необходимые для обработки заказа: ваш ID в MAX, имя, телефон и адрес доставки.

Мы НЕ передаём данные третьим лицам. Вы можете удалить свои данные, написав менеджеру.

Полная версия политики: https://disk.yandex.ru/i/cQjQGw2-VDQp3w

Подтверждая, вы соглашаетесь с обработкой персональных данных."""

MAIN_MENU_TEXT = """🌟 Astralaser — украшения с персональной гравировкой

Здесь вы можете заказать кулоны, браслеты и брелоки с индивидуальной гравировкой для себя или в подарок.

Мы поможем подобрать изделие, согласуем ваш текст и изготовим украшение специально под ваш заказ.

✨ Срок изготовления: 1–2 рабочих дня
📦 Доставка СДЭК по всей России
💝 Бархатная сумочка в комплекте

Выберите раздел, чтобы начать."""

MAIN_MENU_PHOTO = "https://i.postimg.cc/vm2rdtGg/IMG-20260505-105827.png"

DECLINE_TEXT = "Без согласия на обработку данных мы не можем продолжить.\nВы всегда можете вернуться, нажав /start."


async def handle_start(client: MAXClient, chat_id: int | str, user_id: int | str, user_info: dict[str, Any]) -> None:
    async with async_session_maker() as session:
        user = await user_service.get_or_create_user(
            session,
            max_user_id=str(user_id),
            username=user_info.get("username"),
            full_name=user_info.get("name") or user_info.get("first_name", ""),
        )
        await session.commit()
        has_consent = user.consent_at is not None

    if not has_consent:
        await client.send_message(chat_id, PRIVACY_TEXT, reply_markup=consent_keyboard())
    else:
        await client.send_message(
            chat_id,
            MAIN_MENU_TEXT,
            reply_markup=main_menu_reply_keyboard(),
            photo_url=MAIN_MENU_PHOTO,
        )


async def handle_consent_accept(
    client: MAXClient, chat_id: int | str, user_id: int | str, message_id: str,
) -> None:
    async with async_session_maker() as session:
        await user_service.record_consent(session, max_user_id=str(user_id))
        await session.commit()

    await client.edit_message(
        chat_id,
        message_id,
        MAIN_MENU_TEXT,
        reply_markup=main_menu_reply_keyboard(),
        photo_url=MAIN_MENU_PHOTO,
    )


async def handle_consent_decline(client: MAXClient, chat_id: int | str, message_id: str) -> None:
    await client.edit_message(chat_id, message_id, DECLINE_TEXT)
