from uuid import UUID

from app.users.models import User, UserSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

class UserSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def refresh(self, user_settings: UserSettings) -> None:
        await self.session.refresh(user_settings)

    def add(
        self,
        user_settings: UserSettings,
    ) -> None:
        self.session.add(user_settings)

    async def get_by_user_id(
            self,
            user_id: int,
            for_update: bool = False,
    ) -> UserSettings | None:
        stmt = select(UserSettings).where(UserSettings.user_id == user_id)
        if for_update:
            stmt = stmt.with_for_update(of=UserSettings)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
            self, 
            user_id: int,
            for_update: bool = False,
        ) -> User | None:
        stmt = select(User).where(User.id == user_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_uuid(
            self, 
            user_uuid: UUID,
            for_update: bool = False,
            get_settings: bool = False,
        ) -> User | None:
        stmt = select(User).where(User.uuid == user_uuid)

        if get_settings:
            stmt = stmt.options(
                joinedload(User.settings)
            )

        if for_update:
            stmt = stmt.with_for_update(of=User)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    def add(self, user: User) -> None:
        self.session.add(user)

    async def delete(self, user: User) -> None:
        await self.session.delete(user)

    async def refresh(self, user: User) -> None:
        await self.session.refresh(user)

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
