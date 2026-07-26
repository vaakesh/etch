from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.cards.models import Card
from app.decks.schemas import DeckWithUserDataInternal
from app.users.models import User
from app.bff.utils import calculate_accuracy

from .models import Deck, DeckCard, UserDeck


class DeckRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_uuid(self, deck_uuid: UUID, for_update: bool = False) -> Deck | None:
        stmt = select(Deck).where(Deck.uuid == deck_uuid)
        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(
            self,
            deck_id: int,
    ) -> Deck | None:
        stmt = select(Deck).where(Deck.id == deck_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_uuid_and_is_public(self, deck_uuid: UUID) -> Deck | None:
        stmt = (
            select(Deck)
            .where(
                Deck.uuid == deck_uuid,
                Deck.is_public == True,    
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_limit(self, limit: int = 10) -> list[Deck]:
        stmt = select(Deck).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_by_user_id(
        self,
        user_id: int,
        limit: int = 10,
    ) -> list[Deck]:
        stmt = (
            select(Deck)
            .where(Deck.user_id == user_id)
            .limit(limit)
            .order_by(Deck.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_page_by_user_id(
        self,
        user_id: int,
        limit: int = 16,
        cursor: tuple[datetime, int] | None = None,
    ) -> tuple[list[Deck], bool]:
        stmt = select(Deck).where(Deck.user_id == user_id)

        if cursor is not None:
            cursor_updated_at, cursor_id = cursor
            stmt = stmt.where(
                or_(
                    Deck.updated_at < cursor_updated_at,
                    and_(
                        Deck.updated_at == cursor_updated_at,
                        Deck.id < cursor_id,
                    ),
                )
            )

        stmt = stmt.order_by(Deck.updated_at.desc(), Deck.id.desc()).limit(limit + 1)
        result = await self.session.execute(stmt)
        decks = list(result.scalars().all())
        has_more = len(decks) > limit
        return decks[:limit], has_more
    
    async def get_user_statistics_by_decks(
            self,
            deck_ids: list[int],
            user_id: int,
    ) -> list[UserDeck]:
        if not deck_ids:
            return []
        
        stmt = (
            select(UserDeck)
            .where(
                UserDeck.user_id == user_id,
                UserDeck.deck_id.in_(deck_ids),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_public_by_limit(self, limit: int = 10) -> list[Deck]:
        stmt = (
            select(Deck)
            .where(Deck.is_public.is_(True))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def add(self, deck: Deck) -> None:
        self.session.add(deck)

    async def delete(self, deck: Deck) -> None:
        await self.session.delete(deck)

    async def refresh(self, deck: Deck) -> None:
        await self.session.refresh(deck)


class DeckCardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all_decks_by_card_id(
            self,
            card_id: int,
    ) -> list[int]:
        stmt = (
            select(DeckCard.deck_id)
            .where(DeckCard.card_id == card_id)
            .distinct()
        )
        result = await self.session.execute(stmt)
        deck_ids = result.scalars().all()

        return deck_ids

    async def update_cards_count(
            self,
            deck_ids: list[int],
    ) -> None:
        if deck_ids:
            stmt = (
                update(Deck)
                .values(
                    words_count=(
                        select(func.count(DeckCard.id))
                        .where(
                            DeckCard.deck_id == Deck.id,
                        )
                        .scalar_subquery()
                    )
                )
                .where(Deck.id.in_(deck_ids))
            )
            await self.session.execute(stmt)


    async def delete(self, deck_card: DeckCard) -> None:
        await self.session.delete(deck_card)


    async def get_by_uuid(self, deck_card_uuid: UUID) -> DeckCard | None:
        stmt = select(DeckCard).where(DeckCard.uuid == deck_card_uuid)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_max_position(
            self,
            deck_id: int,
    ) -> int:
        stmt = (
            select(DeckCard.position)
            .where(DeckCard.deck_id == deck_id)
            .order_by(DeckCard.position.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        max_position = result.scalar_one_or_none()
        return max_position


    async def reorder_cards(
            self,
            deck_id: int,
            start: int,
            end: int,
            add_to_position: int,
    ):
        stmt = (
            update(DeckCard)
            .where(
                DeckCard.deck_id == deck_id,
                DeckCard.position >= start,
                DeckCard.position < end,
            )
            .values(position=DeckCard.position + add_to_position)
        )
        await self.session.execute(stmt)

    async def get_by_deck_id_and_card_id(
        self,
        deck_id: int,
        card_id: int,
    ) -> DeckCard | None:
        stmt = (
            select(DeckCard)
            .where(
                DeckCard.deck_id == deck_id,
                DeckCard.card_id == card_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_deck_id(
        self,
        deck_id: int,
        offset: int = 0,
        limit: int = 50,
    ) -> list[Card]:
        stmt = (
            select(Card)
            .join(DeckCard, DeckCard.card_id == Card.id)
            .where(DeckCard.deck_id == deck_id)
            .order_by(DeckCard.position.asc(), DeckCard.id.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_deck_cards_by_deck_id(
        self,
        deck_id: int,
    ) -> list[DeckCard]:
        stmt = (
            select(DeckCard)
            .where(DeckCard.deck_id == deck_id)
            .order_by(DeckCard.position.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_all_by_deck_ids(
        self,
        deck_ids: list[int],
        limit: int = 100,
    ) -> list[tuple[int, Card]]:
        if not deck_ids or limit <= 0:
            return []
        
        ranked_deck_cards = (
            select(
                DeckCard.deck_id.label("deck_id"),
                DeckCard.card_id.label("card_id"),
                DeckCard.position.label("position"),
                DeckCard.id.label("deck_card_id"),
                func.row_number()
                .over(
                    partition_by=DeckCard.deck_id,
                    order_by=(
                        DeckCard.position.asc(),
                        DeckCard.id.asc(),
                    ),
                )
                .label("row_number"),
            )
            .where(DeckCard.deck_id.in_(deck_ids))
            .subquery()
        )

        stmt = (
            select(ranked_deck_cards.c.deck_id, Card)
            .join(Card, Card.id == ranked_deck_cards.c.card_id)
            .where(ranked_deck_cards.c.row_number <= limit)
            .order_by(
                ranked_deck_cards.c.deck_id.asc(),
                ranked_deck_cards.c.position.asc(),
                ranked_deck_cards.c.deck_card_id.asc(),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.all())

    def add(self, deck_card: DeckCard) -> None:
        self.session.add(deck_card)

    async def refresh(self, deck_card: DeckCard) -> None:
        await self.session.refresh(deck_card)


class UserDeckRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_favourite_decks_by_user_id(
            self,
            user_id: int,
            limit: int = 16,
            cursor: tuple[datetime, int] | None = None
    ) -> tuple[list[DeckWithUserDataInternal], bool]:
        stmt = (
            select(UserDeck, Deck, User)
            .join(Deck, UserDeck.deck_id == Deck.id)
            .join(User, User.id == Deck.user_id)
            .where(
                UserDeck.user_id == user_id,
                UserDeck.is_favourite.is_(True),
            )
        )

        if cursor is not None:
            cursor_updated_at, cursor_id = cursor
            stmt = stmt.where(
                or_(
                    Deck.updated_at < cursor_updated_at,
                    and_(
                        Deck.updated_at == cursor_updated_at,
                        Deck.id < cursor_id,
                    ),
                )
            )

        stmt = stmt.order_by(
            Deck.updated_at.desc(),
            Deck.id.desc(),
        ).limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.all())
        has_more = len(rows) > limit
        
        decks_with_user_data = []
        for user_deck, deck, owner_deck in rows[:limit]:
            decks_with_user_data.append(
                DeckWithUserDataInternal(
                    deck_id=deck.id,
                    deck_uuid=deck.uuid,
                    owner_id=deck.user_id,
                    owner_uuid=owner_deck.uuid,
                    user_id=user_deck.user_id,
                    title=deck.title,
                    description=deck.description,
                    words_count=deck.words_count,
                    updated_at=deck.updated_at,
                    is_favourite=user_deck.is_favourite,
                    is_following=user_deck.is_following,
                    user_accuracy=calculate_accuracy(user_deck),
                    cards=[],
                )
            )

        return decks_with_user_data[:limit], has_more

    async def get_followed_decks_by_user_id(
            self,
            user_id: int,
            limit: int,
    ) -> list[UserDeck]:
        stmt = (
            select(UserDeck)
            .join(Deck, UserDeck.deck_id == Deck.id)
            .where(
                UserDeck.user_id == user_id,
                UserDeck.is_following.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_user_id_and_deck_id(
            self,
            user_id: int,
            deck_id: int,
            for_update: bool = False,
    ) -> UserDeck | None:
        stmt = (
            select(UserDeck)
            .where(
                UserDeck.user_id == user_id,
                UserDeck.deck_id == deck_id,
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
        
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_favourite(
            self,
            user_id: int,
            deck_id: int,
            value: bool,
    ) -> UserDeck:
        stmt = (
            select(UserDeck)
            .where(
                UserDeck.user_id == user_id,
                UserDeck.deck_id == deck_id,
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        user_deck = result.scalar_one_or_none()

        if user_deck is None:
            user_deck = UserDeck(
                user_id=user_id,
                deck_id=deck_id,
                is_favourite=value,
            )
            self.add(user_deck=user_deck)
        else:
            user_deck.is_favourite = value

        await self.session.flush()
        
        return user_deck
    
    def add(self, user_deck: UserDeck):
        self.session.add(user_deck)
