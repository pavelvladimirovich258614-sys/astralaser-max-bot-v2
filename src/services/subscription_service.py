from __future__ import annotations

from typing import Any


def is_subscribed(response: dict[str, Any] | None) -> bool:
    """Проверяет ответ GET /chats/{chatId}/members?user_ids=... — пользователь подписан.

    MAX API возвращает {"members": [...], "marker": null}.
    Если members непустой — пользователь является участником чата/канала.
    """
    if not response:
        return False
    members = response.get("members")
    if not isinstance(members, list):
        return False
    return len(members) > 0


def is_member_status(member: dict[str, Any] | None) -> bool:
    """Обратная совместимость: проверяет старый формат {"status": "member"}.

    Оставлен для совместимости с тестами и будущими сценариями.
    """
    if not member:
        return False
    status = member.get("status", "")
    return bool(status and status in {"member", "administrator", "creator", "owner"})
