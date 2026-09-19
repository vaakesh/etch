from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.cards.models import Card
from app.common.query import apply_date_pagination, apply_search
from app.common.types import SearchQuery
from app.common.utils import utcnow
from app.users.models import User
from sqlalchemy import Integer, Select, and_, cast, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.decks.query import apply_library_pagination
from app.decks.schemas import DeckLoad, LibraryCursor

from .models import Deck, DeckCard, UserDeck


class DeckRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # helpers
    def _deck_stmt(
        self,
        load: DeckLoad,
    ) -> Select[tuple[Deck]]:
        stmt = select(Deck)

        if load.user:
            stmt = stmt.options(
                joinedload(Deck.user)
            )
        # cards include card_links
        if load.cards:
            stmt = stmt.options(
                selectinload(Deck.card_links)
                .selectinload(DeckCard.card)
            )
        elif load.card_links:
            stmt = stmt.options(
                selectinload(Deck.card_links)
            )

        return stmt

    def _visible_decks_stmt(
        self,
        viewer_id: int | None,
    ) -> Select[tuple[Deck]]:
        stmt = self._deck_stmt(load=DeckLoad(
            user=True,
        ))

        if viewer_id is None:
            return stmt.where(
                Deck.is_public.is_(True),
            )

        return stmt.where(
            or_(
                Deck.is_public.is_(True),
                Deck.user_id == viewer_id,
            )
        )

    def _owned_decks_stmt(
        self,
        owner_id: int,
    ) -> Select[tuple[Deck]]:
        return self._deck_stmt(
            load=DeckLoad(
                user=True,
            ),
        ).where(
            Deck.user_id == owner_id,
        )

    # base
    def add(self, deck: Deck) -> None:
        self.session.add(deck)

    def add_all(self, decks: list[Deck]) -> None:
        self.session.add_all(decks)

    async def refresh(self, deck: Deck) -> None:
        await self.session.refresh(deck)

    async def delete(self, deck: Deck) -> None:
        await self.session.delete(deck)

    # read
    async def get_by_id(
            self,
            deck_id: int,
    ) -> Deck | None:
        stmt = select(Deck).where(Deck.id == deck_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_uuid(
            self, 
            deck_uuid: UUID,
            load: DeckLoad = DeckLoad(),
            for_update: bool = False
        ) -> Deck | None:
        stmt = self._deck_stmt(
            load=load,
        )
        stmt = stmt.where(Deck.uuid == deck_uuid)
        if for_update:
            stmt = stmt.with_for_update(of=Deck)

        result = await self.session.execute(stmt)
        rows = result.scalar_one_or_none()
        return rows

    async def get_by_uuid_and_is_public(self, deck_uuid: UUID) -> Deck | None:
        stmt = (
            select(Deck)
            .where(
                Deck.uuid == deck_uuid,
                Deck.is_public.is_(True),    
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_visible_by_uuid(
        self,
        deck_uuid: UUID,
        viewer_id: int,
    ) -> Deck | None:
        stmt = (
            self._visible_decks_stmt(
                viewer_id=viewer_id,
            )
            .where(
                Deck.uuid == deck_uuid
            )
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_owned_by_uuid(
        self,
        deck_uuid: UUID,
        owner_id: int,
        for_update: bool = False,
    ) -> Deck | None:
        stmt = (
            self._owned_decks_stmt(
                owner_id=owner_id,
            ).where(
                Deck.uuid == deck_uuid,
            )
        )

        if for_update:
            stmt = stmt.with_for_update(of=Deck)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_decks_with_all_cards(
        self,
        deck_ids: list[int],
        for_update: bool = False,
    ) -> list[Deck]:
        stmt = (
            select(Deck)
            .options(
                selectinload(Deck.card_links).selectinload(DeckCard.card)
            )
            .where(Deck.id.in_(deck_ids))
        )
        if for_update:
            stmt = stmt.with_for_update(of=Deck)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_visible_by_ids(
        self,
        deck_ids: list[int],
        viewer_id: int,
    ) -> list[Deck]:
        stmt = (
            self._visible_decks_stmt(
                viewer_id=viewer_id,
            )
            .where(
                Deck.id.in_(deck_ids),
            )
        )

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return rows

    async def has_archivable_user_decks(
        self,
        deck_id: int,
        exclude_user_id: int | None,
    ) -> bool:
        query = exists().where(
            UserDeck.deck_id == deck_id,
            or_(UserDeck.is_saved.is_(True), UserDeck.sessions_count > 0),
        )
        if exclude_user_id is not None:
            query = query.where(UserDeck.user_id != exclude_user_id)
        return bool(await self.session.scalar(select(query)))

    async def get_public_decks(
        self,
        search_query: SearchQuery = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Deck]:
        stmt = (
            select(Deck)
            .options(
                joinedload(Deck.user).load_only(
                    User.uuid,
                    User.username,
                )
            )
            .where(Deck.is_public)
        )

        stmt = apply_search(stmt, search_query, Deck.title)

        stmt = (
            stmt
            .order_by(Deck.saves_count.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return rows

    async def get_public_by_owner_id(
        self,
        owner_id: int,
        viewer_id: int | None = None,
        search_query: SearchQuery = None,
        cursor_updated_at: datetime | None = None,
        cursor_id: int | None = None,
        limit: int = 30,
    ) -> tuple[list[Deck], bool]:
        stmt = (
            self._visible_decks_stmt(
                viewer_id=viewer_id,
            ).where(
                Deck.user_id == owner_id,
            )
        )
        stmt = apply_search(stmt, search_query, Deck.title)

        stmt = apply_date_pagination(
            stmt,
            date_column=Deck.updated_at,
            id_column=Deck.id,
            cursor_at=cursor_updated_at,
            cursor_id=cursor_id,
            limit=limit,
        )

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def get_visible_to_user_id(
        self,
        viewer_id: int,
        search_query: SearchQuery = None,
        cursor_updated_at: datetime | None = None,
        cursor_id: int | None = None,
        limit: int = 30,
    ) -> tuple[list[Deck], bool]:
        stmt = (
            self._visible_decks_stmt(
                viewer_id=viewer_id,
            )
        )

        stmt = apply_search(stmt, search_query, Deck.title)

        stmt = apply_date_pagination(
            stmt,
            date_column=Deck.updated_at,
            id_column=Deck.id,
            cursor_at=cursor_updated_at,
            cursor_id=cursor_id,
            limit=limit,
        )

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def get_all_by_user_id(
        self,
        user_id: int,
        public_only: bool = True,
    ) -> list[Deck]:
        stmt = (
            select(Deck)
            .options(
                joinedload(Deck.user).load_only(
                    User.uuid,
                    User.username,
                )
            )
            .where(
                Deck.user_id == user_id,
            )
        )
        if public_only:
            stmt = stmt.where(Deck.is_public.is_(True))

        stmt = stmt.order_by(Deck.updated_at.desc(), Deck.id.desc())

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return rows

    async def get_owned_by_owner_id(
        self,
        owner_id: int,
        search_query: SearchQuery = None,
        cursor_updated_at: datetime | None = None,
        cursor_id: int | None = None,
        limit: int = 30,
    ) -> tuple[list[Deck], bool]:
        stmt = (
            self._owned_decks_stmt(
                owner_id=owner_id,
            )
        )

        stmt = apply_search(stmt, search_query, Deck.title)

        stmt = apply_date_pagination(
            stmt,
            date_column=Deck.updated_at,
            id_column=Deck.id,
            cursor_at=cursor_updated_at,
            cursor_id=cursor_id,
            limit=limit,
        )

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def get_saved_by_user_id(
        self,
        user_id: int,
        search_query: SearchQuery = None,
        cursor_updated_at: datetime | None = None,
        cursor_id: int | None = None,
        limit: int = 30,
    ) -> tuple[list[Deck], bool]:
        stmt = (
            self._deck_stmt(load=True)
            .join(
                UserDeck,
                UserDeck.deck_id == Deck.id,
            )
            .where(
                UserDeck.user_id == user_id,
                UserDeck.is_saved.is_(True),
                Deck.user_id != user_id,
                Deck.is_public.is_(True),
            )
        )

        stmt = apply_search(stmt, search_query, Deck.title)

        stmt = apply_date_pagination(
            stmt,
            date_column=Deck.updated_at,
            id_column=Deck.id,
            cursor_at=cursor_updated_at,
            cursor_id=cursor_id,
            limit=limit,
        )

        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def get_library_by_user_id(
        self,
        user_id: int,
        search_query: SearchQuery = None,
        cursor: LibraryCursor | None = None,
        limit: int = 30,
    ) -> tuple[list[Deck], tuple[Deck, UserDeck] | None]:
        stmt = (
            select(Deck, UserDeck)
            .options(
                joinedload(Deck.user).load_only(
                    User.uuid,
                    User.username,
                ),
            )
            .join(
                UserDeck,
                and_(
                    UserDeck.deck_id == Deck.id,
                    UserDeck.user_id == user_id,
                ),
            )
            .where(
                or_(
                    Deck.user_id == user_id,
                    and_(
                        UserDeck.is_saved.is_(True),
                        Deck.user_id != user_id,
                        Deck.is_public.is_(True),
                    ),
                )
            )
        )

        stmt = apply_search(stmt, search_query, Deck.title)

        stmt = apply_library_pagination(stmt, cursor=cursor, limit=limit)

        result = await self.session.execute(stmt)
        rows = list(result.tuples().all())

        has_more = len(rows) > limit
        page_rows = rows[:limit]
        decks = [deck for deck, _ in page_rows]
        last_item = page_rows[-1] if has_more and page_rows else None
        return decks, last_item

    # write
    async def reassign_saves_user_deck(
        self,
        user_id: int,
        from_deck_id: int,
        to_deck_id: int,
    ) -> None:
        stmt = (
            update(UserDeck)
            .where(
                UserDeck.deck_id == from_deck_id,
                UserDeck.user_id == user_id,
                UserDeck.is_saved.is_(True),
            )
            .values(
                deck_id=to_deck_id,
            )
        )
        await self.session.execute(stmt)

    async def reassign_user_decks(
        self,
        from_deck_id: int,
        to_deck_id: int,
        exclude_user_id: int | None,
    ) -> list[tuple[int, bool]]:
        stmt = (
            update(UserDeck)
            .where(
                UserDeck.deck_id == from_deck_id,
            )
            .values(
                deck_id=to_deck_id,
            )
            .returning(UserDeck.user_id, UserDeck.is_saved)
        )
        if exclude_user_id is not None:
            stmt = stmt.where(UserDeck.user_id != exclude_user_id)
        result = await self.session.execute(stmt)
        return list(result.tuples().all())


class DeckCardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # base
    def add(self, deck_card: DeckCard) -> None:
        self.session.add(deck_card)

    def add_all(self, deck_cards: list[DeckCard]) -> None:
        self.session.add_all(deck_cards)

    async def refresh(self, deck_card: DeckCard) -> None:
        await self.session.refresh(deck_card)

    async def delete(self, deck_card: DeckCard) -> None:
        await self.session.delete(deck_card)

    # read
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

    async def get_cards_by_deck_id(
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

    async def get_cards_by_deck_ids(
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

    async def get_all_deck_ids_by_card_ids(
            self,
            card_ids: list[int],
            for_update: bool = False,
    ) -> list[int]:
        if not card_ids:
            return []

        stmt = (
            select(Deck.id)
            .where(
                exists().where(
                    DeckCard.deck_id == Deck.id,
                    DeckCard.card_id.in_(card_ids),
                )
            )
            .order_by(Deck.id.asc())
        )
        if for_update:
            stmt = stmt.with_for_update(of=Deck)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_max_position(
            self,
            deck_id: int,
    ) -> int | None:
        stmt = (
            select(DeckCard.position)
            .where(DeckCard.deck_id == deck_id)
            .order_by(DeckCard.position.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        max_position = result.scalar_one_or_none()
        return max_position

    # write
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

    async def normalize_positions(
        self,
        deck_ids: list[int],
    ) -> None:
        if not deck_ids:
            return

        ranked_positions = (
            select(
                DeckCard.id.label("deck_card_id"),
                cast(
                    func.row_number().over(
                        partition_by=DeckCard.deck_id,
                        order_by=(
                            DeckCard.position.asc(),
                            DeckCard.id.asc(),
                        ),
                    ),
                    Integer,
                ).label("position"),
            )
            .where(DeckCard.deck_id.in_(deck_ids))
            .cte("ranked_deck_card_positions")
        )

        stmt = (
            update(DeckCard)
            .where(
                DeckCard.id == ranked_positions.c.deck_card_id,
                DeckCard.position != ranked_positions.c.position,
            )
            .values(position=ranked_positions.c.position)
        )
        await self.session.execute(stmt)

    async def update_deck_cards_positions_after_deleting(
        self,
        deck_id: int,
        deleted_position: int,
    ) -> None:
        stmt = (
            update(DeckCard)
            .where(
                DeckCard.deck_id == deck_id,
                DeckCard.position > deleted_position,
            )
            .values(
                position = DeckCard.position - 1,
            )
        )

        await self.session.execute(stmt)
        return None

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
                    ),
                    updated_at=utcnow(),
                )
                .where(Deck.id.in_(deck_ids))
            )
            await self.session.execute(stmt)


class UserDeckRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # base
    def add(self, user_deck: UserDeck):
        self.session.add(user_deck)

    # read
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

    async def get_user_decks_by_deck_ids(
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

    async def get_user_ids_by_deck_ids(
        self,
        deck_ids: list[int],
    ) -> list[int]:
        stmt = (
            select(User.id)
            .join(UserDeck, UserDeck.user_id == UserDeck.deck_id)
            .where(
                UserDeck.deck_id.in_(deck_ids)
            )
            .distinct()
            .order_by(User.id.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_saved_decks_by_user_id(
            self,
            user_id: int,
            offset: int,
            limit: int,
    ) -> Sequence[tuple[Deck, UserDeck]]:
        stmt = (
            select(
                Deck,
                UserDeck,
            )
            .options(
                joinedload(Deck.user).load_only(
                    User.uuid,
                    User.username,
                )
            )
            .join(Deck, UserDeck.deck_id == Deck.id)
            .where(
                UserDeck.user_id == user_id,
                UserDeck.is_saved.is_(True),
                or_(
                    Deck.is_public.is_(True),
                    and_(
                        Deck.is_public.is_(False),
                        Deck.user_id == user_id,
                    ),
                )
            )
            .order_by(
                Deck.updated_at.desc(),
                Deck.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        
        result = await self.session.execute(stmt)
        rows = result.all()
        return rows

    async def get_favourite_decks_by_user_id(
            self,
            user_id: int,
            search_query: SearchQuery = None,
            cursor_updated_at: datetime | None = None,
            cursor_id: int | None = None,
            limit: int = 16,
    ) -> tuple[list[Deck], bool]:
        stmt = (
            select(Deck)
            .options(
                joinedload(Deck.user).load_only(
                    User.uuid,
                    User.username,
                )
            )
            .join(UserDeck, UserDeck.deck_id == Deck.id)
            .where(
                UserDeck.user_id == user_id,
                UserDeck.is_favourite.is_(True),
                or_(
                    Deck.is_public.is_(True),
                    and_(
                        Deck.is_public.is_(False),
                        Deck.user_id == user_id,
                    )
                )
            )
        )

        stmt = apply_search(stmt, search_query, Deck.title)

        stmt = apply_date_pagination(
            stmt,
            date_column=Deck.updated_at,
            id_column=Deck.id,
            cursor_at=cursor_updated_at,
            cursor_id=cursor_id,
            limit=limit,
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        
        return rows[:limit], has_more

    # write
    async def transfer_user_progress(
        self,
        from_deck_id: int,
        to_deck_id: int,
        user_id: int,
    ) -> UserDeck:
        stmt = (

        )
