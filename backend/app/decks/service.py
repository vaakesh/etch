from collections.abc import Callable
from uuid import UUID

from app.cards.errors import CardNotFoundError
from app.cards.models import Card
from app.cards.schemas import (
    CreateCardRequest,
    InternalCard,
    LoadCardsResponse,
    LoadedCardResponse,
)
from app.common.types import SearchQuery
from app.common.utils import calculate_accuracy, decode_cursor, encode_cursor
from app.redis.service import RedisCacheService
from app.service import UnitOfWork
from app.users.errors import UserNotFoundError
from sqlalchemy.exc import IntegrityError

from .errors import (
    CannotSaveOwnDeckError,
    DeckAlreadyExistsError,
    DeckCardAlreadyExistsError,
    DeckCardNotFoundError,
    DeckIsNotFavouriteError,
    DeckIsNotSavedError,
    DeckNotFoundError,
    InvalidDeckCardPositionError,
    PermissionDeniedError,
)
from .models import Deck, DeckCard, UserDeck
from .schemas import (
    CreateDeckRequest,
    DeckCardResponse,
    DeckListItemResponse,
    DeckResponse,
    DeckViewerStateResponse,
    InternalDeck,
    InternalDeckCard,
    InternalUserDeck,
    UpdateDeckRequest,
)


