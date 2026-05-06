from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import UserState


async def get_state(session: AsyncSession, user_id: int) -> UserState | None:
    result = await session.execute(select(UserState).where(UserState.user_id == user_id))
    return result.scalar_one_or_none()


async def set_state(session: AsyncSession, user_id: int, state: str, data: str = "{}") -> UserState:
    result = await session.execute(select(UserState).where(UserState.user_id == user_id))
    user_state = result.scalar_one_or_none()
    if user_state:
        user_state.state = state
        user_state.data = data
    else:
        user_state = UserState(user_id=user_id, state=state, data=data)
        session.add(user_state)
    await session.commit()
    await session.refresh(user_state)
    return user_state


async def clear_state(session: AsyncSession, user_id: int) -> None:
    result = await session.execute(select(UserState).where(UserState.user_id == user_id))
    user_state = result.scalar_one_or_none()
    if user_state:
        await session.delete(user_state)
        await session.commit()
