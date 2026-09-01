import asyncio
from collections.abc import Callable
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
from app.service import UnitOfWork
from sqlalchemy.exc import IntegrityError


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
    ) -> InternalCard:
        async with self.uow_factory() as uow:
            card = await uow.card_repo.get_card_in_deck(
                deck_uuid=deck_uuid,
                card_uuid=card_uuid,
                viewer_id=viewer_id,
                for_update=False,
            )

            if card is None:
                raise CardNotFoundError()

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

    async def get_by_uuid(
            self, 
            card_uuid: UUID,
        ) -> InternalCard:
        async with self.uow_factory() as uow:
            card = await self._get_by_uuid(uow, card_uuid)
            return InternalCard.model_validate(card)

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
                await uow.card_repo.refresh(card)

                await self.cache_service.invalidate_library_card_page(
                    user_id=user_id,
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

                await asyncio.gather(
                    self.cache_service.invalidate_cards(
                        card_ids=[card.id],
                    ),
                    self.cache_service.invalidate_library_card_page(
                        user_id=user_id,
                    )
                )

                return InternalCard.model_validate(card)

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

            deck_ids = await uow.deck_card_repo.get_all_deck_ids_by_card_id(
                card_id=card.id,
            )

            await uow.card_repo.delete(card)
            await uow.flush()
            await uow.deck_card_repo.update_cards_count(
                deck_ids=deck_ids
            )
            await uow.commit()

            await self.cache_service.invalidate_cards(
                card_ids=[card.id],
            )

            await self.cache_service.invalidate_card_ids_by_uuids(
                card_uuids=[card.uuid],
            )

            await self.cache_service.invalidate_library_card_page(
                user_id=user_id,
            )

            await self.cache_service.invalidate_library_deck_page(
                user_id=user_id,
            )

            await self.cache_service.invalidate_deck_cards(
                deck_ids=deck_ids,
            )

            await self.cache_service.invalidate_decks(
                deck_ids=deck_ids,
            )

            return None
