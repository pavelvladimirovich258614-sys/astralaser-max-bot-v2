from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.crud import user_state as user_state_crud


async def get_state(session: AsyncSession, user_id: int) -> tuple[str | None, dict[str, Any]]:
    """Получить текущий FSM-state и данные пользователя."""
    user_state = await user_state_crud.get_state(session, user_id)
    if not user_state:
        return None, {}
    try:
        data: dict[str, Any] = json.loads(user_state.data)
    except json.JSONDecodeError:
        data = {}
    return user_state.state, data


async def set_state(session: AsyncSession, user_id: int, state: str, data: dict[str, Any] | None = None) -> None:
    """Установить FSM-state и данные пользователя."""
    data_json = json.dumps(data or {}, ensure_ascii=False)
    await user_state_crud.set_state(session, user_id, state, data_json)


async def clear_state(session: AsyncSession, user_id: int) -> None:
    """Очистить FSM-state пользователя."""
    await user_state_crud.clear_state(session, user_id)


async def set_waiting_name(session: AsyncSession, user_id: int) -> None:
    """Перевести пользователя в состояние ожидания ФИО."""
    await set_state(session, user_id, "order:waiting_name", {})
