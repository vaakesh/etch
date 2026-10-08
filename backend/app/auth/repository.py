from datetime import datetime
from app.tracing import traced

from app.auth.models import UserSession
from app.common.query import apply_date_pagination
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # base

    async def get_by_id(self, user_session_id: int) -> UserSession | None:
        return await self.session.get(UserSession, user_session_id)

    def add(self, user_session: UserSession) -> None:
        self.session.add(user_session)

    @traced("auth.repository.flush")
    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, user_session: UserSession) -> None:
        await self.session.refresh(user_session)

    async def delete(self, user_session: UserSession) -> None:
        await self.session.delete(user_session)

    # read

    @traced("auth.repository.get_user_id_by_refresh")
    async def get_user_id_by_refresh(self, refresh_token_hash: str) -> int | None:
        stmt = select(UserSession.user_id).where(
            UserSession.refresh_token_hash == refresh_token_hash
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @traced("auth.repository.get_user_session_by_refresh")
    async def get_user_session_by_refresh(
        self, refresh_token_hash: str, *, for_update: bool = False
    ) -> UserSession | None:
        stmt = select(UserSession).where(
            UserSession.refresh_token_hash == refresh_token_hash
        )
        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @traced("auth.repository.get_active_user_sessions")
    async def get_active_user_sessions(
        self,
        user_id: int,
        now: datetime,
        cursor_created_at: datetime | None = None,
        cursor_id: int | None = None,
        limit: int = 20,
    ) -> tuple[list[UserSession], bool]:
        stmt = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.replaced_by_session_id.is_(None),
            UserSession.expires_at > now,
        )

        stmt = apply_date_pagination(
            stmt,
            date_column=UserSession.created_at,
            id_column=UserSession.id,
            cursor_at=cursor_created_at,
            cursor_id=cursor_id,
            limit=limit,
        )

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        has_more = len(rows) > limit
        return rows[:limit], has_more

    # write

    @traced("auth.repository.revoke_active_session_by_refresh_token_hash")
    async def revoke_active_session_by_refresh_token_hash(
        self,
        refresh_token_hash: str,
        revoked_at: datetime,
    ) -> bool:
        stmt = (
            update(UserSession)
            .where(
                UserSession.refresh_token_hash == refresh_token_hash,
                UserSession.revoked_at.is_(None),
                UserSession.replaced_by_session_id.is_(None),
                UserSession.expires_at > revoked_at,
            )
            .values(revoked_at=revoked_at)
        )
        result = await self.session.execute(stmt)
        return bool(result.rowcount)

    @traced("auth.repository.revoke_all_active_sessions_by_user_id")
    async def revoke_all_active_sessions_by_user_id(
        self,
        user_id: int,
        revoked_at: datetime,
    ) -> None:
        stmt = (
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.replaced_by_session_id.is_(None),
                UserSession.expires_at > revoked_at,
            )
            .values(revoked_at=revoked_at)
        )
        await self.session.execute(stmt)
