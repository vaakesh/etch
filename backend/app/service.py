from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.repository import AuthRepository
from app.card_memory.repository import CardMemoryRepository
from app.cards.repository import CardRepository
from app.decks.repository import DeckCardRepository, DeckRepository, UserDeckRepository
from app.outbox.repository import OutboxRepository
from app.tracing import traced
from app.training_sessions.repository import (
    TrainingSessionItemRepository,
    TrainingSessionRepository,
)
from app.users.repository import UserRepository, UserSettingsRepository


class UnitOfWork:
    # session and repositories exist only inside `async with uow:`
    session: AsyncSession
    user_repo: UserRepository
    training_session_repo: TrainingSessionRepository
    card_repo: CardRepository
    deck_repo: DeckRepository
    deck_card_repo: DeckCardRepository
    auth_repo: AuthRepository
    user_deck_repo: UserDeckRepository
    training_session_item_repo: TrainingSessionItemRepository
    user_settings_repo: UserSettingsRepository
    outbox_repo: OutboxRepository
    card_memory_repo: CardMemoryRepository

    def __init__(self, async_session_maker: async_sessionmaker[AsyncSession]):
        self._async_session_maker = async_session_maker

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
        self.outbox_repo = OutboxRepository(self.session)
        self.card_memory_repo = CardMemoryRepository(self.session)
        return self

    @traced("uow.close")
    async def __aexit__(self, exc_type, exc, tb):
        try:
            if exc_type is not None:
                await self.rollback()
        finally:
            await self.session.close()

    @traced("uow.commit")
    async def commit(self):
        try:
            await self.session.commit()
        except Exception:
            await self.rollback()
            raise

    async def flush(self) -> None:
        await self.session.flush()

    @traced("uow.rollback")
    async def rollback(self):
        await self.session.rollback()
