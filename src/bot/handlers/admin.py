from __future__ import annotations

from src.bot import keyboards as kb
from src.bot.handlers import start as start_handler
from src.bot.max_client import MAXClient
from src.config import get_settings

ADMIN_MENU_TEXT = """🛠 Админ-панель

Выберите раздел для управления.

📦 Заказы — просмотр и обработка заказов
📚 Товары — управление товарами
🏷 Категории — управление категориями
📊 Статистика — краткие показатели
📤 Рассылка — сообщения пользователям
🚪 Выход — вернуться в главное меню"""

NOT_FOUND_TEXT = "Команда не найдена."


async def handle_admin_command(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    user_info: dict[str, str] | None = None,
) -> None:
    """Обработка команды /admin. Доступ только для MAX_ADMIN_USER_IDS."""
    if not _is_admin(user_id):
        await client.send_message(chat_id, NOT_FOUND_TEXT)
        return
    await show_admin_menu(client, chat_id)


async def show_admin_menu(
    client: MAXClient,
    chat_id: int | str,
    message_id: str | None = None,
) -> None:
    """Показать главное меню админ-панели."""
    if message_id:
        await client.edit_message(chat_id, message_id, ADMIN_MENU_TEXT, reply_markup=kb.admin_menu_keyboard())
    else:
        await client.send_message(chat_id, ADMIN_MENU_TEXT, reply_markup=kb.admin_menu_keyboard())


async def admin_exit(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Выйти из админ-панели в главное меню."""
    await start_handler.show_main_menu(client, chat_id, message_id)


async def admin_back_to_menu(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """Вернуться из placeholder-экрана в меню админ-панели."""
    if not _is_admin(user_id):
        return
    await show_admin_menu(client, chat_id, message_id)


# ---------------------------------------------------------------------------
# Skeleton callbacks для подменю F10.2–F10.5
# ---------------------------------------------------------------------------


async def admin_orders(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """📦 Заказы — placeholder (F10.2)."""
    if not _is_admin(user_id):
        return
    text = "📦 Заказы — скоро."
    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_back_keyboard())
    else:
        await client.send_message(chat_id, text, reply_markup=kb.admin_back_keyboard())


async def admin_products(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """📚 Товары — placeholder (F10.3)."""
    if not _is_admin(user_id):
        return
    text = "📚 Товары — скоро."
    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_back_keyboard())
    else:
        await client.send_message(chat_id, text, reply_markup=kb.admin_back_keyboard())


async def admin_categories(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """🏷 Категории — placeholder (F10.3)."""
    if not _is_admin(user_id):
        return
    text = "🏷 Категории — скоро."
    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_back_keyboard())
    else:
        await client.send_message(chat_id, text, reply_markup=kb.admin_back_keyboard())


async def admin_stats(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """📊 Статистика — placeholder."""
    if not _is_admin(user_id):
        return
    text = "📊 Статистика — скоро."
    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_back_keyboard())
    else:
        await client.send_message(chat_id, text, reply_markup=kb.admin_back_keyboard())


async def admin_broadcast(
    client: MAXClient,
    chat_id: int | str,
    user_id: int | str,
    message_id: str | None = None,
) -> None:
    """📤 Рассылка — placeholder (F10.5)."""
    if not _is_admin(user_id):
        return
    text = "📤 Рассылка — скоро."
    if message_id:
        await client.edit_message(chat_id, message_id, text, reply_markup=kb.admin_back_keyboard())
    else:
        await client.send_message(chat_id, text, reply_markup=kb.admin_back_keyboard())


def _is_admin(user_id: int | str) -> bool:
    """Проверить, что user_id входит в список администраторов."""
    return str(user_id) in get_settings().admin_ids_list
