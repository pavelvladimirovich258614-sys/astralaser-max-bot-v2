from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User


async def get_user_by_max_id(session: AsyncSession, max_user_id: str) -> User | None:
    result = await session.execute(select(User).where(User.max_user_id == max_user_id))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, max_user_id: str, username: str | None = None, full_name: str | None = None) -> User:
    user = User(max_user_id=max_user_id, username=username, full_name=full_name)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_consent(session: AsyncSession, user: User) -> User:
    from datetime import datetime
    user.consent_at = datetime.utcnow()
    await session.commit()
    await session.refresh(user)
    return user
