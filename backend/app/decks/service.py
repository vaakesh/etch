import asyncio
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import update

from app.cards.errors import CardNotFoundError
from app.cards.models import Card
from app.cards.schemas import (
    CreateCardRequest,
    InternalCard,
    LoadCardsResponse,
    LoadedCardResponse,
)
from app.common.limits import MAX_DECK_SIZE
from app.common.types import SearchQuery, Username
from app.common.utils import decode_cursor, encode_cursor, utcnow
from app.redis.service import RedisCacheService
from app.service import UnitOfWork
from app.users.errors import UserNotFoundError
from sqlalchemy.exc import IntegrityError

from app.common.schemas import CursorPage
from app.decks.utils import make_user_deck_identity

from .errors import (
    CannotFavouriteUnsavedDeckError,
    CannotSaveOwnDeckError,
    DeckAlreadyExistsError,
    DeckCardAlreadyExistsError,
    DeckCardNotFoundError,
    DeckIsNotSavedError,
    DeckNotFoundError,
    DeckSizeLimitExceededError,
    InvalidDeckCardPositionError,
    PermissionDeniedError,
)
from app.decks.cursor import library_cursor_codec
from .models import Deck, DeckCard, UserDeck
from .schemas import (
    CreateDeckRequest,
    DeckListItemResponse,
    DeckLoad,
    DeckResponse,
    DeckViewerStateResponse,
    InternalDeck,
    InternalDeckCard,
    InternalUserDeck,
    LibraryCursor,
    UpdateDeckRequest,
)


class DeckArchiver:
    def __init__(self, archive_user_id: int = 1) -> None:
        self.archive_user_id = archive_user_id

    async def archive(
        self,
        uow: UnitOfWork,
        deck: Deck,
        *,
        include_owner: bool = False,
    ) -> list[int]:
        """Move user state and history; the caller commits the whole operation.

        Hiding a deck keeps the owner's history on the original. Deleting a deck
        passes include_owner=True. Deleting its owner leaves this False because
        that user's own sessions will be deleted along with their account.
        """
        decks = await uow.deck_repo.get_decks_with_all_cards(
            deck_ids=[deck.id],
            for_update=True,
        )
        if not decks:
            raise DeckNotFoundError()
        source = decks[0]
        if source.user_id == self.archive_user_id:
            return []
        exclude_user_id = None if include_owner else source.user_id
        has_user_state = await uow.deck_repo.has_archivable_user_decks(
            deck_id=source.id,
            exclude_user_id=exclude_user_id,
        )
        has_history = await uow.training_session_repo.has_by_deck_id(
            deck_id=source.id,
            exclude_user_id=exclude_user_id,
        )
        if not has_user_state and not has_history:
            return []

        archived_deck = await self._copy_deck(uow=uow, deck=source)
        # Lock/move sessions before UserDeck, matching submit_answer's lock order.
        session_user_ids = await uow.training_session_repo.reassign_deck(
            from_deck_id=source.id,
            to_deck_id=archived_deck.id,
            exclude_user_id=exclude_user_id,
        )
        user_states = await uow.deck_repo.reassign_user_decks(
            from_deck_id=source.id,
            to_deck_id=archived_deck.id,
            exclude_user_id=exclude_user_id,
        )
        archived_deck.saves_count = sum(is_saved for _, is_saved in user_states)
        source.saves_count = 0
        return sorted(set(session_user_ids) | {user_id for user_id, _ in user_states})

    async def archive_many(
        self,
        uow: UnitOfWork,
        decks: list[Deck],
    ) -> list[int]:
        affected_user_ids: set[int] = set()
        for deck in sorted(decks, key=lambda item: item.id):
            affected_user_ids.update(await self.archive(uow=uow, deck=deck))
        return sorted(affected_user_ids)

    async def _copy_deck(
        self,
        uow: UnitOfWork,
        deck: Deck,
    ) -> Deck:
        copied_deck = Deck(
            user_id=self.archive_user_id,
            source_deck_id=deck.id,
            title=deck.title,
            description=deck.description,
            words_count=deck.words_count,
            is_public=deck.is_public,
            saves_count=0,
            version=deck.version,
            created_at=deck.created_at,
            updated_at=utcnow(),
        )
        uow.deck_repo.add(deck=copied_deck)
        await uow.flush()

        cards = [
            link.card for link in deck.card_links
        ]

        copied_cards = [
            Card(
                user_id=self.archive_user_id,
                front_text=card.front_text,
                back_text=card.back_text,
                front_lang=card.front_lang,
                back_lang=card.back_lang,
                created_at=card.created_at,
                updated_at=card.updated_at,
            ) for card in cards
        ]
        uow.card_repo.add_all(
            cards=copied_cards,
        )
        await uow.flush()
        copied_deck_cards = [
            DeckCard(
                deck_id=copied_deck.id,
                card_id=copied_card.id,
                position=link.position,
                created_at=link.created_at,
                updated_at=link.updated_at,
            ) for copied_card, link in zip(
                copied_cards, deck.card_links, strict=True
            )
        ]
        uow.deck_card_repo.add_all(
            deck_cards=copied_deck_cards,
        )

        return copied_deck


