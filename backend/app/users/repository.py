from uuid import UUID

from app.users.models import User, UserSettings
from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.common.types import Username
from app.decks.models import Deck, UserDeck

class UserSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # base
    def add(
        self,
        user_settings: UserSettings,
    ) -> None:
        self.session.add(user_settings)

    async def refresh(self, user_settings: UserSettings) -> None:
        await self.session.refresh(user_settings)

    # read
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

    # base
    def add(self, user: User) -> None:
        self.session.add(user)

    async def refresh(self, user: User) -> None:
        await self.session.refresh(user)

    async def delete(self, user: User) -> None:
        await self.session.delete(user)

    # read

    async def get_user_profile(
        self,
        profile_username: Username,
    ) -> tuple[User, int, int, int] | None:
        """
        returns User, his total created decks, his public created decks and\n
        total_saves_count of his public decks
        """
        stmt = (
            select(
                User,
                func.count(Deck.id).label("total_decks"),
                func.count(Deck.id)
                .filter(Deck.is_public.is_(True))
                .label("public_decks"),
                func.coalesce(
                    func.sum(Deck.saves_count)
                    .filter(Deck.is_public.is_(True)),
                    0,
                ).label("total_saves_count"),
            )
            .outerjoin(
                Deck, 
                Deck.user_id == User.id,
            )
            .where(
                User.username == profile_username,
            )
            .group_by(User.id)
        )
        result = await self.session.execute(stmt)
        return result.one_or_none()

    async def get_by_id(
            self, 
            user_id: int,
            for_update: bool = False,
            include_settings: bool = False,
        ) -> User | None:
        stmt = select(User).where(User.id == user_id)
        if include_settings:
            stmt = stmt.options(
                joinedload(User.settings)
            )
        if for_update:
            stmt = stmt.with_for_update(of=User)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_uuid(
            self, 
            user_uuid: UUID,
            for_update: bool = False,
            include_settings: bool = False,
        ) -> User | None:
        stmt = select(User).where(User.uuid == user_uuid)

        if include_settings:
            stmt = stmt.options(
                joinedload(User.settings)
            )

        if for_update:
            stmt = stmt.with_for_update(of=User)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
