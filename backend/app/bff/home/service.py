from collections import defaultdict
from typing import Callable
from uuid import UUID
from datetime import datetime
from app.service import UnitOfWork
from app.bff.home.schemas import CardsLibraryPage, DeckDashboard, DeckForDeckPage, DeckPageData, DeckPageFavouritesDecks, HomeDashboard, ResponseCardsLibraryPage, UserProgress
from app.decks.models import UserDeck
from app.cards.models import Card
from app.decks.schemas import DeckWithUserData
from app.bff.utils import calculate_accuracy, decode_cursor, encode_cursor


def get_is_favourite(user_deck: UserDeck) -> bool:
    if user_deck is None:
        return False
    
    return user_deck.is_favourite

class BffService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def get_home_dashboard(self, user_id: int) -> HomeDashboard:
        async with self.uow_factory() as uow:
            user = await uow.user_repo.get_by_id(user_id=user_id)
            decks = await uow.deck_repo.get_all_by_user_id(
                user_id=user.id,
                limit=6,
            )
            user_decks = await uow.deck_repo.get_user_statistics_by_decks(
                deck_ids=[deck.id for deck in decks],
                user_id=user.id,
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
                decks=[DeckDashboard(
                    title=deck.title,
                    description=deck.description,
                    deck_total_words_count=deck.words_count,
                    user_accuracy=calculate_accuracy(
                        user_decks_by_deck_id.get(deck.id)
                    ),
                    updated_at=deck.updated_at,
                ) for deck in decks],
                progress=UserProgress(
                    user_words_explored=67,
                    user_weekly_accuracy=55,
                    user_current_streak=6,
                    user_total_study_time=120,
                ),
                user_weekly_activity=user_weekly_activity,
            )
            return result
    
    async def get_favourite_decks_by_user_id(
            self,
            user_id:int,
            cursor: str | None = None,
    ) -> DeckPageFavouritesDecks:
        async with self.uow_factory() as uow:
            decoded_cursor = decode_cursor(cursor) if cursor is not None else None

            decks, has_more = await uow.user_deck_repo.get_favourite_decks_by_user_id(
                user_id=user_id,
                limit=16,
                cursor=decoded_cursor,
            ) # получаем decks с пустыми cards
            deck_ids = [deck.deck_id for deck in decks]
            cards = await uow.deck_card_repo.get_all_by_deck_ids(
                deck_ids=deck_ids,
                limit=2,
            )
            deck_cards_by_deck_id: dict[int, list[Card]] = defaultdict(list)
            for deck_id, card in cards:
                deck_cards_by_deck_id[deck_id].append(card)
            
            for deck in decks:
                deck.cards = deck_cards_by_deck_id[deck.deck_id]

            next_cursor = None
            if has_more and decks:
                last_deck = decks[-1]
                next_cursor = encode_cursor(
                    updated_at=last_deck.updated_at,
                    entity_id=last_deck.deck_id,
                )
            
            result = DeckPageFavouritesDecks(
                decks=[DeckWithUserData.model_validate(deck) for deck in decks],
                next_cursor=next_cursor,
                has_more=has_more,
            )
            return result
        


    async def get_deck_page_data(self, user_id: int, cursor: str | None = None) -> DeckPageData:
        async with self.uow_factory() as uow:
            decoded_cursor = decode_cursor(cursor) if cursor is not None else None

            decks, has_more = await uow.deck_repo.get_page_by_user_id(
                user_id=user_id,
                limit=20,
                cursor=decoded_cursor,
            )

            next_cursor = None
            if has_more and decks:
                last_deck = decks[-1]
                next_cursor = encode_cursor(
                    updated_at=last_deck.updated_at,
                    entity_id=last_deck.id,
                )
            
            user_decks = await uow.deck_repo.get_user_statistics_by_decks(
                deck_ids=[deck.id for deck in decks],
                user_id=user_id,
            )
            user_decks_by_deck_id = {
                user_deck.deck_id: user_deck
                for user_deck in user_decks
            }

            cards = await uow.deck_card_repo.get_all_by_deck_ids(
                [deck.id for deck in decks],
                limit=2,
            )
            deck_cards_by_deck_id: dict[int, list[Card]] = defaultdict(list)
            for deck_id, card in cards:
                deck_cards_by_deck_id[deck_id].append(card)

            result = DeckPageData(
                decks=[DeckForDeckPage(
                    uuid=deck.uuid,
                    title=deck.title,
                    description=deck.description,
                    deck_total_words_count=deck.words_count,
                    user_accuracy=calculate_accuracy(user_decks_by_deck_id.get(deck.id)),
                    is_favourite=get_is_favourite(user_decks_by_deck_id.get(deck.id)),
                    updated_at=deck.updated_at,
                    cards=deck_cards_by_deck_id.get(deck.id, []),
                ) for deck in decks],
                next_cursor=next_cursor,
                has_more=has_more,
            )
            return result
        
    async def get_cards_library_page_by_user_id(
            self,
            user_id: int,
            user_uuid: UUID,
            cursor: str,
    ) -> ResponseCardsLibraryPage:
        async with self.uow_factory() as uow:
            decoded_cursor = decode_cursor(cursor) if cursor is not None else None
            cards, has_more = await uow.card_repo.get_cards_library_page(
                user_id=user_id,
                user_uuid=user_uuid,
                cursor=decoded_cursor,
                limit=50,
            )

            next_cursor = None
            if cards and has_more:
                last_card = cards[-1]
                next_cursor = encode_cursor(
                    last_card.updated_at,
                    last_card.id,
                )
            
            result = ResponseCardsLibraryPage(
                cards=cards,
                cursor=next_cursor,
                has_more=has_more,
            )
            return result
