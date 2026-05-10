from __future__ import annotations

from typing import Any

SUBSCRIBED_STATUSES = frozenset({"member", "administrator", "creator", "owner"})


def is_member_status(member: dict[str, Any] | None) -> bool:
    if not member:
        return False
    status = member.get("status", "")
    return bool(status and status in SUBSCRIBED_STATUSES)
