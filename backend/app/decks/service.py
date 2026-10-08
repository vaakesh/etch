from collections.abc import Callable
from uuid import UUID
from app.tracing import traced

from sqlalchemy import update

from app.cards.errors import CardNotFoundError
from app.cards.models import Card
from app.cards.schemas import (
    CardResponse,
    CreateCardRequest,
    InternalCard,
    LoadCardsResponse,
    LoadedCardResponse,
)
from app.common.limits import MAX_DECK_SIZE
from app.common.types import SearchQuery, Username
from app.common.utils import decode_cursor, encode_cursor, utcnow
from app.redis.service import RedisCacheService
from app.redis.invalidation import CacheInvalidator, scopes
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
    DeckNotArchivedError,
    DeckSizeLimitExceededError,
    InvalidDeckCardPositionError,
    PermissionDeniedError,
)
from app.decks.cursor import library_cursor_codec
from app.decks.archiver import (
    ArchiveChanges,
    ArchiveExpiredError,
    DeckArchiveResult,
    DeckArchiveWorkflow,
)
from .models import Deck, DeckArchiveRecipient, DeckCard, UserDeck
from .schemas import (
    ArchivedDeckResponse,
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


class DeckService:
    def __init__(
        self, 
        uow_factory: Callable[[], UnitOfWork],
        cache_service: RedisCacheService,
        cache_invalidator: CacheInvalidator,
    ) -> None:
        self.uow_factory = uow_factory
        self.cache_service = cache_service
        self.cache_invalidator = cache_invalidator

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

    async def _require_archive_for_user(
        self,
        uow: UnitOfWork,
        deck_uuid: UUID,
        user_id: int,
    ) -> tuple[Deck, DeckArchiveRecipient]:
        row = await uow.deck_repo.get_with_archive_recipient(
            deck_uuid=deck_uuid, user_id=user_id,
        )
        if row is None:
            raise DeckNotFoundError()
        deck, recipient = row
        if deck.state != "archived":
            raise DeckNotArchivedError()
        if recipient is None:
            raise PermissionDeniedError()
        if deck.expires_at is None or utcnow() >= deck.expires_at:
            raise ArchiveExpiredError("Archive preservation period has expired")
        return deck, recipient

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
    @traced("decks.service.get_visible_by_uuid")
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

    @traced("decks.service.get_archive_deck")
    async def get_archive_deck(
        self, deck_uuid: UUID, user_id: int,
    ) -> ArchivedDeckResponse:
        async with self.uow_factory() as uow:
            deck, recipient = await self._require_archive_for_user(
                uow=uow, deck_uuid=deck_uuid, user_id=user_id,
            )
            return ArchivedDeckResponse(
                uuid=deck.uuid,
                title=deck.title,
                description=deck.description,
                words_count=deck.words_count,
                archived_at=deck.archived_at,
                expires_at=deck.expires_at,
                archive_reason=deck.archive_reason,
                source_deck_uuid_snapshot=deck.source_deck_uuid_snapshot,
                preserved_deck_uuid=recipient.preserved_deck_uuid_snapshot,
            )

    @traced("decks.service.get_archive_cards")
    async def get_archive_cards(
        self,
        deck_uuid: UUID,
        user_id: int,
        offset: int = 0,
        limit: int = 50,
    ) -> list[CardResponse]:
        async with self.uow_factory() as uow:
            deck, _ = await self._require_archive_for_user(
                uow=uow, deck_uuid=deck_uuid, user_id=user_id,
            )
            cards = await uow.deck_card_repo.get_cards_by_deck_id(
                deck_id=deck.id, offset=offset, limit=limit,
            )
            return [CardResponse.model_validate(card) for card in cards]

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

    @traced("decks.service.get_public_decks")
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

    @traced("decks.service.get_public_by_owner_uuid")
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

    @traced("decks.service.get_owned_decks")
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

    @traced("decks.service.get_library_decks")
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

    @traced("decks.service.get_deck_cards")
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

    @traced("decks.service.get_all_cards_by_deck_ids")
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
    @traced("decks.service.create_deck")
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

                await self.cache_invalidator.invalidate(
                    scopes.library_deck_pages(user_id),
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
    ) -> DeckArchiveResult | None:
        if deck.is_public is False:
            return None

        return await DeckArchiveWorkflow(uow).make_private(deck.uuid)
            
    @traced("decks.service.update_deck")
    async def update_deck(
        self,
        user_id: int,
        deck_uuid: UUID,
        payload: UpdateDeckRequest,
    ) -> InternalDeck:
        try:
            async with self.uow_factory() as uow:
                deck = await self._require_owned_deck(
                    uow=uow,
                    deck_uuid=deck_uuid,
                    owner_id=user_id,
                    for_update=True,
                )

                update_data = payload.model_dump(exclude_unset=True)
                is_public = update_data.pop("is_public", None)
                update_data = {
                    field: value
                    for field, value in update_data.items()
                    if getattr(deck, field) != value
                }

                visibility_changed = is_public is not None and is_public != deck.is_public
                changed = bool(update_data) or visibility_changed
                deck_id = deck.id
                affected_user_ids = (
                    set(await uow.user_deck_repo.get_library_user_ids_by_deck_ids([deck_id]))
                    if changed else set()
                )
                changes = ArchiveChanges()

                if update_data:
                    for field, value in update_data.items():
                        setattr(deck, field, value)
                    deck.mark_content_changed()

                if is_public is True:
                    await self._make_deck_public(
                        deck=deck,
                    )

                elif is_public is False:
                    archived = await self._make_deck_private(
                        uow=uow,
                        deck=deck,
                    )
                    if archived is not None:
                        changes = archived.changes
                affected_user_ids.add(user_id)

                await uow.commit()

                if changed:
                    await self.cache_invalidator.invalidate(
                        scopes.decks(*sorted({deck_id} | changes.deck_ids)),
                        scopes.user_decks(*sorted(changes.user_deck_keys)),
                        scopes.library_deck_pages(*sorted(affected_user_ids)),
                    )

                return InternalDeck.from_entity(
                    deck=deck,
                )

        except IntegrityError as e:
            raise DeckAlreadyExistsError() from e

    @traced("decks.service.delete_deck")
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

            deck_id, removed_uuid = deck.id, deck.uuid
            existing_keys = set(
                await uow.user_deck_repo.get_user_deck_keys_by_deck_ids([deck_id])
            )
            affected_user_ids = {user_id} | set(
                await uow.user_deck_repo.get_library_user_ids_by_deck_ids([deck_id])
            )
            result = await DeckArchiveWorkflow(uow).delete_deck(removed_uuid)
            changes = result.changes
            await uow.commit()

            await self.cache_invalidator.invalidate(
                scopes.deck_with_cards(deck_id),
                scopes.decks(*sorted(changes.deck_ids - {deck_id})),
                scopes.deck_ids_by_uuids(removed_uuid),
                scopes.user_decks(*sorted(existing_keys | changes.user_deck_keys)),
                scopes.library_deck_pages(*sorted(affected_user_ids)),
            )
            return None

    @traced("decks.service.preserve_archived_deck")
    async def preserve_archived_deck(
        self, archive_deck_uuid: UUID, user_id: int,
    ):
        async with self.uow_factory() as uow:
            result = await DeckArchiveWorkflow(uow).preserve(
                archive_deck_uuid, user_id=user_id,
            )
            await uow.commit()

        if not result.already_preserved:
            changes = result.changes
            await self.cache_invalidator.invalidate(
                scopes.decks(*sorted(changes.deck_ids)),
                scopes.user_decks(*sorted(changes.user_deck_keys)),
                scopes.library_deck_pages(user_id),
                scopes.library_card_pages(user_id),
            )
        return result

    @traced("decks.service.get_archives_for_user")
    async def get_archives_for_user(self, user_id: int):
        async with self.uow_factory() as uow:
            rows = await uow.deck_repo.get_archives_for_recipient(
                user_id=user_id, now=utcnow(),
            )
            return [
                {
                    "uuid": deck.uuid,
                    "title": deck.title,
                    "expires_at": deck.expires_at,
                    "preserved_deck_uuid": recipient.preserved_deck_uuid_snapshot,
                }
                for deck, recipient in rows
            ]

    @traced("decks.service.add_card_to_deck")
    async def add_card_to_deck(
        self,
        user_id: int,
        deck_uuid: UUID,
        card_uuid: UUID,
    ) -> InternalDeckCard:
        try:
            async with self.uow_factory() as uow:
                deck = await self._require_owned_deck(
                    uow=uow,
                    deck_uuid=deck_uuid,
                    owner_id=user_id,
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

                deck_id = deck.id
                affected_user_ids = {user_id} | set(
                    await uow.user_deck_repo.get_library_user_ids_by_deck_ids([deck_id])
                )
                await uow.commit()

                await self.cache_invalidator.invalidate(
                    scopes.deck_with_cards(deck_id),
                    scopes.library_deck_pages(*sorted(affected_user_ids)),
                )

                return InternalDeckCard.model_validate(obj=deck_card)
        except IntegrityError as e:
            raise DeckCardAlreadyExistsError() from e

    @traced("decks.service.load_cards_to_deck")
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

            deck_id = deck.id
            affected_user_ids = {user_id} | set(
                await uow.user_deck_repo.get_library_user_ids_by_deck_ids([deck_id])
            )
            await uow.commit()

            await self.cache_invalidator.invalidate(
                scopes.deck_with_cards(deck_id),
                scopes.library_deck_pages(*sorted(affected_user_ids)),
                scopes.library_card_pages(user_id) if card_entities else (),
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

    @traced("decks.service.reorder_cards")
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
            deck_id = deck.id
            await uow.commit()

            if from_position != to_position:
                await self.cache_invalidator.invalidate(
                    scopes.deck_cards(deck_id),
                )

    @traced("decks.service.remove_card_from_deck")
    async def remove_card_from_deck(
        self,
        user_id: int,
        deck_uuid: UUID,
        card_uuid: UUID,
    ) -> None:
        async with self.uow_factory() as uow:
            deck = await self._require_owned_deck(
                uow=uow,
                deck_uuid=deck_uuid,
                owner_id=user_id,
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
            deck.mark_content_changed()

            await uow.deck_card_repo.delete(deck_card)
            await uow.flush()
            await uow.deck_card_repo.update_deck_cards_positions_after_deleting(
                deck_id=deck.id,
                deleted_position=deck_card.position,
            )
            deck_id = deck.id
            affected_user_ids = {user_id} | set(
                await uow.user_deck_repo.get_library_user_ids_by_deck_ids([deck_id])
            )
            await uow.commit()

            await self.cache_invalidator.invalidate(
                scopes.deck_with_cards(deck_id),
                scopes.library_deck_pages(*sorted(affected_user_ids)),
            )

            return None


class UserDeckService:
    def __init__(
        self, 
        uow_factory: Callable[[], UnitOfWork],
        cache_service: RedisCacheService,
        cache_invalidator: CacheInvalidator,
    ) -> None:
        self.uow_factory = uow_factory
        self.cache_service = cache_service
        self.cache_invalidator = cache_invalidator

    # read
    # todo: отдавать (fetched, missing)
    @traced("decks.service.get_user_decks_by_deck_ids")
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

    @traced("decks.user_deck_service.get_page_of_saved_decks_by_user_id")
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

    @traced("decks.service.get_my_favourite_decks")
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
    @traced("decks.user_deck_service.save_deck")
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
            changed = user_deck.is_saved is False
            if changed:
                user_deck.is_saved = True
                deck.saves_count += 1

            identity = make_user_deck_identity(
                user_id=user_deck.user_id, deck_id=user_deck.deck_id,
            )
            await uow.commit()

            if changed:
                await self.cache_invalidator.invalidate(
                    scopes.user_decks(identity),
                    scopes.library_deck_pages(user_id),
                )

            return InternalUserDeck.model_validate(user_deck)

    @traced("decks.user_deck_service.set_favourite_deck")
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

            identity = make_user_deck_identity(
                user_id=user_deck.user_id, deck_id=user_deck.deck_id,
            )
            await uow.commit()

            await self.cache_invalidator.invalidate(
                scopes.user_decks(identity),
                scopes.library_deck_pages(user_id),
            )

            return InternalUserDeck.model_validate(user_deck)

    @traced("decks.user_deck_service.unsave_deck")
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
            changed = user_deck.is_saved is True
            if changed:
                user_deck.is_saved = False
                user_deck.is_favourite = False
                deck.saves_count -= 1

            identity = make_user_deck_identity(
                user_id=user_deck.user_id, deck_id=user_deck.deck_id,
            )
            await uow.commit()

            if changed:
                await self.cache_invalidator.invalidate(
                    scopes.user_decks(identity),
                    scopes.library_deck_pages(user_id),
                )

            return InternalUserDeck.model_validate(user_deck)
