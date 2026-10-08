from collections.abc import Callable
from app.tracing import traced
from uuid import UUID

from app.cards.errors import (
    CardAlreadyExistsError,
    CardNotFoundError,
    PermissionDeniedError,
)
from app.cards.models import Card
from app.cards.schemas import CreateCardRequest, InternalCard, UpdateCardRequest
from app.common.types import SearchQuery
from app.common.utils import decode_cursor, encode_cursor
from app.redis.service import RedisCacheService
from app.redis.invalidation import CacheInvalidator, scopes
from app.service import UnitOfWork
from sqlalchemy.exc import IntegrityError


class CardService:
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
    async def _get_by_uuid(
        self,
        uow: UnitOfWork,
        card_uuid: UUID,
        for_update: bool = False,
    ) -> Card:
        card = await uow.card_repo.get_by_uuid(
            card_uuid=card_uuid,
            for_update=for_update,
        )

        if card is None:
            raise CardNotFoundError(f"Card with uuid={card_uuid} not found")

        return card

    async def _lock_card_for_deletion(
        self,
        uow: UnitOfWork,
        card_uuid: UUID,
        user_id: int,
    ) -> tuple[Card, list[int]]:
        while True:
            card = await self._get_by_uuid(uow, card_uuid)
            if card.user_id != user_id:
                raise CardNotFoundError(f"Card with uuid={card_uuid} not found")

            # Lock all related decks by id before locking the shared card.
            deck_ids = await uow.deck_card_repo.get_all_deck_ids_by_card_ids(
                card_ids=[card.id],
                for_update=True,
            )
            card = await self._get_by_uuid(uow, card_uuid, for_update=True)
            if card.user_id != user_id:
                raise CardNotFoundError(f"Card with uuid={card_uuid} not found")

            current_deck_ids = await uow.deck_card_repo.get_all_deck_ids_by_card_ids(
                card_ids=[card.id],
            )
            if set(current_deck_ids).issubset(deck_ids):
                return card, deck_ids

            # A link committed before the card lock was acquired. Release all
            # locks and retry rather than acquiring another deck after the card.
            await uow.rollback()

    # read
    async def get_by_uuid(
            self,
            card_uuid: UUID,
        ) -> InternalCard:
        async with self.uow_factory() as uow:
            card = await self._get_by_uuid(uow, card_uuid)
            return InternalCard.model_validate(card)

    async def get_by_ids(
        self,
        card_ids: list[int],
    ) -> list[InternalCard]:
        async with self.uow_factory() as uow:
            cards = await uow.card_repo.get_by_ids(
                card_ids=card_ids,
            )
            return [
                InternalCard.model_validate(card)
                for card in cards
            ]

    @traced("cards.service.get_cards_by_user_id")
    async def get_cards_by_user_id(
        self,
        user_id: int,
        search_query: SearchQuery = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[InternalCard], str | None, bool]:
        async with self.uow_factory() as uow:
            cursor_updated_at, cursor_id = (
                decode_cursor(cursor) if cursor is not None else (None, None)
            )
            cards, has_more = await uow.card_repo.get_all_by_user_id(
                user_id=user_id,
                search_query=search_query,
                cursor_updated_at=cursor_updated_at,
                cursor_id=cursor_id,
                limit=limit,
            )

            next_cursor = None
            if cards and has_more:
                next_cursor = encode_cursor(
                    time_condition=cards[-1].updated_at,
                    entity_id=cards[-1].id,
                )

            return (
                [InternalCard.model_validate(card) for card in cards],
                next_cursor, 
                has_more
            )

    # write
    async def create_card(
        self,
        payload: CreateCardRequest,
        user_id: int,
    ) -> InternalCard:
        try:
            async with self.uow_factory() as uow:
                card = Card(
                    **payload.model_dump(),
                    user_id=user_id,
                )

                uow.card_repo.add(card)

                await uow.commit()

                await self.cache_invalidator.invalidate(
                    scopes.library_card_pages(user_id),
                )

                return InternalCard.model_validate(card)

        except IntegrityError as e:
            raise CardAlreadyExistsError() from e

    async def update_card(
        self,
        card_uuid: UUID,
        user_id: int,
        payload: UpdateCardRequest,
    ) -> InternalCard:
        try:
            async with self.uow_factory() as uow:
                card = await self._get_by_uuid(
                    uow=uow,
                    card_uuid=card_uuid,
                    for_update=True,
                )
                if card.user_id != user_id:
                    raise PermissionDeniedError()

                update_data = payload.model_dump(
                    exclude_unset=True,
                )
                update_data = {
                    field: value for field, value in update_data.items()
                    if getattr(card, field) != value
                }
                if not update_data:
                    return InternalCard.model_validate(card)

                for field, value in update_data.items():
                    setattr(card, field, value)

                card_id = card.id
                await uow.commit()

                await self.cache_invalidator.invalidate(
                    scopes.cards(card_id),
                    scopes.library_card_pages(user_id),
                )
                await uow.card_repo.refresh(card)

                return InternalCard.model_validate(card)

        except IntegrityError as e:
            raise CardAlreadyExistsError() from e

    async def delete_card(
            self, 
            user_id: int,
            card_uuid: UUID,
        ) -> None:
        async with self.uow_factory() as uow:
            card, deck_ids = await self._lock_card_for_deletion(
                uow=uow,
                card_uuid=card_uuid,
                user_id=user_id,
            )

            card_id, removed_uuid = card.id, card.uuid
            affected_user_ids = await uow.user_deck_repo.get_library_user_ids_by_deck_ids(
                deck_ids=deck_ids,
            )
            await uow.card_repo.delete(card)
            await uow.flush()
            await uow.deck_card_repo.normalize_positions(
                deck_ids=deck_ids,
            )
            await uow.deck_card_repo.update_cards_count(
                deck_ids=deck_ids
            )
            await uow.commit()

            await self.cache_invalidator.invalidate(
                scopes.cards(card_id),
                scopes.card_ids_by_uuids(removed_uuid),
                scopes.library_card_pages(user_id),
                scopes.deck_with_cards(*deck_ids),
                scopes.library_deck_pages(*affected_user_ids),
            )

            return None
