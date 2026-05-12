from sqlalchemy.ext.asyncio import AsyncSession

from src.db.crud import user as user_crud
from src.db.models import User


async def get_or_create_user(
    session: AsyncSession,
    max_user_id: str,
    max_chat_id: str | None = None,
    **info: str | None,
) -> User:
    user = await user_crud.get_user_by_max_id(session, max_user_id)
    if user:
        if max_chat_id is not None:
            user = await user_crud.update_max_chat_id(session, user, max_chat_id)
        return user
    return await user_crud.create_user(session, max_user_id=max_user_id, max_chat_id=max_chat_id, **info)


async def has_given_consent(session: AsyncSession, max_user_id: str) -> bool:
    user = await user_crud.get_user_by_max_id(session, max_user_id)
    return user is not None and user.consent_at is not None


async def record_consent(session: AsyncSession, max_user_id: str) -> None:
    user = await user_crud.get_user_by_max_id(session, max_user_id)
    if user:
        await user_crud.update_consent(session, user)
