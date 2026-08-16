import asyncio
from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Literal
from uuid import UUID


from app.bff.schemas import (
    CatalogDeckItemResponse,
    HomeDeckItemResponse,
    LibraryCardItemResponse,
    LibraryDeckItemResponse,
    HomeDashboardResponse,
    UserProgressResponse,
)
from app.cards.service import CardService
from app.decks.errors import UserDeckNotFoundError
from app.decks.models import UserDeck
from app.decks.schemas import DeckResponse, DeckViewerStateResponse, InternalDeck, InternalUserDeck
from app.decks.service import DeckService, UserDeckService
from app.deps import UoWFactory
from app.redis.service import (
    RedisCacheService,
)
from app.training_sessions.service import TrainingSessionService
from app.users.schemas import SearchQuery
from app.redis.schemas import UserDeckIdentity
from app.cards.schemas import CardResponse, InternalCard
from app.training_sessions.schemas import PracticeSessionResponse
from app.common.schemas import CursorPage
from app.common.utils import calculate_accuracy, utcnow
from app.common.utils import make_user_deck_identity


logger = logging.getLogger(__name__)

def get_is_favourite(user_deck: UserDeck) -> bool:
    if user_deck is None:
        return False
    
    return user_deck.is_favourite

class BffService:
    def __init__(
        self, 
        uow_factory: UoWFactory,
        cache_service: RedisCacheService,
    ) -> None:
        self.uow_factory = uow_factory
        self.cache_service = cache_service
        self.deck_service = DeckService(
            uow_factory=uow_factory,
            cache_service=cache_service,
        )
        self.user_deck_service = UserDeckService(
            uow_factory=uow_factory,
            cache_service=cache_service,
        )
        self.card_service = CardService(
            uow_factory=uow_factory,
            cache_service=cache_service,
        )
        self.training_session_service = TrainingSessionService(
            uow_factory=self.uow_factory,
            cache_service=cache_service,
        )

    @staticmethod
    def _build_library_deck(
        deck: InternalDeck,
        user_deck: InternalUserDeck,
        cards: list[InternalCard],
    ) -> LibraryDeckItemResponse:
        return LibraryDeckItemResponse(
            deck=DeckResponse.model_validate(obj=deck),
            viewer_state=DeckViewerStateResponse.validate(user_deck=user_deck),
            preview_cards=[
                CardResponse.model_validate(obj=card)
                for card in cards
            ],
        )

    @staticmethod
    def _build_library_card(
        card: InternalCard,
    ) -> LibraryCardItemResponse:
        return LibraryCardItemResponse(
            card=CardResponse.model_validate(card),
        )

    async def get_catalog_page(
        self,
        user_id: int,
        search_query: SearchQuery = None,
        page: int = 1,
        limit: int = 50,
    ) -> list[CatalogDeckItemResponse]:
        decks = await self.deck_service.get_public_decks(
            search_query=search_query,
            page=page,
            limit=limit,
        )
        user_decks = await self.user_deck_service.get_user_decks_by_deck_ids(
            deck_ids=[deck.id for deck in decks],
            user_id=user_id,
        )
        user_decks_by_identity: dict[tuple[int, int], InternalUserDeck] = {}
        for user_deck in user_decks:
            user_decks_by_identity[
                make_user_deck_identity(
                    user_id=user_deck.user_id,
                    deck_id=user_deck.deck_id,
                )
            ] = user_deck

        return [
            CatalogDeckItemResponse(
                deck=DeckResponse.model_validate(deck),
                viewer_state=DeckViewerStateResponse.validate(
                    user_deck=user_decks_by_identity[
                        make_user_deck_identity(
                            user_id=user_id,
                            deck_id=deck.id,
                        )
                    ]
                ) if make_user_deck_identity(
                    user_id=user_id,
                    deck_id=deck.id,
                ) in user_decks_by_identity else None
            )
            for deck in decks
        ]


    async def get_home_dashboard(
            self,
            user_id: int,
            user_uuid: UUID,
        ) -> HomeDashboardResponse:
        decks, cursor, has_more = await self.deck_service.get_all_by_user_uuid(
            user_uuid=user_uuid,
            search_query=None,
            cursor=None,
            limit=6,
            public_only=False,
            current_user_id=user_id,
        )

        user_decks = await self.user_deck_service.get_user_decks_by_deck_ids(
            deck_ids=[deck.id for deck in decks],
            user_id=user_id,
        )
        user_decks_by_deck_id = {
            user_deck.deck_id: user_deck
            for user_deck in user_decks
        }

        today = utcnow().date()
        from_date = today - timedelta(days=6)
        to_date = today + timedelta(days=1)

        daily_activities = await self.training_session_service.user_daily_activity(
            user_id=user_id,
            from_date=from_date,
            to_date=to_date,
        )

        max_value = 0
        for value in list(daily_activities.values()):
            max_value = max(value, max_value)

        user_weekly_activity = []
        while from_date < to_date:
            user_weekly_activity.append(
                {
                    "date": from_date, 
                    "percent": round(
                        daily_activities[from_date] * 100 / max_value
                    ) if max_value > 0 else 0
                }
            ) 
                
            from_date += timedelta(days=1)

        result = HomeDashboardResponse(
            decks=[
                HomeDeckItemResponse(
                    uuid=deck.uuid,
                    owner_uuid=user_uuid,
                    title=deck.title,
                    description=deck.description,
                    words_count=deck.words_count,
                    user_accuracy=calculate_accuracy(
                        user_decks_by_deck_id.get(deck.id, None),
                    ),
                    updated_at=deck.updated_at,
                ) for deck in decks
            ],
            progress=await self.training_session_service.get_user_progress(
                user_id=user_id,
            ),
            user_weekly_activity=user_weekly_activity,
        )
        return result

    async def _fetch_and_cache_library_deck_page_cards_previews(
        self,
        user_id: int,
        deck_uuids: list[UUID],
    ) -> dict[UUID, list[InternalCard]]:
        if not deck_uuids:
            return {}

        fetched_by_deck = (
            await self.deck_service.get_all_cards_by_deck_uuids(
                user_id=user_id,
                deck_uuids=deck_uuids,
                offset=0,
                limit=2,
            )
        )

        all_fetched_cards = [
            card
            for cards in list(fetched_by_deck.values())
            for card in cards
        ]

        await asyncio.gather(
            self.cache_service.cache_deck_cards(
                deck_cards={
                    deck_uuid: [card.uuid for card in cards]
                    for deck_uuid, cards in fetched_by_deck.items()
                }
            ),
            self.cache_service.cache_cards(
                cards=all_fetched_cards,
            ),
        )

        return fetched_by_deck

    async def _get_user_decks_by_deck_ids(
        self,
        user_id: int,
        deck_ids: list[int],
    ) -> dict[UserDeckIdentity, InternalUserDeck]:
        lookup_user_decks = await self.cache_service.get_cached_user_decks(
            user_id=user_id,
            deck_ids=deck_ids,
        )
        user_decks: dict[UserDeckIdentity, UserDeck] = lookup_user_decks.cached
        if lookup_user_decks.missing:
            identities = lookup_user_decks.missing
            missing_deck_ids: list[int] = []
            for identity in identities:
                missing_deck_ids.append(identity[1])
            fetched_user_decks = await self.user_deck_service.get_user_decks_by_deck_ids(
                deck_ids=missing_deck_ids,
                user_id=user_id,
            )
            await self.cache_service.cache_user_decks(
                user_id=user_id,
                user_decks=fetched_user_decks,
            )
            for fetched_user_deck in fetched_user_decks:
                user_decks[
                    (fetched_user_deck.user_id, fetched_user_deck.deck_id)
                ] = fetched_user_deck
        return user_decks

    async def _fetch_and_cache_library_deck_page_decks(
        self,
        user_id: int,
        user_uuid: UUID,
        expected_generation: int | None,
        search_query: SearchQuery = None,
        is_favourite: bool = False,
        cursor: str | None = None,
        limit: int = 50,
    ) -> CursorPage[InternalDeck]:
        """
        source-of-truth чтение library page из БД + кэширование
        """
        if not is_favourite:
            decks, next_cursor, has_more = await self.deck_service.get_all_by_user_uuid(
                user_uuid=user_uuid,
                search_query=search_query,
                cursor=cursor,
                limit=limit,
                public_only=False,
                current_user_id=user_id,
            )
        else:
            decks, next_cursor, has_more = (
                await self.user_deck_service.get_my_favourite_decks(
                    user_id=user_id,
                    search_query=search_query,
                    cursor=cursor,
                    limit=limit,
                )
            )

        await asyncio.gather(
            self.cache_service.cache_library_decks_page(
                user_uuid=user_uuid,
                deck_uuids=[deck.uuid for deck in decks],
                next_cursor=next_cursor,
                has_more=has_more,
                expected_generation=expected_generation,
                search_query=search_query,
                is_favourite=is_favourite,
                cursor=cursor,
                limit=limit,
            ),
            self.cache_service.cache_decks(
                decks=decks,
            ),
        )

        return CursorPage[InternalDeck](
            items=decks,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def get_decks_library_page(
        self,
        user_id: int,
        user_uuid: UUID,
        search_query: SearchQuery = None,
        is_favourite: bool = False,
        cursor: str | None = None,
        limit: int = 50,
    ) -> CursorPage[LibraryDeckItemResponse]:
        library_result = await self._get_decks_library_deck_page(
            user_id=user_id,
            user_uuid=user_uuid,
            search_query=search_query,
            is_favourite=is_favourite,
            cursor=cursor,
            limit=limit,
        )

        if not library_result.items:
            return CursorPage[LibraryDeckItemResponse](
                items=[],
                next_cursor=library_result.next_cursor,
                has_more=library_result.has_more,
            )

        decks = library_result.items

        cards_by_deck, user_decks = await asyncio.gather(
            self._get_cards_library_deck_page(
                user_id=user_id,
                deck_uuids=[deck.uuid for deck in decks],
            ),
            self._get_user_decks_by_deck_ids(
                user_id=user_id,
                deck_ids=[deck.id for deck in decks],
            )
        )
        # проверка, что все UserDecks существуют
        for deck in decks:
            if (user_id, deck.id) not in user_decks:
                raise UserDeckNotFoundError()


        result = CursorPage[LibraryDeckItemResponse](
            items=[
                self._build_library_deck(
                    deck=deck,
                    user_deck=user_decks[(user_id, deck.id)],
                    cards=cards_by_deck[deck.uuid]
                ) for deck in decks
            ],
            next_cursor=library_result.next_cursor,
            has_more=library_result.has_more,
        )
        return result

    async def _get_decks_library_deck_page(
        self,
        user_id: int,
        user_uuid: UUID,
        search_query: SearchQuery,
        is_favourite: bool,
        cursor: str | None,
        limit: int,
    ) -> CursorPage[InternalDeck]:
        page_lookup = await self.cache_service.get_cached_library_decks_page(
            user_uuid=user_uuid,
            search_query=search_query,
            is_favourite=is_favourite,
            cursor=cursor,
            limit=limit,
        )

        if page_lookup.page is None:
            return await self._fetch_and_cache_library_deck_page_decks(
                user_id=user_id,
                user_uuid=user_uuid,
                expected_generation=page_lookup.generation,
                search_query=search_query,
                is_favourite=is_favourite,
                cursor=cursor,
                limit=limit,
            )

        cached_page = page_lookup.page

        if not cached_page.items:
            return CursorPage[InternalDeck](
                items=[],
                next_cursor=cached_page.next_cursor,
                has_more=cached_page.has_more,
            )

        deck_lookup = await self.cache_service.get_cached_decks(
            deck_uuids=cached_page.items,
        )

        decks_by_uuid: dict[UUID, InternalDeck] = dict(
            deck_lookup.cached
        )

        if deck_lookup.missing:
            fetched_decks = await self.deck_service.get_by_uuids(
                deck_uuids=deck_lookup.missing,
            )

            decks_by_uuid.update(
                {
                    deck.uuid: deck
                    for deck in fetched_decks
                }
            )

            await self.cache_service.cache_decks(
                decks=fetched_decks,
            )

        # устаревшие deck_uuids, которых уже нет
        unresolved_deck_uuids = [
            deck_uuid
            for deck_uuid in cached_page.items
            if deck_uuid not in decks_by_uuid
        ]

        if unresolved_deck_uuids:
            # page cache не соответствует БД
            # перечитываем страницу полностью
            return await self._fetch_and_cache_library_deck_page_decks(
                user_id=user_id,
                user_uuid=user_uuid,
                expected_generation=page_lookup.generation,
                search_query=search_query,
                is_favourite=is_favourite,
                cursor=cursor,
                limit=limit,
            )

        return CursorPage[InternalDeck](
            items=[
                decks_by_uuid[deck_uuid]
                for deck_uuid in cached_page.items
            ],
            next_cursor=cached_page.next_cursor,
            has_more=cached_page.has_more,
        )

    async def _get_cards_library_deck_page(
        self,
        user_id: int,
        deck_uuids: list[UUID],
    ) -> dict[UUID, list[InternalCard]]:
        if not deck_uuids:
            return {}

        deck_cards_lookup = await self.cache_service.get_cached_deck_cards(
            deck_uuids=deck_uuids,
        )

        cards_by_deck: dict[UUID, list[InternalCard]] = {}

        if deck_cards_lookup.missing:
            fetched_cards_by_deck = await self._fetch_and_cache_library_deck_page_cards_previews(
                user_id=user_id,
                deck_uuids=deck_cards_lookup.missing,
            )
            cards_by_deck.update(fetched_cards_by_deck)

        cached_card_uuids_by_deck = {
            deck_uuid: card_uuids[:2] # первые 2 карточки
            for deck_uuid, card_uuids
            in deck_cards_lookup.cached.items()
        }

        card_uuids = list(
            dict.fromkeys(
                card_uuid
                for tmp_card_uuids in cached_card_uuids_by_deck.values()
                for card_uuid in tmp_card_uuids
            )
        )

        if not card_uuids:
            return {
                deck_uuid: cards_by_deck.get(deck_uuid, [])
                for deck_uuid in deck_uuids
            }

        card_lookup = await self.cache_service.get_cached_cards(
            card_uuids=card_uuids,
        )

        cards_by_uuid: dict[UUID, InternalCard] = dict(
            card_lookup.cached
        )

        fetched_cards: list[InternalCard] = []

        if card_lookup.missing:
            fetched_cards = await self.card_service.get_by_uuids(
                card_uuids=card_lookup.missing,
            )

            cards_by_uuid.update(
                {
                    card.uuid: card
                    for card in fetched_cards
                }
            )

            await self.cache_service.cache_cards(
                cards=fetched_cards,
            )

        # uuid карточек был в кэше, но самих карточек в бд не нашлось -> кэш deck_cards старый
        unresolved_card_uuids = {
            card_uuid
            for card_uuid in card_lookup.missing
            if card_uuid not in cards_by_uuid
        }

        # какие именно deck_cards ссылаются на несуществующие карточки
        stale_deck_uuids = {
            deck_uuid
            for deck_uuid, card_uuids
            in cached_card_uuids_by_deck.items()
            if unresolved_card_uuids.intersection(card_uuids)
        }

        if stale_deck_uuids:
            refreshed_cards = await self._fetch_and_cache_library_deck_page_cards_previews(
                user_id=user_id,
                deck_uuids=list(stale_deck_uuids),
            )

            cards_by_deck.update(refreshed_cards)


        for deck_uuid, card_uuids in cached_card_uuids_by_deck.items():
            if deck_uuid in stale_deck_uuids:
                continue

            cards_by_deck[deck_uuid] = [
                cards_by_uuid[card_uuid]
                for card_uuid in card_uuids
            ]

        return {
            deck_uuid: cards_by_deck.get(deck_uuid, [])
            for deck_uuid in deck_uuids
        }

    async def _get_cards_library_card_page(
        self,
        user_id: int,
        user_uuid: UUID,
        search_query: SearchQuery = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> CursorPage[InternalCard]:
        cards_page_lookup = await self.cache_service.get_cached_library_cards_page(
            user_uuid=user_uuid,
            search_query=search_query,
            cursor=cursor,
            limit=limit,
        )

        # no cache -> get from db and do cache
        if cards_page_lookup.page is None:
            return await self._fetch_and_cache_cards_library_cards_page(
                user_id=user_id,
                user_uuid=user_uuid,
                expected_generation=cards_page_lookup.generation,
                search_query=search_query,
                cursor=cursor,
                limit=limit,
            )

        cached_page = cards_page_lookup.page


        if not cached_page.items:
            return CursorPage[InternalCard](
                items=[],
                next_cursor=cached_page.next_cursor,
                has_more=cached_page.has_more,
            )

        cards_lookup = await self.cache_service.get_cached_cards(
            card_uuids=cached_page.items,
        )
        cards_by_uuid = cards_lookup.cached

        if cards_lookup.missing:
            fetched_missing_cards = await self.card_service.get_by_uuids(
                card_uuids=cards_lookup.missing,
            )

            for fetched_card in fetched_missing_cards:
                cards_by_uuid[fetched_card.uuid] = fetched_card

            # карточки, которые есть в кэше страницы, но нет в бд
            unresolved_cards = []

            for missing_card_uuid in cards_lookup.missing:
                # проходим по всему списку, можно оптимизировать и пройти только по fetched списку
                if missing_card_uuid not in cards_by_uuid:
                    unresolved_cards.append(missing_card_uuid)

            # если в кэше старое значение, значит кэш где-то не инвалидировался
            # полностью достаем страницу из бд
            if unresolved_cards:
                return await self._fetch_and_cache_cards_library_cards_page(
                    user_id=user_id,
                    user_uuid=user_uuid,
                    expected_generation=cards_page_lookup.generation,
                    search_query=search_query,
                    cursor=cursor,
                    limit=limit,
                )

        return CursorPage[InternalCard](
            items=[
                InternalCard.from_entity(cards_by_uuid[card_uuid])
                for card_uuid in cached_page.items
            ],
            next_cursor=cached_page.next_cursor,
            has_more=cached_page.has_more,
        )

    async def _fetch_and_cache_cards_library_cards_page(
        self,
        user_id: int,
        user_uuid: UUID,
        expected_generation: int | None,
        search_query: SearchQuery = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> CursorPage[InternalCard]:
        
        # no cache -> get from db
        cards, next_cursor, has_more = await self.card_service.get_all_by_user_id(
            user_id=user_id,
            search_query=search_query,
            cursor=cursor,
            limit=limit,
        )

        # caching page and cards
        await asyncio.gather(
            self.cache_service.cache_library_cards_page(
                user_uuid=user_uuid,
                card_uuids=[card.uuid for card in cards],
                expected_generation=expected_generation,
                search_query=search_query,
                cursor=cursor,
                limit=limit,
                next_cursor=next_cursor,
                has_more=has_more,
            ),
            self.cache_service.cache_cards(
                cards=cards,
            ),
        )

        return CursorPage[InternalCard](
            items=[InternalCard.from_entity(card) for card in cards],
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def get_cards_library_page(
            self,
            user_id: int,
            user_uuid: UUID,
            search_query: SearchQuery = None,
            cursor: str | None = None,
            limit: int = 50,
    ) -> CursorPage[LibraryCardItemResponse]:
        cards_page = await self._get_cards_library_card_page(
            user_id=user_id,
            user_uuid=user_uuid,
            search_query=search_query,
            cursor=cursor,
            limit=limit,
        )

        return CursorPage[LibraryCardItemResponse](
            items=[
                self._build_library_card(card) for card in cards_page.items
            ],
            next_cursor=cards_page.next_cursor,
            has_more=cards_page.has_more,
        )

    async def start_practice_session(
            self,
            user_id: int,
            deck_uuid: UUID,
            prompt_side: Literal["front", "back"],
    ) -> PracticeSessionResponse:
        response = await self.training_session_service.start_training_session(
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
        response = await self.training_session_service.resume_practice_session(
            user_id=user_id,
            training_session_uuid=training_session_uuid,
        )
        return response