class DeckService:
    def __init__(
        self, 
        uow_factory: Callable[[], UnitOfWork],
        cache_service: RedisCacheService,
    ) -> None:
        self.uow_factory = uow_factory
        self.cache_service = cache_service

    async def get_public_decks(
        self,
        search_query: SearchQuery = None,
        page: int = 1,
        limit: int = 50,
    ) -> list[InternalDeck]:
        async with self.uow_factory() as uow:
            offset = (page - 1) * limit
            decks = await uow.deck_repo.get_public_decks(
                search_query=search_query,
                limit=limit,
                offset=offset,
            )
            return [InternalDeck.from_entity(deck) for deck in decks]

    async def load_cards_to_deck(
        self,
        deck_uuid: UUID,
        cards: list[CreateCardRequest],
        user_id: int,
        user_uuid: UUID,
    ) -> LoadCardsResponse:
        async with self.uow_factory() as uow:
            deck = await self._get_by_uuid(
                uow=uow,
                deck_uuid=deck_uuid,
                for_update=True,
            )

            if deck.user_id != user_id:
                raise PermissionDeniedError()

            max_position = await uow.deck_card_repo.get_max_position(
                deck_id=deck.id,
            )
            first_position = (max_position or 0) + 1

            card_entities = [
                Card(
                    user_id=user_id,
                    **card.model_dump()
                )
                for card in cards
            ]

            uow.card_repo.add_all(card_entities)
            await uow.flush()

            links = [
                DeckCard(
                    deck_id=deck.id,
                    card_id=card.id,
                    position=first_position + index,
                )
                for index, card in enumerate(card_entities)
            ]

            uow.deck_card_repo.add_all(links)

            deck.words_count += len(card_entities)
            deck.version += 1

            await uow.commit()

            await self.cache_service.invalidate_deck_cards(
                deck_uuids=[deck_uuid],
            )

            await self.cache_service.invalidate_decks(
                deck_uuids=[deck_uuid],
            )

            await self.cache_service.invalidate_library_card_page(
                user_uuid=user_uuid,
            )

            return LoadCardsResponse(
                imported_count=len(card_entities),
                cards=[
                    LoadedCardResponse(
                        uuid=card.uuid,
                        position=link.position,
                    )
                    for card, link in zip(card_entities, links, strict=True)
                ]
            )

    async def get_by_uuids(
        self,
        deck_uuids: list[UUID],
    ) -> list[InternalDeck]:
        async with self.uow_factory() as uow:
            decks = await uow.deck_repo._get_by_uuids(
                deck_uuids=deck_uuids,
                for_update=False,
            )
            return [InternalDeck.model_validate(deck) for deck in decks]

    async def get_by_uuid(
            self, 
            deck_uuid: UUID,
            current_user_id: int | None = None,
        ) -> InternalDeck:
        async with self.uow_factory() as uow:
            deck = await self._get_by_uuid(uow, deck_uuid)
            if not deck.is_public:
                if current_user_id is None or current_user_id != deck.user_id:
                    raise DeckNotFoundError()
            return InternalDeck.model_validate(deck)

    async def _get_by_uuid(
        self,
        uow: UnitOfWork,
        deck_uuid: UUID,
        for_update: bool = False,
    ) -> Deck:
        deck = await uow.deck_repo.get_by_uuid(
            deck_uuid,
            for_update=for_update,
        )

        if deck is None:
            raise DeckNotFoundError(f"Deck with uuid={deck_uuid} not found")

        return deck

    async def _get_card_by_uuid(
        self,
        uow: UnitOfWork,
        card_uuid: UUID,
        for_update: bool = False,
    ):
        card = await uow.card_repo.get_by_uuid(
            card_uuid,
            for_update=for_update,
        )

        if card is None:
            raise CardNotFoundError(f"Card with uuid={card_uuid} not found")

        return card

    async def _get_deck_card_by_uuid(
        self,
        uow: UnitOfWork,
        deck_card_uuid: UUID,
    ) -> DeckCard:
        deck_card = await uow.deck_card_repo.get_by_uuid(deck_card_uuid)

        if deck_card is None:
            raise DeckCardNotFoundError(
                f"Deck card link with uuid={deck_card_uuid} not found"
            )

        return deck_card

    async def get_all_by_user_uuid(
        self,
        user_uuid: UUID,
        search_query: str | None = None,
        cursor: str | None = None,
        limit: int = 10,
        public_only: bool = True,
        current_user_id: int | None = None,
    ) -> tuple[list[InternalDeck], str | None, bool]:
        async with self.uow_factory() as uow:
            user = await uow.user_repo.get_by_uuid(user_uuid=user_uuid)
            if user is None:
                raise UserNotFoundError()

            if not public_only:
                if current_user_id is None or current_user_id != user.id:
                    raise PermissionDeniedError()

            cursor_updated_at, cursor_id = (
                decode_cursor(cursor) if cursor is not None else (None, None)
            )
            decks, has_more = await uow.deck_repo.get_all_by_user_id(
                user_id=user.id,
                search_query=search_query,
                cursor_updated_at=cursor_updated_at,
                cursor_id=cursor_id,
                limit=limit,
                public_only=public_only,
            )

            next_cursor = None
            if decks and has_more:
                next_cursor = encode_cursor(
                    time_condition=decks[-1].updated_at,
                    entity_id=decks[-1].id,
                )

            return [InternalDeck.model_validate(deck) for deck in decks], next_cursor, has_more

    async def create_deck(
        self,
        payload: CreateDeckRequest,
        user_id: int,
        user_uuid: UUID,
    ) -> InternalDeck:
        try:
            async with self.uow_factory() as uow:
                deck = Deck(
                    **payload.model_dump(),
                    user_id=user_id,
                )

                uow.deck_repo.add(deck)

                await uow.flush()
                user_deck = UserDeck(
                    user_id=user_id,
                    deck_id=deck.id,
                    last_seen_version=deck.version,
                )
                uow.user_deck_repo.add(user_deck)
                await uow.commit()

                await self.cache_service.invalidate_library_deck_page(
                    user_uuid=user_uuid,
                )

                return InternalDeck(
                    id=deck.id,
                    uuid=deck.uuid,
                    owner_uuid=user_uuid,
                    title=deck.title,
                    description=deck.description,
                    words_count=deck.words_count,
                    is_public=deck.is_public,
                    saves_count=deck.saves_count,
                    version=deck.version,
                    created_at=deck.created_at,
                    updated_at=deck.updated_at,
                )

        except IntegrityError as e:
            raise DeckAlreadyExistsError() from e

    async def update_deck(
        self,
        user_id: int,
        user_uuid: UUID,
        deck_uuid: UUID,
        payload: UpdateDeckRequest,
    ) -> InternalDeck:
        try:
            async with self.uow_factory() as uow:
                deck = await self._get_by_uuid(
                    uow=uow, 
                    deck_uuid=deck_uuid,
                    for_update=True,
                )

                if deck.user_id != user_id:
                    raise PermissionDeniedError()

                update_data = payload.model_dump(exclude_unset=True)
                update_data["version"] = deck.version + 1
                for field, value in update_data.items():
                    setattr(deck, field, value)

                await uow.commit()
                await uow.deck_repo.refresh(deck)

                await self.cache_service.invalidate_user_decks(
                    identities=[(user_id, deck.id)]
                )

                await self.cache_service.invalidate_decks(
                    deck_uuids=[deck.uuid],
                )

                await self.cache_service.invalidate_library_deck_page(
                    user_uuid=user_uuid,
                )

                return InternalDeck(
                    id=deck.id,
                    uuid=deck.uuid,
                    owner_uuid=user_uuid,
                    title=deck.title,
                    description=deck.description,
                    words_count=deck.words_count,
                    saves_count=deck.saves_count,
                    is_public=deck.is_public,
                    version=deck.version,
                    created_at=deck.created_at,
                    updated_at=deck.updated_at,
                )

        except IntegrityError as e:
            raise DeckAlreadyExistsError() from e

    async def delete_deck(
            self, 
            deck_uuid: UUID,
            user_id: int,
            user_uuid: UUID,
        ) -> None:
        async with self.uow_factory() as uow:
            deck = await self._get_by_uuid(uow, deck_uuid)

            if deck.user_id != user_id:
                raise PermissionDeniedError()

            await uow.deck_repo.delete(deck)
            await uow.commit()

            await self.cache_service.invalidate_user_decks(
                identities=[(user_id, deck.id)]
            )

            await self.cache_service.invalidate_decks(
                deck_uuids=[deck.uuid],
            )

            await self.cache_service.invalidate_deck_cards(
                deck_uuids=[deck.uuid],
            )

            await self.cache_service.invalidate_library_deck_page(
                user_uuid=user_uuid,
            )

            return None

    async def get_deck_cards(
        self,
        user_id: int | None,
        deck_uuid: UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> list[InternalCard]:
        async with self.uow_factory() as uow:
            deck = await self._get_by_uuid(uow, deck_uuid)

            if not deck.is_public:
                if user_id is None or user_id != deck.user_id:
                    raise DeckNotFoundError()

            cards = await uow.deck_card_repo.get_all_by_deck_id(
                deck_id=deck.id,
                offset=offset,
                limit=limit,
            )

            return [InternalCard.model_validate(card) for card in cards]

    async def get_all_cards_by_deck_ids(
        self,
        user_id: int,
        deck_ids: list[int],
        offset: int = 0,
        limit: int = 2,
    ) -> list[tuple[int, InternalCard]]:
        async with self.uow_factory() as uow:
            cards = await uow.deck_card_repo.get_all_cards_by_deck_ids(
                deck_ids=deck_ids,
                limit=limit,
            )
            return [(deck_id, InternalCard.model_validate(card)) for deck_id, card in cards]

    async def get_all_cards_by_deck_uuids(
        self,
        user_id: int,
        deck_uuids: list[UUID],
        offset: int = 0,
        limit: int = 2,
    ) -> dict[UUID, list[InternalCard]]:
        """
        returns only existing decks with its cards including empty decks
        """
        async with self.uow_factory() as uow:
            cards_by_deck = await uow.deck_card_repo.get_all_cards_by_deck_uuids(
                deck_uuids=deck_uuids,
                limit=limit,
            )
            return {
                deck_uuid: [InternalCard.model_validate(card) for card in cards]
                for deck_uuid, cards in cards_by_deck.items()
            }

    async def add_card_to_deck(
        self,
        user_id: int,
        user_uuid: UUID,
        deck_uuid: UUID,
        card_uuid: UUID,
    ) -> InternalDeckCard:
        try:
            async with self.uow_factory() as uow:
                deck = await self._get_by_uuid(
                    uow=uow,
                    deck_uuid=deck_uuid,
                    for_update=True,
                )

                card = await self._get_card_by_uuid(
                    uow, 
                    card_uuid,
                    for_update=True,
                )

                if deck.user_id != user_id or card.user_id != user_id:
                    raise PermissionDeniedError()

                deck_card = await uow.deck_card_repo.get_by_deck_id_and_card_id(
                    deck_id=deck.id,
                    card_id=card.id,
                )

                if deck_card is not None:
                    raise DeckCardAlreadyExistsError()

                deck.words_count += 1
                deck.version += 1

                max_position = await uow.deck_card_repo.get_max_position(
                    deck_id=deck.id,
                )
                if max_position is None:
                    next_position = 1
                else:
                    next_position = max_position + 1

                deck_card = DeckCard(
                    deck_id=deck.id,
                    card_id=card.id,
                    position=next_position,
                )

                uow.deck_card_repo.add(deck_card)

                await uow.commit()
                await uow.deck_card_repo.refresh(deck_card=deck_card)

                await self.cache_service.invalidate_user_decks(
                    identities=[(user_id, deck.id)]
                )

                await self.cache_service.invalidate_library_deck_page(
                    user_uuid=user_uuid,
                )

                await self.cache_service.invalidate_decks(
                    deck_uuids=[deck_uuid],
                )

                await self.cache_service.invalidate_deck_cards(
                    deck_uuids=[deck_uuid],
                )

                return InternalDeckCard.model_validate(obj=deck_card)
        except IntegrityError as e:
            raise DeckCardAlreadyExistsError() from e

    async def remove_card_from_deck(
        self,
        user_id: int,
        user_uuid: UUID,
        deck_uuid: UUID,
        card_uuid: UUID,
    ) -> None:
        async with self.uow_factory() as uow:
            deck = await self._get_by_uuid(
                uow=uow, 
                deck_uuid=deck_uuid,
                for_update=True,
            )

            card = await self._get_card_by_uuid(
                uow=uow, 
                card_uuid=card_uuid,
                for_update=True,
            )

            if deck.user_id != user_id or card.user_id != user_id:
                raise PermissionDeniedError()

            deck_card = await uow.deck_card_repo.get_by_deck_id_and_card_id(
                deck_id=deck.id,
                card_id=card.id,
            )

            if deck_card is None:
                raise DeckCardNotFoundError(
                    f"Card with uuid={card_uuid} not found in deck uuid={deck_uuid}"
                )


            deck.words_count -= 1
            deck.version += 1

            await uow.deck_card_repo.delete(deck_card)
            await uow.flush()
            await uow.deck_card_repo.update_deck_cards_positions_after_deleting(
                deck_id=deck.id,
                deleted_position=deck_card.position,
            )
            await uow.commit()

            await self.cache_service.invalidate_user_decks(
                identities=[(user_id, deck.id)]
            )

            await self.cache_service.invalidate_library_deck_page(
                user_uuid=user_uuid,
            )

            await self.cache_service.invalidate_decks(
                deck_uuids=[deck_uuid],
            )

            await self.cache_service.invalidate_deck_cards(
                deck_uuids=[deck_uuid],
            )

            return None
        
    async def reorder_cards(
            self,
            user_id: int,
            deck_uuid: UUID,
            card_uuid: UUID,
            to_position: int,
    ):
        async with self.uow_factory() as uow:
            card = await self._get_card_by_uuid(
                uow,
                card_uuid=card_uuid,
            )
            deck = await self._get_by_uuid(
                uow,
                deck_uuid=deck_uuid,
                for_update=True,
            )
            if card.user_id != user_id or deck.user_id != user_id:
                raise PermissionDeniedError()

            if not 1 <= to_position <= deck.words_count:
                raise InvalidDeckCardPositionError()
            
            deck_card = await uow.deck_card_repo.get_by_deck_id_and_card_id(
                deck_id=deck.id,
                card_id=card.id,
            )

            if deck_card is None:
                raise DeckCardNotFoundError()
            
            from_position = deck_card.position
            if from_position >= to_position:
                start, end, add_to_position = to_position, from_position, 1
            else:
                start, end, add_to_position = from_position + 1, to_position + 1, -1

            await uow.deck_card_repo.reorder_cards(
                deck_id=deck.id,
                start=start,
                end=end,
                add_to_position=add_to_position,
            )
            deck_card.position = to_position
            await uow.commit()

            await self.cache_service.invalidate_deck_cards(
                deck_uuids=[deck_uuid],
            )


class UserDeckService:
    def __init__(
        self, 
        uow_factory: Callable[[], UnitOfWork],
        cache_service: RedisCacheService,
    ) -> None:
        self.uow_factory = uow_factory
        self.cache_service = cache_service

    async def unsave_deck(
        self,
        user_id: int,
        user_uuid: UUID,
        deck_uuid: UUID,
    ) -> InternalUserDeck:
        async with self.uow_factory() as uow:
            deck = await uow.deck_repo.get_by_uuid_and_is_public(deck_uuid=deck_uuid)
            if deck is None or not deck.is_public:
                raise DeckNotFoundError()
            if deck.user_id == user_id:
                raise CannotSaveOwnDeckError()
            
            user_deck = await uow.user_deck_repo.get_by_user_id_and_deck_id(
                user_id=user_id,
                deck_id=deck.id,
            )
            if user_deck is None:
                raise DeckIsNotSavedError()
            if user_deck.is_saved is True:
                user_deck.is_saved = False
                deck.saves_count -= 1

            await uow.commit()

            await self.cache_service.invalidate_user_decks(
                identities=[(user_deck.user_id, user_deck.deck_id)],
            )

            await self.cache_service.invalidate_library_deck_page(
                user_uuid=user_uuid,
            )

            return InternalUserDeck.model_validate(user_deck)

    async def save_deck(
            self,
            user_id: int,
            user_uuid: UUID,
            deck_uuid: UUID,
    ) -> InternalUserDeck:
        async with self.uow_factory() as uow:
            deck = await uow.deck_repo.get_by_uuid(deck_uuid=deck_uuid)
            if deck is None or not deck.is_public:
                raise DeckNotFoundError()
            if deck.user_id == user_id:
                raise CannotSaveOwnDeckError()
            
            user_deck = await uow.user_deck_repo.get_by_user_id_and_deck_id(
                user_id=user_id,
                deck_id=deck.id,
            )
            if user_deck is None:
                user_deck = UserDeck(
                    user_id=user_id,
                    deck_id=deck.id,
                    last_seen_version=deck.version,
                    is_saved=False,
                )
                uow.user_deck_repo.add(user_deck)
            if user_deck.is_saved is False:
                user_deck.is_saved = True
                deck.saves_count += 1

            await uow.commit()

            await self.cache_service.invalidate_user_decks(
                identities=[(user_deck.user_id, user_deck.deck_id)],
            )

            await self.cache_service.invalidate_library_deck_page(
                user_uuid=user_uuid,
            )

            return InternalUserDeck.model_validate(user_deck)

    async def get_page_of_saved_decks_by_user_id(
            self,
            user_id: int,
            page: int,
            page_size: int,
    ) -> list[DeckListItemResponse]:
        async with self.uow_factory() as uow:
            offset = (page - 1) * page_size
            rows = (
                await uow.user_deck_repo.
                get_saved_decks_by_user_id(
                    user_id=user_id,
                    offset=offset,
                    limit=page_size,
                )
            )
            result: list[DeckListItemResponse] = []
            for (owner_uuid, deck, user_deck) in rows:
                result.append(
                    DeckListItemResponse(
                        deck=DeckResponse(
                            uuid=deck.uuid,
                            owner_uuid=owner_uuid,
                            title=deck.title,
                            description=deck.description,
                            words_count=deck.words_count,
                            saves_count=deck.saves_count,
                            is_public=deck.is_public,
                        ),
                        viewer_state=DeckViewerStateResponse.validate(user_deck=user_deck)
                    )
                )
            return result

    async def set_favourite_deck(
            self,
            user_id: int,
            user_uuid: UUID,
            deck_uuid: UUID,
            value: bool,
    ) -> InternalUserDeck:
        async with self.uow_factory() as uow:
            deck = await uow.deck_repo.get_by_uuid(deck_uuid=deck_uuid)

            if deck is None or (deck.user_id != user_id and not deck.is_public):
                raise DeckNotFoundError()
            
            user_deck = await uow.user_deck_repo.get_by_user_id_and_deck_id(
                user_id=user_id,
                deck_id=deck.id,
            )
            if user_deck is None:
                if value is True:
                    user_deck = UserDeck(
                        user_id=user_id,
                        deck_id=deck.id,
                        last_seen_version=deck.version,
                        is_favourite=True,
                        is_saved=True,
                    )
                    uow.user_deck_repo.add(user_deck=user_deck)
                else:
                    raise DeckIsNotFavouriteError()

            user_deck.is_favourite = value
            
            await uow.commit()

            await self.cache_service.invalidate_user_decks(
                identities=[(user_deck.user_id, user_deck.deck_id)],
            )

            await self.cache_service.invalidate_library_deck_page(
                user_uuid=user_uuid,
            )

            return InternalUserDeck.model_validate(user_deck)

    # todo: отдавать (fetched, missing)
    async def get_user_decks_by_deck_ids(
        self,
        deck_ids: list[int],
        user_id: int,
    ) -> list[InternalUserDeck]:
        async with self.uow_factory() as uow:
            user_decks = await uow.user_deck_repo.get_user_decks_by_deck_ids(
                deck_ids=deck_ids,
                user_id=user_id,
            )
            return [
                InternalUserDeck.model_validate(user_deck)
                for user_deck in user_decks
            ]

    async def get_my_favourite_decks(
        self,
        user_id: int,
        search_query: SearchQuery = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[InternalDeck], str | None, bool]:
        async with self.uow_factory() as uow:
            cursor_updated_at, cursor_id = (
                decode_cursor(cursor) if cursor is not None
                else (None, None)
            )
            favourite_decks, has_more = (
                await uow.user_deck_repo.get_favourite_decks_by_user_id(
                    user_id=user_id,
                    search_query=search_query,
                    cursor_updated_at=cursor_updated_at,
                    cursor_id=cursor_id,
                    limit=limit,
                )
            )
            next_cursor = None
            if favourite_decks and has_more:
                next_cursor = encode_cursor(
                    time_condition=favourite_decks[-1].updated_at,
                    entity_id=favourite_decks[-1].id,
                )

            return (
                [InternalDeck.model_validate(deck) for deck in favourite_decks],
                next_cursor, 
                has_more
            )
