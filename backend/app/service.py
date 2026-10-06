
from app.auth.repository import AuthRepository
from app.tracing import traced
from app.cards.repository import CardRepository
from app.decks.repository import DeckCardRepository, DeckRepository, UserDeckRepository
from app.training_sessions.repository import (
    TrainingSessionItemRepository,
    TrainingSessionRepository,
)
from app.users.repository import UserRepository, UserSettingsRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class UnitOfWork:
    def __init__(self, async_session_maker: async_sessionmaker[AsyncSession]):
        self._async_session_maker = async_session_maker
        self.session: AsyncSession | None = None
        self.user_repo: UserRepository | None = None
        self.training_session_repo: TrainingSessionRepository | None = None
        self.card_repo: CardRepository | None = None
        self.deck_repo: DeckRepository | None = None
        self.deck_card_repo: DeckCardRepository | None = None
        self.auth_repo: AuthRepository | None = None
        self.user_deck_repo: UserDeckRepository | None = None
        self.training_session_item_repo: TrainingSessionItemRepository | None = None
        self.user_settings_repo: UserSettingsRepository | None = None

    async def __aenter__(self):
        self.session = self._async_session_maker()
        self.user_repo = UserRepository(self.session)
        self.training_session_repo = TrainingSessionRepository(self.session)
        self.card_repo = CardRepository(self.session)
        self.deck_repo = DeckRepository(self.session)
        self.deck_card_repo = DeckCardRepository(self.session)
        self.auth_repo = AuthRepository(self.session)
        self.user_deck_repo = UserDeckRepository(self.session)
        self.training_session_item_repo = TrainingSessionItemRepository(self.session)
        self.user_settings_repo = UserSettingsRepository(self.session)
        return self

    @traced("uow.close")
    async def __aexit__(self, exc_type, exc, tb):
        try:
            if exc_type is not None and self.session is not None:
                await self.rollback()
        finally:
            if self.session is not None:
                await self.session.close()
            self.session = None
            self.user_repo = None
            self.training_session_repo = None
            self.card_repo = None
            self.deck_repo = None
            self.deck_card_repo = None
            self.auth_repo = None
            self.user_deck_repo = None
            self.training_session_item_repo = None
            self.user_settings_repo = None

    @traced("uow.commit")
    async def commit(self):
        if self.session is None:
            raise RuntimeError("session is not initialized")
        try:
            await self.session.commit()
        except Exception:
            await self.rollback()
            raise

    async def flush(self) -> None:
        if self.session is None:
            raise RuntimeError("session is not initialized")
        await self.session.flush()
    
    @traced("uow.rollback")
    async def rollback(self):
        if self.session is None:
            raise RuntimeError("session is not initialized")
        await self.session.rollback()
