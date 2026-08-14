from collections.abc import Callable
from uuid import UUID

from app.cards.errors import (
    CardAlreadyExistsError,
    CardNotFoundError,
    PermissionDeniedError,
)
from app.redis.service import RedisCacheService
from app.service import UnitOfWork
from app.utils import decode_cursor, encode_cursor
from sqlalchemy.exc import IntegrityError

from .models import Card
from .schemas import CreateCardRequest, UpdateCardRequest


class CardService:
    def __init__(
        self, 
        uow_factory: Callable[[], UnitOfWork],
        cache_service: RedisCacheService,
    ) -> None:
        self.uow_factory = uow_factory
        self.cache_service = cache_service

    async def get_card_in_deck(
        self,
        card_uuid: UUID,
        deck_uuid: UUID,
        viewer_id: int | None,
    ):
        async with self.uow_factory() as uow:
            card = await uow.card_repo.get_card_in_deck(
                deck_uuid=deck_uuid,
                card_uuid=card_uuid,
                viewer_id=viewer_id,
                for_update=False,
            )

            if card is None:
                raise CardNotFoundError()

            return card

    async def get_by_uuids(
        self,
        card_uuids: list[UUID],
    ) -> list[Card]:
        async with self.uow_factory() as uow:
            cards = await uow.card_repo.get_by_uuids(
                card_uuids=card_uuids,
            )
            return cards

    async def get_by_uuid(
            self, 
            card_uuid: UUID,
        ) -> Card:
        async with self.uow_factory() as uow:
            card = await self._get_by_uuid(uow, card_uuid)
            return card

    async def _get_by_uuid(
        self,
        uow: UnitOfWork,
        card_uuid: UUID,
    ) -> Card:
        card = await uow.card_repo.get_by_uuid(card_uuid)

        if card is None:
            raise CardNotFoundError(f"Card with uuid={card_uuid} not found")

        return card

    async def get_all_by_user_id(
        self,
        user_id: int,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Card], str | None, bool]:
        async with self.uow_factory() as uow:
            cursor_updated_at, cursor_id = (
                decode_cursor(cursor) if cursor is not None else (None, None)
            )
            cards, has_more = await uow.card_repo.get_all_by_user_id(
                user_id=user_id,
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

            return cards, next_cursor, has_more

    async def create_card(
        self,
        payload: CreateCardRequest,
        user_id: int,
    ) -> Card:
        try:
            async with self.uow_factory() as uow:
                card = Card(
                    **payload.model_dump(),
                    user_id=user_id,
                )

                uow.card_repo.add(card)

                await uow.commit()
                await uow.card_repo.refresh(card)

                return card

        except IntegrityError as e:
            raise CardAlreadyExistsError() from e

    async def update_card(
        self,
        card_uuid: UUID,
        user_id: int,
        payload: UpdateCardRequest,
    ) -> Card:
        try:
            async with self.uow_factory() as uow:
                card = await self._get_by_uuid(uow, card_uuid)
                if card.user_id != user_id:
                    raise PermissionDeniedError()

                update_data = payload.model_dump(
                    exclude_unset=True,
                    exclude_none=True,
                )

                for field, value in update_data.items():
                    setattr(card, field, value)

                await uow.commit()
                await uow.card_repo.refresh(card)

                await self.cache_service.invalidate_cards(
                    card_uuids=[card.uuid],
                )

                return card

        except IntegrityError as e:
            raise CardAlreadyExistsError() from e

    async def delete_card(
            self, 
            user_id: int,
            card_uuid: UUID,
        ) -> None:
        async with self.uow_factory() as uow:
            card = await self._get_by_uuid(uow, card_uuid)
            if card.user_id != user_id:
                raise CardNotFoundError(f"Card with uuid={card_uuid} not found")

            deck_ids_and_uuids = await uow.deck_card_repo.get_all_decks_by_card_id(card.id)
            deck_ids=[deck_id for deck_id, deck_uuid in deck_ids_and_uuids]
            deck_uuids=[deck_uuid for deck_id, deck_uuid in deck_ids_and_uuids]

            await uow.card_repo.delete(card)
            await uow.flush()
            await uow.deck_card_repo.update_cards_count(
                deck_ids=deck_ids
            )
            await uow.commit()

            await self.cache_service.invalidate_cards(
                card_uuids=[card.uuid],
            )

            await self.cache_service.invalidate_deck_cards(
                deck_uuids=deck_uuids,
            )

            await self.cache_service.invalidate_decks(
                deck_uuids=deck_uuids,
            )

            return None