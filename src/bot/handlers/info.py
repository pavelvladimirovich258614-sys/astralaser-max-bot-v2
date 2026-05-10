from __future__ import annotations

from src.bot.keyboards import contact_keyboard, help_keyboard
from src.bot.max_client import MAXClient
from src.config import get_settings


def _build_contact_text() -> str:
    s = get_settings()
    lines: list[str] = ["💬 Связаться с менеджером", ""]
    if s.manager_phone.strip():
        lines.append(f"📱 Телефон: {s.manager_phone.strip()}")
    if s.manager_vk_link.strip():
        lines.append(f"🌐 ВКонтакте: {s.manager_vk_link.strip()}")
    if s.max_manager_link.strip():
        lines.append(f"💬 MAX: {s.max_manager_link.strip()}")
    if s.working_hours.strip():
        lines.append(f"🕐 Рабочие часы: {s.working_hours.strip()}")

    marketplace = [
        ("MAX", s.max_channel_link.strip()),
        ("ВКонтакте", s.manager_vk_link.strip()),
        ("Ozon", s.ozon_link.strip()),
        ("Wildberries", s.wildberries_link.strip()),
    ]
    marketplace_lines = [f"• {name}: {url}" for name, url in marketplace if url]
    if marketplace_lines:
        lines.append("")
        lines.append("🌐 Наши площадки:")
        lines.extend(marketplace_lines)

    lines.append("")
    lines.append("Если кнопка не открывается, напишите сообщение здесь — менеджер свяжется с вами.")
    return "\n".join(lines)


HELP_TEXT = (
    "❓ Помощь\n\n"
    "Команды:\n"
    "/start — главное меню\n"
    "/catalog — каталог украшений\n"
    "/cart — корзина\n"
    "/contact — связаться с менеджером\n"
    "/help — эта справка\n\n"
    "Как сделать заказ:\n"
    "1. Выберите категорию в каталоге\n"
    "2. Откройте товар, нажмите «🛒 В корзину»\n"
    "3. Перейдите в корзину → «Оформить заказ»\n"
    "4. Заполните анкету (имя, телефон, адрес, гравировка)\n"
    "5. Подтвердите заказ\n"
    "6. Дождитесь связи менеджера\n\n"
    "Срок изготовления: 1–2 рабочих дня\n"
    "Доставка: СДЭК (ПВЗ или курьер)"
)


async def show_contact(client: MAXClient, chat_id: int | str, message_id: str | None = None) -> None:
    s = get_settings()
    text = _build_contact_text()
    kb = contact_keyboard(s.manager_phone.strip(), s.manager_vk_link.strip(), s.max_manager_link.strip())
    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=kb)
    else:
        await client.send_message(chat_id, text, reply_markup=kb)


async def show_help(client: MAXClient, chat_id: int | str, message_id: str | None = None) -> None:
    kb = help_keyboard()
    if message_id:
        await client.edit_message(chat_id, message_id, HELP_TEXT, reply_markup=kb)
    else:
        await client.send_message(chat_id, HELP_TEXT, reply_markup=kb)
