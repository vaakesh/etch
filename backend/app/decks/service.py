from typing import Callable
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.cards.errors import CardNotFoundError, PermissionDeniedError
from app.cards.schemas import CardSchema
from app.service import UnitOfWork

from .errors import (
    CannotFollowOwnDeckError,
    DeckAlreadyExistsError,
    DeckCardAlreadyExistsError,
    DeckCardNotFoundError,
    DeckIsNotFollowedError,
    DeckNotFoundError,
)
from .models import Deck, DeckCard, UserDeck
from .schemas import (
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
    ) -> Deck:
        try:
            async with self.uow_factory() as uow:
                deck = Deck(
                    **payload.model_dump(),
                    user_id=user_id,
                )

                uow.deck_repo.add(deck)

                await uow.commit()
                await uow.deck_repo.refresh(deck)

                return deck

        except IntegrityError as e:
            raise DeckAlreadyExistsError() from e

    async def update_deck(
        self,
        user_id: int,
        deck_uuid: UUID,
        payload: DeckUpdate,
    ) -> DeckSchema:
        try:
            async with self.uow_factory() as uow:
                deck = await self._get_by_uuid(uow, deck_uuid)

                if deck.user_id != user_id:
                    raise PermissionDeniedError()

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
        user_id: int,
        deck_uuid: UUID,
        offset: int = 0,
        limit: int = 50,
    ) -> list[CardSchema]:
        async with self.uow_factory() as uow:
            deck = await self._get_by_uuid(uow, deck_uuid)

            if deck.user_id != user_id and not deck.is_public:
                raise PermissionDeniedError()

            cards = await uow.deck_card_repo.get_all_by_deck_id(
                deck_id=deck.id,
                offset=offset,
                limit=limit,
            )

            return [
                CardSchema.model_validate(card)
                for card in cards
            ]

    async def add_card_to_deck(
        self,
        user_id: int,
        deck_uuid: UUID,
        card_uuid: UUID,
    ) -> DeckCardSchema:
        try:
            async with self.uow_factory() as uow:
                deck = await self._get_by_uuid(
                    uow=uow,
                    deck_uuid=deck_uuid,
                    for_update=True,
                )

                card = await self._get_card_by_uuid(uow, card_uuid)
                print(deck, card)

                if deck.user_id != user_id or card.user_id != user_id:
                    raise PermissionDeniedError()

                deck_card = await uow.deck_card_repo.get_by_deck_id_and_card_id(
                    deck_id=deck.id,
                    card_id=card.id,
                ) # todo: надо сделать, чтобы можно было добавлять одну карточку в колоду несколько раз

                max_position = await uow.deck_card_repo.get_max_position(
                    deck_id=deck.id,
                )
                if max_position is None:
                    next_position = 0
                else:
                    next_position = max_position + 1

                deck_card = DeckCard(
                    deck_id=deck.id,
                    card_id=card.id,
                    position=next_position,
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
        user_id: int,
        deck_uuid: UUID,
        card_uuid: UUID,
    ) -> None:
        async with self.uow_factory() as uow:
            deck = await self._get_by_uuid(uow, deck_uuid)
            card = await self._get_card_by_uuid(uow, card_uuid)

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

            await uow.deck_card_repo.delete(deck_card)
            await uow.commit()

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
            deck_card = await uow.deck_card_repo.get_by_deck_id_and_card_id(
                deck_id=deck.id,
                card_id=card.id,
            )
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


class UserDeckService:
    def __init__(self, uow_factory: Callable[[], UnitOfWork]) -> None:
        self.uow_factory = uow_factory

    async def unfollow_deck(
            self,
            user_id: int,
            deck_uuid: UUID,
    ) -> UserDeck:
        async with self.uow_factory() as uow:
            deck = await uow.deck_repo.get_by_uuid_and_is_public(deck_uuid=deck_uuid)
            if deck.user_id == user_id:
                raise CannotFollowOwnDeckError()
            if deck is None or not deck.is_public:
                raise DeckNotFoundError()
            
            user_deck = await uow.user_deck_repo.get_by_user_id_and_deck_id(
                user_id=user_id,
                deck_id=deck.id,
            )
            if user_deck is None:
                raise DeckIsNotFollowedError()
            else:
                user_deck.is_following = False
            await uow.commit()
            return user_deck

    async def follow_deck(
            self,
            user_id: int,
            deck_uuid: UUID,
    ) -> UserDeck:
        async with self.uow_factory() as uow:
            deck = await uow.deck_repo.get_by_uuid(deck_uuid=deck_uuid)
            if deck.user_id == user_id:
                raise CannotFollowOwnDeckError()
            if deck is None or not deck.is_public:
                raise DeckNotFoundError()
            
            user_deck = await uow.user_deck_repo.get_by_user_id_and_deck_id(
                user_id=user_id,
                deck_id=deck.id,
            )
            if user_deck is None:
                user_deck = UserDeck(
                    user_id=user_id,
                    deck_id=deck.id,
                    last_seen_version=deck.version,
                    is_following=True,
                )
                uow.user_deck_repo.add(user_deck)
            else:
                user_deck.is_following = True
            await uow.commit()
            return user_deck
        
    async def get_followed_decks_by_user_id(
            self,
            user_id: int,
            limit: int = 10,
    ) -> list[UserDeck]:
        async with self.uow_factory() as uow:
            user_decks = await uow.user_deck_repo.get_followed_decks_by_user_id(
                user_id=user_id,
                limit=limit,
            )
            return user_decks
        

    async def set_favourite_deck(
            self,
            user_id: int,
            deck_uuid: UUID,
            value: bool,
    ):
        async with self.uow_factory() as uow:
            deck = await uow.deck_repo.get_by_uuid(deck_uuid=deck_uuid)
            user_deck = await uow.user_deck_repo.set_favourite(
                user_id=user_id,
                deck_id=deck.id,
                value=value
            )
            await uow.commit()
            return user_deck
