from typing import Callable
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.cards.errors import CardNotFoundError
from app.service import UnitOfWork

from .errors import (
    DeckAlreadyExistsError,
    DeckCardAlreadyExistsError,
    DeckCardNotFoundError,
    DeckNotFoundError,
)
from .models import Deck, DeckCard
from .schemas import (
    DeckCardAdd,
    DeckCardSchema,
    DeckCreate,
    DeckSchema,
    DeckUpdate,
)


class DeckService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def get_by_uuid(self, deck_uuid: UUID) -> DeckSchema:
        async with self.uow_factory() as uow:
            deck = await self._get_by_uuid(uow, deck_uuid)
            return DeckSchema.model_validate(deck)

    async def _get_by_uuid(
        self,
        uow: UnitOfWork,
        deck_uuid: UUID,
    ) -> Deck:
        deck = await uow.deck_repo.get_by_uuid(deck_uuid)

        if deck is None:
            raise DeckNotFoundError(f"Deck with uuid={deck_uuid} not found")

        return deck

    async def _get_card_by_uuid(
        self,
        uow: UnitOfWork,
        card_uuid: UUID,
    ):
        card = await uow.card_repo.get_by_uuid(card_uuid)

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

    async def get_all_decks_by_limit(
        self,
        limit: int = 10,
    ) -> list[DeckSchema]:
        async with self.uow_factory() as uow:
            decks = await uow.deck_repo.get_all_by_limit(limit)
            return [DeckSchema.model_validate(deck) for deck in decks]

    async def get_all_by_user_uuid(
        self,
        user_uuid: int,
        limit: int = 10,
    ) -> list[DeckSchema]:
        async with self.uow_factory() as uow:
            user = await uow.user_repo.get_by_uuid(user_uuid=user_uuid)
            decks = await uow.deck_repo.get_all_by_user_id(
                user_id=user.id,
                limit=limit,
            )
            return [DeckSchema.model_validate(deck) for deck in decks]

    async def get_public_decks_by_limit(
        self,
        limit: int = 10,
    ) -> list[DeckSchema]:
        async with self.uow_factory() as uow:
            decks = await uow.deck_repo.get_public_by_limit(limit)
            return [DeckSchema.model_validate(deck) for deck in decks]

    async def create_deck(
        self,
        payload: DeckCreate,
        user_id: int,
    ) -> DeckSchema:
        try:
            async with self.uow_factory() as uow:
                deck = Deck(
                    **payload.model_dump(),
                    user_id=user_id,
                )

                uow.deck_repo.add(deck)

                await uow.commit()
                await uow.deck_repo.refresh(deck)

                return DeckSchema.model_validate(deck)

        except IntegrityError as e:
            raise DeckAlreadyExistsError() from e

    async def update_deck(
        self,
        deck_uuid: UUID,
        payload: DeckUpdate,
    ) -> DeckSchema:
        try:
            async with self.uow_factory() as uow:
                deck = await self._get_by_uuid(uow, deck_uuid)

                update_data = payload.model_dump(exclude_unset=True)

                for field, value in update_data.items():
                    setattr(deck, field, value)

                await uow.commit()
                await uow.deck_repo.refresh(deck)

                return DeckSchema.model_validate(deck)

        except IntegrityError as e:
            raise DeckAlreadyExistsError() from e

    async def delete_deck(self, deck_uuid: UUID) -> None:
        async with self.uow_factory() as uow:
            deck = await self._get_by_uuid(uow, deck_uuid)

            await uow.deck_repo.delete(deck)
            await uow.commit()

            return None

    async def get_deck_cards(
        self,
        deck_uuid: UUID,
        limit: int = 100,
    ) -> list[DeckCardSchema]:
        async with self.uow_factory() as uow:
            deck = await self._get_by_uuid(uow, deck_uuid)

            deck_cards = await uow.deck_card_repo.get_all_by_deck_id(
                deck_id=deck.id,
                limit=limit,
            )

            return [
                DeckCardSchema.model_validate(deck_card)
                for deck_card in deck_cards
            ]

    async def add_card_to_deck(
        self,
        deck_uuid: UUID,
        card_uuid: UUID,
        payload: DeckCardAdd,
    ) -> DeckCardSchema:
        try:
            async with self.uow_factory() as uow:
                deck = await self._get_by_uuid(uow, deck_uuid)
                card = await self._get_card_by_uuid(uow, card_uuid)

                existing_link = await uow.deck_card_repo.get_by_deck_id_and_card_id(
                    deck_id=deck.id,
                    card_id=card.id,
                )

                if existing_link is not None:
                    raise DeckCardAlreadyExistsError(
                        "Card already exists in this deck"
                    )

                deck_card = DeckCard(
                    deck_id=deck.id,
                    card_id=card.id,
                    position=payload.position,
                )

                uow.deck_card_repo.add(deck_card)

                await uow.commit()
                await uow.deck_card_repo.refresh(deck_card)

                return DeckCardSchema.model_validate(deck_card)

        except IntegrityError as e:
            raise DeckCardAlreadyExistsError() from e

    async def update_deck_card(
        self,
        deck_card_uuid: UUID,
        position: int,
    ) -> DeckCardSchema:
        async with self.uow_factory() as uow:
            deck_card = await self._get_deck_card_by_uuid(uow, deck_card_uuid)

            deck_card.position = position

            await uow.commit()
            await uow.deck_card_repo.refresh(deck_card)

            return DeckCardSchema.model_validate(deck_card)

    async def remove_card_from_deck(
        self,
        deck_uuid: UUID,
        card_uuid: UUID,
    ) -> None:
        async with self.uow_factory() as uow:
            deck = await self._get_by_uuid(uow, deck_uuid)
            card = await self._get_card_by_uuid(uow, card_uuid)

            deck_card = await uow.deck_card_repo.get_by_deck_id_and_card_id(
                deck_id=deck.id,
                card_id=card.id,
            )

            if deck_card is None:
                raise DeckCardNotFoundError(
                    f"Card with uuid={card_uuid} not found in deck uuid={deck_uuid}"
                )

            await uow.deck_card_repo.delete(deck_card)
            await uow.commit()

            return None