from collections import defaultdict
from typing import Literal
from uuid import UUID

from app.bff.schemas import (
    CardLibraryPage,
    DeckDashboard,
    DeckLibraryPage,
    HomeDashboard,
    PracticeCard,
    PracticeSessionResponse,
    UserProgress,
)
from app.bff.utils import calculate_accuracy
from app.cards.errors import PermissionDeniedError
from app.cards.models import Card
from app.cards.service import CardService
from app.decks.errors import DeckIsEmptyError, DeckNotFoundError
from app.decks.models import UserDeck
from app.decks.schemas import CursorPage
from app.decks.service import DeckService, UserDeckService
from app.deps import UoWFactory
from app.training_sessions.errors import (
    TrainingSessionAlreadyFinishedError,
    TrainingSessionNotFoundError,
)
from app.training_sessions.models import TrainingSession
from app.utils import decode_cursor
from app.training_sessions.service import TrainingSessionService
from app.users.schemas import SearchQuery


def get_is_favourite(user_deck: UserDeck) -> bool:
    if user_deck is None:
        return False
    
    return user_deck.is_favourite

class BffService:
    def __init__(self, uow_factory: UoWFactory) -> None:
        self.uow_factory = uow_factory

    async def get_home_dashboard(
            self,
            user_id: int,
            user_uuid: UUID,
        ) -> HomeDashboard:
        deck_service = DeckService(uow_factory=self.uow_factory)
        decks, cursor, has_more = await deck_service.get_all_by_user_uuid(
            user_uuid=user_uuid,
            search_query=None,
            cursor=None,
            limit=6,
            public_only=False,
            current_user_id=user_id,
        )

        user_deck_service = UserDeckService(uow_factory=self.uow_factory)
        user_decks = await user_deck_service.get_user_decks_by_deck_ids(
            deck_ids=[deck.id for deck in decks],
            user_id=user_id,
        )
        user_decks_by_deck_id = {
            user_deck.deck_id: user_deck
            for user_deck in user_decks
        }

        user_weekly_activity = [
            { "date": "2026-07-12", "percent": 55 },
            { "date": "2026-07-13", "percent": 67 },
            { "date": "2026-07-14", "percent": 32 },
            { "date": "2026-07-15", "percent": 12 },
            { "date": "2026-07-16", "percent": 0 },
            { "date": "2026-07-17", "percent": 38 },
            { "date": "2026-07-18", "percent": 100 }
        ]


        result = HomeDashboard(
            decks=[
                DeckDashboard(
                    deck_uuid=deck.uuid,
                    owner_uuid=user_uuid,
                    title=deck.title,
                    description=deck.description,
                    deck_words_count=deck.words_count,
                    user_accuracy=calculate_accuracy(
                        user_decks_by_deck_id.get(deck.id, None),
                    ),
                    updated_at=deck.updated_at,
                ) for deck in decks
            ],
            progress=UserProgress(
                user_words_explored=67,
                user_weekly_accuracy=55,
                user_current_streak=6,
                user_total_study_time=120,
            ),
            user_weekly_activity=user_weekly_activity,
        )
        return result

    async def get_decks_library_page(
        self,
        user_id: int,
        user_uuid: UUID,
        search_query: SearchQuery = None,
        is_favourite: bool = False,
        cursor: str | None = None,
        limit: int = 50,
    ) -> CursorPage[DeckLibraryPage]:

        deck_service = DeckService(uow_factory=self.uow_factory)
        user_deck_service = UserDeckService(uow_factory=self.uow_factory)
        if not is_favourite:
            decks, next_cursor, has_more = await deck_service.get_all_by_user_uuid(
                user_uuid=user_uuid,
                search_query=search_query,
                cursor=cursor,
                limit=limit,
                public_only=False,
                current_user_id=user_id,
            )
        else:
            decks, next_cursor, has_more = (
                await user_deck_service.get_favourite_decks(
                    user_id=user_id,
                    cursor=cursor,
                    limit=limit,
                )
            )

        user_decks = await user_deck_service.get_user_decks_by_deck_ids(
            deck_ids=[deck.id for deck in decks],
            user_id=user_id,
        )
        user_decks_by_deck_id = {
            user_deck.deck_id: user_deck
            for user_deck in user_decks
        }

        cards = await deck_service.get_all_cards_by_deck_ids(
            user_id=user_id,
            deck_ids=[deck.id for deck in decks],
            offset=0,
            limit=2,
        )

        deck_cards_by_deck_id: dict[int, list[Card]] = defaultdict(list)
        for deck_id, card in cards:
            deck_cards_by_deck_id[deck_id].append(card)

        result = CursorPage[DeckLibraryPage](
            items=[
                DeckLibraryPage(
                    deck_uuid=deck.uuid,
                    owner_uuid=deck.owner_uuid,
                    title=deck.title,
                    description=deck.description,
                    deck_words_count=deck.words_count,
                    user_accuracy=calculate_accuracy(
                        user_decks_by_deck_id.get(deck.id, None),
                    ),
                    is_favourite=(
                        get_is_favourite(
                            user_decks_by_deck_id.get(deck.id, None)
                        )
                    ),
                    updated_at=deck.updated_at,
                    cards=[
                        CardLibraryPage(
                            card_uuid=card.uuid,
                            front_text=card.front_text,
                            back_text=card.back_text,
                            front_lang=card.front_lang,
                            back_lang=card.back_lang,
                            updated_at=card.updated_at,
                        ) for card in deck_cards_by_deck_id[deck.id]
                    ]
                ) for deck in decks
            ],
            next_cursor=next_cursor,
            has_more=has_more,
        )
        return result

    async def get_cards_library_page(
            self,
            user_id: int,
            user_uuid: UUID,
            cursor: str | None = None,
            limit: int = 50,
    ) -> CursorPage[CardLibraryPage]:
        cursor_updated_at, cursor_id = (
            decode_cursor(cursor) if cursor is not None else (None, None)
        )

        card_service = CardService(uow_factory=self.uow_factory)
        cards, next_cursor, has_more = await card_service.get_all_by_user_id(
            user_id=user_id,
            cursor=cursor,
            limit=limit,
        )


        result = CursorPage[CardLibraryPage](
            items=[
                CardLibraryPage(
                    card_uuid=card.uuid,
                    front_text=card.front_text,
                    back_text=card.back_text,
                    front_lang=card.front_lang,
                    back_lang=card.back_lang,
                    updated_at=card.updated_at,
                ) for card in cards
            ],
            next_cursor=next_cursor,
            has_more=has_more,
        )
        return result

    async def start_practice_session(
            self,
            user_id: int,
            deck_uuid: UUID,
            prompt_side: Literal["front", "back"],
    ) -> PracticeSessionResponse:
        training_session_service = TrainingSessionService(uow_factory=self.uow_factory)
        response = await training_session_service.start_training_session(
            user_id=user_id,
            deck_uuid=deck_uuid,
            prompt_side=prompt_side,
        )
        return response

    async def resume_practice_session(
            self,
            user_id: int,
            training_session_uuid: UUID,
    ) -> PracticeSessionResponse:
        training_session_service = TrainingSessionService(uow_factory=self.uow_factory)
        response = await training_session_service.resume_practice_session(
            user_id=user_id,
            training_session_uuid=training_session_uuid,
        )
        return response