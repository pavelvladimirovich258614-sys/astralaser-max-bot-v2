from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User


async def get_user_by_max_id(session: AsyncSession, max_user_id: str) -> User | None:
    result = await session.execute(select(User).where(User.max_user_id == max_user_id))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    max_user_id: str,
    username: str | None = None,
    full_name: str | None = None,
    max_chat_id: str | None = None,
) -> User:
    user = User(max_user_id=max_user_id, username=username, full_name=full_name, max_chat_id=max_chat_id)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_max_chat_id(session: AsyncSession, user: User, max_chat_id: str | None) -> User:
    if max_chat_id is not None and user.max_chat_id != max_chat_id:
        user.max_chat_id = max_chat_id
        await session.commit()
        await session.refresh(user)
    return user


async def update_consent(session: AsyncSession, user: User) -> User:
    from datetime import datetime
    user.consent_at = datetime.utcnow()
    await session.commit()
    await session.refresh(user)
    return user


async def get_broadcast_recipients(session: AsyncSession, limit: int | None = None) -> list[User]:
    """Получить пользователей для рассылки: только с consent_at IS NOT NULL, сортировка по id ASC."""
    stmt = select(User).where(User.consent_at.is_not(None)).order_by(User.id.asc())
    if limit:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())