class DeckService:
    def __init__(
        self, 
        uow_factory: Callable[[], UnitOfWork],
        cache_service: RedisCacheService,
    ) -> None:
        self.uow_factory = uow_factory
        self.cache_service = cache_service
        self.deck_archiver = DeckArchiver()

    # helpers

    async def _require_visible_deck(
        self,
        uow: UnitOfWork,
        deck_uuid: UUID,
        viewer_id: int | None,
    ) -> Deck:
        deck = await uow.deck_repo.get_visible_by_uuid(
            deck_uuid=deck_uuid,
            viewer_id=viewer_id,
        )
        if deck is None:
            raise DeckNotFoundError()
        return deck

    async def _require_owned_deck(
        self,
        uow: UnitOfWork,
        deck_uuid: UUID,
        owner_id: int,
        for_update: bool = False,
    ) -> Deck:
        deck = await uow.deck_repo.get_owned_by_uuid(
            deck_uuid=deck_uuid,
            owner_id=owner_id,
            for_update=for_update,
        )
        if deck is None:
            raise DeckNotFoundError()
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

    # read
    async def get_visible_by_uuid(
            self, 
            deck_uuid: UUID,
            viewer_id: int | None = None,
        ) -> InternalDeck:
        async with self.uow_factory() as uow:
            deck = await self._require_visible_deck(
                uow=uow,
                deck_uuid=deck_uuid,
                viewer_id=viewer_id,
            )
            return InternalDeck.model_validate(deck)

    async def get_visible_by_ids(
        self,
        deck_ids: list[int],
        viewer_id: int,
    ) -> tuple[dict[int, InternalDeck], list[int]]:
        async with self.uow_factory() as uow:
            decks = await uow.deck_repo.get_visible_by_ids(
                deck_ids=deck_ids,
                viewer_id=viewer_id,
            )
            fetched_decks: dict[int, InternalDeck] = {
                deck.id: InternalDeck.model_validate(deck)
                for deck in decks
            }
            # если есть missing, значит для пользователя неактуальный deck_id
            # колода удалена или закрыта
            missing_decks: list[int] = [
                deck_id
                for deck_id in deck_ids
                if deck_id not in fetched_decks
            ]
            return (fetched_decks, missing_decks)

    async def get_public_decks(
        self,
        search_query: SearchQuery = None,
        page: int = 1,
        limit: int = 50,
    ) -> list[InternalDeck]:
        '''
        получение колод на странице каталога, подумать над логикой,
        добавить фильтры какие-то
        '''
        async with self.uow_factory() as uow:
            offset = (page - 1) * limit
            decks = await uow.deck_repo.get_public_decks(
                search_query=search_query,
                limit=limit,
                offset=offset,
            )
            return [InternalDeck.from_entity(deck) for deck in decks]

    async def get_public_by_owner_uuid(
        self,
        owner_uuid: UUID,
        viewer_id: int | None = None,
        search_query: str | None = None,
        cursor: str | None = None,
        limit: int = 10,
    ) -> CursorPage[InternalDeck]:
        async with self.uow_factory() as uow:
            user = await uow.user_repo.get_by_uuid(
                user_uuid=owner_uuid,
            )
            if user is None:
                raise UserNotFoundError()

            cursor_updated_at, cursor_id = (
                decode_cursor(cursor) if cursor is not None else (None, None)
            )

            decks, has_more = await uow.deck_repo.get_public_by_owner_id(
                owner_id=user.id,
                viewer_id=viewer_id,
                search_query=search_query,
                cursor_updated_at=cursor_updated_at,
                cursor_id=cursor_id,
                limit=limit,
            )

            next_cursor = None
            if decks and has_more:
                next_cursor = encode_cursor(
                    time_condition=decks[-1].updated_at,
                    entity_id=decks[-1].id,
                )

            return CursorPage(
                items=[InternalDeck.model_validate(deck) for deck in decks], 
                next_cursor=next_cursor, 
                has_more=has_more,
            )

    async def get_visible_to_user(
        self,
        viewer_id: int,
        search_query: str | None = None,
        cursor: str | None = None,
        limit: int = 10,
    ) -> CursorPage[InternalDeck]:
        async with self.uow_factory() as uow:
            cursor_updated_at, cursor_id = (
                decode_cursor(cursor) if cursor is not None else (None, None)
            )

            decks, has_more = await uow.deck_repo.get_visible_to_user_id(
                viewer_id=viewer_id,
                search_query=search_query,
                cursor_updated_at=cursor_updated_at,
                cursor_id=cursor_id,
                limit=limit,
            )

            next_cursor = None
            if decks and has_more:
                next_cursor = encode_cursor(
                    time_condition=decks[-1].updated_at,
                    entity_id=decks[-1].id,
                )

            return CursorPage(
                items=[InternalDeck.model_validate(deck) for deck in decks], 
                next_cursor=next_cursor, 
                has_more=has_more,
            )

    async def get_owned_decks(
        self,
        owner_id: int,
        search_query: str | None = None,
        cursor: str | None = None,
        limit: int = 10,
    ) -> CursorPage[InternalDeck]:
        async with self.uow_factory() as uow:
            cursor_updated_at, cursor_id = (
                decode_cursor(cursor) if cursor is not None else (None, None)
            )

            decks, has_more = await uow.deck_repo.get_owned_by_owner_id(
                owner_id=owner_id,
                search_query=search_query,
                cursor_updated_at=cursor_updated_at,
                cursor_id=cursor_id,
                limit=limit,
            )

            next_cursor = None
            if decks and has_more:
                next_cursor = encode_cursor(
                    time_condition=decks[-1].updated_at,
                    entity_id=decks[-1].id,
                )

            return CursorPage(
                items=[InternalDeck.model_validate(deck) for deck in decks], 
                next_cursor=next_cursor, 
                has_more=has_more,
            )

    async def get_saved_decks(
        self,
        user_id: int,
        search_query: str | None = None,
        cursor: str | None = None,
        limit: int = 10,
    ) -> CursorPage[InternalDeck]:
        async with self.uow_factory() as uow:
            cursor_updated_at, cursor_id = (
                decode_cursor(cursor) if cursor is not None else (None, None)
            )

            decks, has_more = await uow.deck_repo.get_saved_by_user_id(
                user_id=user_id,
                search_query=search_query,
                cursor_updated_at=cursor_updated_at,
                cursor_id=cursor_id,
                limit=limit,
            )

            next_cursor = None
            if decks and has_more:
                next_cursor = encode_cursor(
                    time_condition=decks[-1].updated_at,
                    entity_id=decks[-1].id,
                )

            return CursorPage(
                items=[InternalDeck.model_validate(deck) for deck in decks], 
                next_cursor=next_cursor, 
                has_more=has_more,
            )

    async def get_library_decks(
        self,
        user_id: int,
        search_query: str | None = None,
        cursor: str | None = None,
        limit: int = 10,
    ) -> CursorPage[InternalDeck]:
        async with self.uow_factory() as uow:
            decoded_cursor = library_cursor_codec.decode(
                cursor=cursor,
            ) if cursor else None

            decks, last_item = await uow.deck_repo.get_library_by_user_id(
                user_id=user_id,
                search_query=search_query,
                cursor=decoded_cursor,
                limit=limit,
            )

            next_cursor = None
            if last_item is not None:
                last_deck, last_user_deck = last_item
                next_cursor = library_cursor_codec.encode(
                    value=LibraryCursor(
                        last_studied_at=last_user_deck.last_studied_at,
                        added_at=last_user_deck.added_at,
                        id=last_deck.id,
                    )
                )

            return CursorPage(
                items=[InternalDeck.model_validate(deck) for deck in decks],
                next_cursor=next_cursor,
                has_more=True if last_item is not None else False,
            )

    async def get_deck_cards(
        self,
        user_id: int | None,
        deck_uuid: UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> list[InternalCard]:
        async with self.uow_factory() as uow:
            deck = await self._require_visible_deck(
                uow=uow,
                deck_uuid=deck_uuid,
                viewer_id=user_id,
            )

            cards = await uow.deck_card_repo.get_cards_by_deck_id(
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
    ) -> dict[int, list[InternalCard]]:
        async with self.uow_factory() as uow:
            rows = await uow.deck_card_repo.get_cards_by_deck_ids(
                deck_ids=deck_ids,
                limit=limit,
            )
            cards_by_deck = {
                deck_id: []
                for deck_id in deck_ids
            }
            for deck_id, card in rows:
                cards_by_deck[deck_id].append(
                    InternalCard.model_validate(card)
                )
            return cards_by_deck

    # write
    async def create_deck(
        self,
        payload: CreateDeckRequest,
        user_id: int,
        user_uuid: UUID,
        user_username: Username,
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

                await self.cache_service.invalidate_library_deck_pages(
                    user_ids=[user_id],
                )

                return InternalDeck(
                    id=deck.id,
                    uuid=deck.uuid,
                    user_id=user_id,
                    owner_uuid=user_uuid,
                    owner_username=user_username,
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

    async def _make_deck_public(
        self,
        deck: Deck,
    ) -> bool:
        if deck.is_public is True:
            return False
        deck.is_public = True
        return True

    async def _make_deck_private(
        self,
        uow: UnitOfWork,
        deck: Deck,
    ) -> list[int]:
        if deck.is_public is False:
            return []

        affected_user_ids = await self.deck_archiver.archive(
            uow=uow,
            deck=deck,
        )

        deck.saves_count = 0
        deck.is_public = False

        return affected_user_ids
            
    async def update_deck(
        self,
        user_id: int,
        deck_uuid: UUID,
        payload: UpdateDeckRequest,
    ) -> InternalDeck:
        try:
            affected_user_ids: list[int] = []
            invalidate_deck = False
            invalidate_affected_user_caches = False

            async with self.uow_factory() as uow:
                deck = await self._require_owned_deck(
                    uow=uow,
                    deck_uuid=deck_uuid,
                    owner_id=user_id,
                    for_update=True,
                )

                update_data = payload.model_dump(exclude_unset=True)
                is_public = update_data.pop("is_public", None)

                if update_data:
                    for field, value in update_data.items():
                        setattr(deck, field, value)
                    deck.mark_content_changed()
                    invalidate_deck = True

                if is_public is True:
                    changed = await self._make_deck_public(
                        deck=deck,
                    )
                    if changed:
                        invalidate_deck = True

                elif is_public is False:
                    invalidate_deck = invalidate_deck or deck.is_public
                    affected_user_ids = await self._make_deck_private(
                        uow=uow,
                        deck=deck,
                    )
                    if affected_user_ids:
                        invalidate_affected_user_caches = True

                await uow.commit()

                tasks = []
                if invalidate_deck:
                    tasks.append(
                        self.cache_service.invalidate_decks(
                            deck_ids=[deck.id],
                        )
                    )

                if invalidate_affected_user_caches:
                    tasks.extend(
                        [
                            self.cache_service.invalidate_user_decks(
                                identities=[
                                    make_user_deck_identity(
                                        user_id=affected_user_id,
                                        deck_id=deck.id,
                                    ) for affected_user_id in affected_user_ids
                                ]
                            ),
                            self.cache_service.invalidate_library_deck_pages(
                                user_ids=affected_user_ids,
                            ),
                            self.cache_service.invalidate_library_card_pages(
                                user_ids=affected_user_ids,
                            )
                        ]
                    )

                if tasks:
                    await asyncio.gather(*tasks)

                return InternalDeck.from_entity(
                    deck=deck,
                )

        except IntegrityError as e:
            raise DeckAlreadyExistsError() from e

    async def delete_deck(
        self, 
        deck_uuid: UUID,
        user_id: int,
    ) -> None:
        async with self.uow_factory() as uow:
            deck = await self._require_owned_deck(
                uow=uow,
                deck_uuid=deck_uuid,
                owner_id=user_id,
                for_update=True,
            )

            affected_user_ids = set(await self.deck_archiver.archive(
                uow=uow,
                deck=deck,
                include_owner=True,
            ))

            await uow.deck_repo.delete(deck)
            await uow.commit()

            affected_user_ids.add(user_id)
            tasks = []

            tasks.extend([
                self.cache_service.invalidate_decks(
                    deck_ids=[deck.id],
                ),
                self.cache_service.invalidate_library_deck_pages(
                    user_ids=affected_user_ids,
                ),
                self.cache_service.invalidate_library_card_pages(
                    user_ids=affected_user_ids,
                ),
                self.cache_service.invalidate_deck_cards(
                    deck_ids=[deck.id],
                ),
                self.cache_service.invalidate_deck_ids_by_uuids(
                    deck_uuids=[deck.uuid],
                ),
                self.cache_service.invalidate_user_decks(
                    identities=[
                        make_user_deck_identity(
                            user_id=user_id,
                            deck_id=deck.id,
                        ) for user_id in affected_user_ids
                    ]
                ),
            ])
            await asyncio.gather(*tasks)
            return None

    async def add_card_to_deck(
        self,
        user_id: int,
        deck_uuid: UUID,
        card_uuid: UUID,
    ) -> InternalDeckCard:
        try:
            async with self.uow_factory() as uow:
                card = await self._get_card_by_uuid(
                    uow,
                    card_uuid,
                    for_update=True,
                )

                deck = await self._require_owned_deck(
                    uow=uow,
                    deck_uuid=deck_uuid,
                    owner_id=user_id,
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

                if deck.words_count + 1 > MAX_DECK_SIZE:
                    raise DeckSizeLimitExceededError(
                        limit=MAX_DECK_SIZE,
                        current=deck.words_count,
                        requested=1,
                    )

                deck.words_count += 1
                deck.mark_content_changed()

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

                await self.cache_service.invalidate_decks(
                    deck_ids=[deck.id],
                )

                await self.cache_service.invalidate_deck_cards(
                    deck_ids=[deck.id],
                )

                return InternalDeckCard.model_validate(obj=deck_card)
        except IntegrityError as e:
            raise DeckCardAlreadyExistsError() from e

    async def load_cards_to_deck(
        self,
        deck_uuid: UUID,
        cards: list[CreateCardRequest],
        user_id: int,
    ) -> LoadCardsResponse:
        '''
        импорт карточек батчем
        '''
        async with self.uow_factory() as uow:
            deck = await self._require_owned_deck(
                uow=uow,
                deck_uuid=deck_uuid,
                owner_id=user_id,
                for_update=True,
            )

            if deck.words_count + len(cards) > MAX_DECK_SIZE:
                raise DeckSizeLimitExceededError(
                    limit=MAX_DECK_SIZE,
                    current=deck.words_count,
                    requested=len(cards),
                )

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
            deck.mark_content_changed()

            await uow.commit()

            await self.cache_service.invalidate_decks(
                deck_ids=[deck.id],
            )

            await self.cache_service.invalidate_deck_cards(
                deck_ids=[deck.id],
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
            deck = await self._require_owned_deck(
                uow=uow,
                deck_uuid=deck_uuid,
                owner_id=user_id,
                for_update=True,
            )
            if card.user_id != user_id:
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
            deck.mark_content_changed()
            await uow.commit()

            await self.cache_service.invalidate_decks(
                deck_ids=[deck.id],
            )

            await self.cache_service.invalidate_deck_cards(
                deck_ids=[deck.id],
            )

    async def remove_card_from_deck(
        self,
        user_id: int,
        deck_uuid: UUID,
        card_uuid: UUID,
    ) -> None:
        async with self.uow_factory() as uow:
            card = await self._get_card_by_uuid(
                uow=uow,
                card_uuid=card_uuid,
                for_update=True,
            )

            deck = await self._require_owned_deck(
                uow=uow,
                deck_uuid=deck_uuid,
                owner_id=user_id,
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
            deck.mark_content_changed()

            await uow.deck_card_repo.delete(deck_card)
            await uow.flush()
            await uow.deck_card_repo.update_deck_cards_positions_after_deleting(
                deck_id=deck.id,
                deleted_position=deck_card.position,
            )
            await uow.commit()

            await self.cache_service.invalidate_decks(
                deck_ids=[deck.id],
            )

            await self.cache_service.invalidate_deck_cards(
                deck_ids=[deck.id],
            )

            return None


class UserDeckService:
    def __init__(
        self, 
        uow_factory: Callable[[], UnitOfWork],
        cache_service: RedisCacheService,
    ) -> None:
        self.uow_factory = uow_factory
        self.cache_service = cache_service

    # read
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
            for (deck, user_deck) in rows:
                result.append(
                    DeckListItemResponse(
                        deck=DeckResponse.model_validate(
                            obj=deck,
                        ),
                        viewer_state=DeckViewerStateResponse.validate(
                            user_deck=user_deck
                        )
                    )
                )
            return result

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

    # write
    async def save_deck(
            self,
            user_id: int,
            deck_uuid: UUID,
    ) -> InternalUserDeck:
        async with self.uow_factory() as uow:
            deck = await uow.deck_repo.get_by_uuid(
                deck_uuid=deck_uuid,
                load=DeckLoad(
                    user=True,
                ),
                for_update=True,
            )
            if deck is None or not deck.is_public:
                raise DeckNotFoundError()
            if deck.user_id == user_id:
                raise CannotSaveOwnDeckError()
            
            user_deck = await uow.user_deck_repo.get_by_user_id_and_deck_id(
                user_id=user_id,
                deck_id=deck.id,
                for_update=True,
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

            await self.cache_service.invalidate_library_deck_pages(
                user_ids=[user_id],
            )

            await self.cache_service.invalidate_library_card_pages(
                user_ids=[user_id],
            )

            return InternalUserDeck.model_validate(user_deck)

    async def set_favourite_deck(
            self,
            user_id: int,
            deck_uuid: UUID,
            value: bool,
    ) -> InternalUserDeck:
        async with self.uow_factory() as uow:
            deck = await uow.deck_repo.get_by_uuid(
                deck_uuid=deck_uuid,
                load=DeckLoad(
                    user=True,
                ),
                for_update=True,
            )

            if deck is None or (deck.user_id != user_id and not deck.is_public):
                raise DeckNotFoundError()
            
            user_deck = await uow.user_deck_repo.get_by_user_id_and_deck_id(
                user_id=user_id,
                deck_id=deck.id,
            )
            if user_deck is None or (
                deck.user_id != user_id and not user_deck.is_saved
            ):
                raise CannotFavouriteUnsavedDeckError()

            if user_deck.is_favourite == value:
                return InternalUserDeck.model_validate(user_deck)

            user_deck.is_favourite = value

            await uow.commit()

            await self.cache_service.invalidate_user_decks(
                identities=[(user_deck.user_id, user_deck.deck_id)],
            )

            await self.cache_service.invalidate_library_deck_pages(
                user_ids=[user_id],
            )

            return InternalUserDeck.model_validate(user_deck)

    async def unsave_deck(
        self,
        user_id: int,
        deck_uuid: UUID,
    ) -> InternalUserDeck:
        async with self.uow_factory() as uow:
            deck = await uow.deck_repo.get_by_uuid(
                deck_uuid=deck_uuid,
                load=DeckLoad(
                    user=True,
                ),
                for_update=True,
            )
            if deck is None or not deck.is_public:
                raise DeckNotFoundError()
            # todo: change error
            if deck.user_id == user_id:
                raise CannotSaveOwnDeckError()

            user_deck = await uow.user_deck_repo.get_by_user_id_and_deck_id(
                user_id=user_id,
                deck_id=deck.id,
                for_update=True,
            )
            if user_deck is None:
                raise DeckIsNotSavedError()
            if user_deck.is_saved is True:
                user_deck.is_saved = False
                user_deck.is_favourite = False
                deck.saves_count -= 1

            await uow.commit()

            await asyncio.gather(
                self.cache_service.invalidate_user_decks(
                    identities=[(user_deck.user_id, user_deck.deck_id)],
                ),
                self.cache_service.invalidate_library_deck_pages(
                    user_ids=[user_id],
                ),
                self.cache_service.invalidate_library_card_pages(
                    user_ids=[user_id],
                ),
            )

            return InternalUserDeck.model_validate(user_deck)
