from typing import Callable
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.service import UnitOfWork

from app.cards.errors import CardAlreadyExistsError, CardNotFoundError
from .models import Card
from .schemas import CardCreate, CardSchema, CardUpdate


class CardService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def get_by_uuid(self, card_uuid: UUID) -> CardSchema:
        async with self.uow_factory() as uow:
            card = await self._get_by_uuid(uow, card_uuid)
            return CardSchema.model_validate(card)

    async def _get_by_uuid(
        self,
        uow: UnitOfWork,
        card_uuid: UUID,
    ) -> Card:
        card = await uow.card_repo.get_by_uuid(card_uuid)

        if card is None:
            raise CardNotFoundError(f"Card with uuid={card_uuid} not found")

        return card

    async def get_all_cards_by_limit(
        self,
        limit: int = 10,
    ) -> list[CardSchema]:
        async with self.uow_factory() as uow:
            cards = await uow.card_repo.get_all_by_limit(limit)
            return [CardSchema.model_validate(card) for card in cards]

    async def get_all_by_user_uuid(
        self,
        user_uuid: UUID,
        limit: int = 10,
    ) -> list[CardSchema]:
        async with self.uow_factory() as uow:
            user = await uow.user_repo.get_by_uuid(user_uuid=user_uuid)

            cards = await uow.card_repo.get_all_by_user_id(
                user_id=user.id,
                limit=limit,
            )
            return [CardSchema.model_validate(card) for card in cards]

    async def create_card(
        self,
        payload: CardCreate,
        user_id: int,
    ) -> CardSchema:
        try:
            async with self.uow_factory() as uow:
                card = Card(
                    **payload.model_dump(),
                    user_id=user_id,
                )

                uow.card_repo.add(card)

                await uow.commit()
                await uow.card_repo.refresh(card)

                return CardSchema.model_validate(card)

        except IntegrityError as e:
            raise CardAlreadyExistsError() from e

    async def update_card(
        self,
        card_uuid: UUID,
        payload: CardUpdate,
    ) -> CardSchema:
        try:
            async with self.uow_factory() as uow:
                card = await self._get_by_uuid(uow, card_uuid)

                update_data = payload.model_dump(exclude_unset=True)

                for field, value in update_data.items():
                    setattr(card, field, value)

                await uow.commit()
                await uow.card_repo.refresh(card)

                return CardSchema.model_validate(card)

        except IntegrityError as e:
            raise CardAlreadyExistsError() from e

    async def delete_card(self, card_uuid: UUID) -> None:
        async with self.uow_factory() as uow:
            card = await self._get_by_uuid(uow, card_uuid)

            await uow.card_repo.delete(card)
            await uow.commit()

            return None