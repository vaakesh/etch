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
        is_favourite: bool = False,
        cursor: str | None = None,
        limit: int = 50,
    ) -> CursorPage[DeckLibraryPage]:

        deck_service = DeckService(uow_factory=self.uow_factory)
        user_deck_service = UserDeckService(uow_factory=self.uow_factory)
        if not is_favourite:
            decks, next_cursor, has_more = await deck_service.get_all_by_user_uuid(
                user_uuid=user_uuid,
                search_query=None,
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
                    owner_uuid=user_uuid,
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
                            source_lang=card.source_lang,
                            target_lang=card.target_lang,
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
                    source_lang=card.source_lang,
                    target_lang=card.target_lang,
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
        async with self.uow_factory() as uow:
            deck = await uow.deck_repo.get_by_uuid(
                deck_uuid=deck_uuid,
                for_update=True,
            )

            if deck is None:
                raise DeckNotFoundError()

            if deck.user_id != user_id and not deck.is_public:
                raise PermissionDeniedError()


            user_deck = await uow.user_deck_repo.get_by_user_id_and_deck_id(
                user_id=user_id,
                deck_id=deck.id,
            )
            if user_deck is None:
                user_deck = UserDeck(
                    user_id=user_id,
                    deck_id=deck.id,
                    sessions_count=0,
                    correct_count=0,
                    wrong_count=0,
                )
                uow.user_deck_repo.add(user_deck)

            answer_side = "back" if prompt_side == "front" else "front"

            training_session = TrainingSession(
                user_id=user_id,
                deck_id=deck.id,
                requested_count=0,
                actual_count=0,
                correct_count=0,
                wrong_count=0,
                prompt_side=prompt_side,
                answer_side=answer_side,
            )


            uow.training_session_repo.add(training_session)
            await uow.flush()

            training_session_items = await uow.training_session_item_repo.create_snapshot(
                training_session_id=training_session.id,
                deck_id=deck.id,
                prompt_side=prompt_side,
                answer_side=answer_side,
            )
            if not training_session_items:
                raise DeckIsEmptyError()
            
            training_session.requested_count = len(training_session_items)

            response = PracticeSessionResponse(
                training_session_uuid=training_session.uuid,
                deck_uuid=deck.uuid,
                prompt_side=training_session.prompt_side,
                answer_side=training_session.answer_side,
                total_count=training_session.requested_count,
                answered_count=training_session.actual_count,
                correct_count=training_session.correct_count,
                wrong_count=training_session.wrong_count,
                started_at=training_session.started_at,
                cards=[PracticeCard(
                    sequence_number=item.sequence_number,
                    prompt_text=item.prompt_text,
                    prompt_language=item.prompt_lang,
                    answer_language=item.answer_lang,
                ) for item in training_session_items]
            )

            await uow.commit()

            return response

    async def resume_practice_session(
            self,
            user_id: int,
            training_session_uuid: UUID,
    ) -> PracticeSessionResponse:
        async with self.uow_factory() as uow:
            training_session = await uow.training_session_repo.get_by_uuid(
                training_session_uuid,
            )

            if training_session is None or training_session.user_id != user_id:
                raise TrainingSessionNotFoundError()

            if training_session.finished_at is not None:
                raise TrainingSessionAlreadyFinishedError()

            deck = await uow.deck_repo.get_by_id(training_session.deck_id)

            if deck is None:
                raise DeckNotFoundError()

            training_session_next_cards = (
                await uow.training_session_item_repo.get_next_cards(
                    training_session_id=training_session.id,
                )
            )

            return PracticeSessionResponse(
                training_session_uuid=training_session.uuid,
                deck_uuid=deck.uuid,
                prompt_side=training_session.prompt_side,
                answer_side=training_session.answer_side,
                total_count=training_session.requested_count,
                answered_count=training_session.actual_count,
                correct_count=training_session.correct_count,
                wrong_count=training_session.wrong_count,
                started_at=training_session.started_at,
                cards=[PracticeCard(
                    sequence_number=item.sequence_number,
                    prompt_text=item.prompt_text,
                    prompt_language=item.prompt_lang,
                    answer_language=item.answer_lang,
                ) for item in training_session_next_cards]
            )
