from collections.abc import Sequence
from datetime import datetime
from uuid import UUID
from app.tracing import traced

from app.cards.models import Card
from app.common.query import apply_date_pagination, apply_search
from app.common.types import SearchQuery
from app.common.utils import utcnow
from app.users.models import User
from sqlalchemy import Integer, Select, and_, cast, delete, exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.decks.query import apply_library_pagination
from app.decks.schemas import ArchiveCleanupBatch, DeckLoad, LibraryCursor
from app.decks.utils import make_user_deck_identity
from app.redis.schemas import UserDeckIdentity
from app.training_sessions.models import TrainingSession

from .models import Deck, DeckArchiveRecipient, DeckCard, UserDeck


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

    def add_archive_recipients(
        self, recipients: list[DeckArchiveRecipient],
    ) -> None:
        self.session.add_all(recipients)

    @traced("decks.repository.get_archive_recipient_for_update")
    async def get_archive_recipient_for_update(
        self, archive_deck_id: int, user_id: int,
    ) -> DeckArchiveRecipient | None:
        stmt = (
            select(DeckArchiveRecipient)
            .where(
                DeckArchiveRecipient.archive_deck_id == archive_deck_id,
                DeckArchiveRecipient.user_id == user_id,
            )
            .with_for_update(of=DeckArchiveRecipient)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    @traced("decks.repository.get_archives_for_recipient")
    async def get_archives_for_recipient(
        self, user_id: int, now: datetime,
    ) -> list[tuple[Deck, DeckArchiveRecipient]]:
        stmt = (
            select(Deck, DeckArchiveRecipient)
            .join(
                DeckArchiveRecipient,
                DeckArchiveRecipient.archive_deck_id == Deck.id,
            )
            .where(
                DeckArchiveRecipient.user_id == user_id,
                Deck.state == "archived",
                Deck.expires_at > now,
            )
            .order_by(Deck.expires_at, Deck.id)
        )
        return list((await self.session.execute(stmt)).tuples().all())

    @traced("decks.repository.get_with_archive_recipient")
    async def get_with_archive_recipient(
        self, deck_uuid: UUID, user_id: int,
    ) -> tuple[Deck, DeckArchiveRecipient | None] | None:
        stmt = (
            select(Deck, DeckArchiveRecipient)
            .outerjoin(
                DeckArchiveRecipient,
                and_(
                    DeckArchiveRecipient.archive_deck_id == Deck.id,
                    DeckArchiveRecipient.user_id == user_id,
                ),
            )
            .where(Deck.uuid == deck_uuid)
        )
        row = (await self.session.execute(stmt)).one_or_none()
        return (row[0], row[1]) if row is not None else None

    # read
    async def get_by_id(
            self,
            deck_id: int,
    ) -> Deck | None:
        stmt = select(Deck).where(Deck.id == deck_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @traced("decks.repository.lock_deck_graph")
    async def lock_deck_graph(
        self,
        deck_uuid: UUID,
    ) -> tuple[Deck, list[DeckCard], list[Card]] | None:
        deck = (await self.session.execute(
            select(Deck)
            .where(Deck.uuid == deck_uuid)
            .with_for_update(of=Deck)
        )).scalar_one_or_none()

        if deck is None:
            return None

        deck_cards = (
            await self.session.execute(
                select(DeckCard)
                .where(DeckCard.deck_id == deck.id)
                .order_by(DeckCard.id)
                .with_for_update(of=DeckCard)
            )
        ).scalars().all()

        cards = (
            (
                await self.session.execute(
                    select(Card)
                    .join(DeckCard, DeckCard.card_id == Card.id)
                    .where(DeckCard.deck_id == deck.id)
                    .order_by(Card.id)
                    .with_for_update(of=Card)
                )
            ).scalars().all()
        )

        return deck, list(deck_cards), list(cards)

    async def lock_owned_public_deck_graphs(
        self, owner_id: int,
    ) -> list[tuple[Deck, list[DeckCard], list[Card]]]:
        decks = list((await self.session.execute(
            select(Deck)
            .where(
                Deck.user_id == owner_id,
                Deck.state == "active",
                Deck.is_public.is_(True),
            )
            .order_by(Deck.id)
            .with_for_update(of=Deck)
        )).scalars().all())
        if not decks:
            return []

        deck_ids = [deck.id for deck in decks]
        links = list((await self.session.execute(
            select(DeckCard)
            .where(DeckCard.deck_id.in_(deck_ids))
            .order_by(DeckCard.id)
            .with_for_update(of=DeckCard)
        )).scalars().all())
        card_ids = sorted({link.card_id for link in links})
        cards = (
            list((await self.session.execute(
                select(Card)
                .where(Card.id.in_(card_ids))
                .order_by(Card.id)
                .with_for_update(of=Card)
            )).scalars().all())
            if card_ids else []
        )
        links_by_deck: dict[int, list[DeckCard]] = {deck.id: [] for deck in decks}
        for link in links:
            links_by_deck[link.deck_id].append(link)
        cards_by_id = {card.id: card for card in cards}
        return [
            (
                deck,
                links_by_deck[deck.id],
                [cards_by_id[link.card_id] for link in links_by_deck[deck.id]],
            )
            for deck in decks
        ]

    @traced("decks.repository.get_by_uuid")
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


    async def delete_expired_archived_decks(
        self,
        now: datetime,
        limit: int,
    ) -> ArchiveCleanupBatch:
        decks = (await self.session.execute(
            select(Deck.id, Deck.uuid)
            .where(
                Deck.state == "archived",
                Deck.expires_at <= now,
            )
            .order_by(Deck.expires_at, Deck.id)
            .limit(limit)
            .with_for_update(of=Deck, skip_locked=True)
        )).tuples().all()
        if not decks:
            return ArchiveCleanupBatch()

        deck_ids = [deck_id for deck_id, _ in decks]

        candidate_card_ids = (
            await self.session.execute(
                select(Card.id)
                .where(
                    Card.user_id.is_(None),
                    Card.id.in_(
                        select(DeckCard.card_id)
                        .where(DeckCard.deck_id.in_(deck_ids))
                    ),
                )
                .order_by(Card.id)
                .with_for_update(of=Card)
            )
        ).scalars().all()

        # блокируем сессии, чтобы они не меняли/блокировали UserDeck
        await self.session.execute(
            select(TrainingSession.id)
            .where(TrainingSession.deck_id.in_(deck_ids))
            .order_by(TrainingSession.id)
            .with_for_update(of=TrainingSession)
        )

        user_deck_keys = (
            await self.session.execute(
                select(UserDeck.user_id, UserDeck.deck_id)
                .where(UserDeck.deck_id.in_(deck_ids))
            )
        ).tuples().all()

        # cascade:
        # delete deck_cards, user_decks, deck_archive_recipients
        # training_sessions.deck_id = NULL
        await self.session.execute(
            delete(Deck)
            .where(Deck.id.in_(deck_ids))
            .execution_options(synchronize_session=False)
        )

        deleted_cards: list[tuple[int, UUID]] = []

        if candidate_card_ids:
            deleted_cards = (
                await self.session.execute(
                    delete(Card)
                    .where(
                        Card.id.in_(candidate_card_ids),
                        Card.user_id.is_(None),
                        ~exists().where(DeckCard.card_id == Card.id),
                    )
                    .returning(Card.id, Card.uuid)
                    .execution_options(synchronize_session=False)
                )
            ).tuples().all()

        return ArchiveCleanupBatch(
            decks=list(decks),
            cards=deleted_cards,
            user_deck_keys=[
                make_user_deck_identity(user_id=user_id, deck_id=deck_id)
                for user_id, deck_id in user_deck_keys
            ],
        )

        

    @traced("decks.repository.get_visible_by_uuid")
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

    @traced("decks.repository.get_owned_by_uuid")
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

    @traced("decks.repository.get_public_decks")
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

    @traced("decks.repository.get_public_by_owner_id")
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
    ) -> Sequence[Deck]:
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

    @traced("decks.repository.get_owned_by_owner_id")
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

    @traced("decks.repository.get_library_by_user_id")
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
    @traced("decks.deck_card_repository.get_by_deck_id_and_card_id")
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

    @traced("decks.deck_card_repository.get_cards_by_deck_id")
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

    @traced("decks.repository.get_cards_by_deck_ids")
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

    @traced("decks.deck_card_repository.get_max_position")
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
    @traced("decks.deck_card_repository.reorder_cards")
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

    @traced("decks.deck_card_repository.update_deck_cards_positions_after_deleting")
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
                    version=Deck.version + 1,
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
    @traced("decks.user_deck_repository.lock_for_transfer")
    async def lock_for_transfer(
        self,
        deck_id: int,
        user_ids: tuple[int, ...] | None,
    ) -> list[UserDeck]:
        stmt = select(UserDeck).where(UserDeck.deck_id == deck_id)
        if user_ids is not None:
            stmt = stmt.where(UserDeck.user_id.in_(user_ids))
        stmt = stmt.order_by(UserDeck.user_id).with_for_update(of=UserDeck)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    @traced("decks.user_deck_repository.count_saved")
    async def count_saved(self, deck_id: int) -> int:
        stmt = select(func.count()).select_from(UserDeck).where(
            UserDeck.deck_id == deck_id,
            UserDeck.is_saved.is_(True),
        )
        return int(await self.session.scalar(stmt) or 0)

    @traced("decks.user_deck_repository.get_archive_recipient_user_ids")
    async def get_archive_recipient_user_ids(self, deck_id: int) -> list[int]:
        stmt = (
            select(UserDeck.user_id)
            .where(
                UserDeck.deck_id == deck_id,
                or_(
                    UserDeck.is_saved.is_(True),
                    UserDeck.sessions_count > 0,
                    UserDeck.correct_count > 0,
                    UserDeck.wrong_count > 0,
                    UserDeck.last_studied_at.is_not(None),
                ),
            )
            .order_by(UserDeck.user_id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_archive_recipient_pairs(
        self, deck_ids: list[int],
    ) -> list[tuple[int, int]]:
        if not deck_ids:
            return []
        stmt = (
            select(UserDeck.deck_id, UserDeck.user_id)
            .where(
                UserDeck.deck_id.in_(deck_ids),
                or_(
                    UserDeck.is_saved.is_(True),
                    UserDeck.sessions_count > 0,
                    UserDeck.correct_count > 0,
                    UserDeck.wrong_count > 0,
                    UserDeck.last_studied_at.is_not(None),
                ),
            )
            .order_by(UserDeck.deck_id, UserDeck.user_id)
        )
        return list((await self.session.execute(stmt)).tuples().all())


    # checked
    async def get_user_ids_who_saved_deck(
        self,
        deck_id: int,
    ) -> Sequence[int]:
        stmt = (
            select(User.id)
            .join(
                UserDeck, UserDeck.user_id == User.id,
            )
            .where(
                UserDeck.deck_id == deck_id,
                UserDeck.is_saved.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    @traced("decks.repository.get_by_user_id_and_deck_id")
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

    @traced("decks.repository.get_user_decks_by_deck_ids")
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

    @traced("decks.user_deck_repository.get_user_ids_by_deck_ids")
    async def get_user_ids_by_deck_ids(
        self,
        deck_ids: list[int],
    ) -> list[int]:
        stmt = (
            select(User.id)
            .join(UserDeck, UserDeck.user_id == User.id)
            .where(
                UserDeck.deck_id.in_(deck_ids)
            )
            .distinct()
            .order_by(User.id.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_library_user_ids_by_deck_ids(
        self,
        deck_ids: list[int],
    ) -> list[int]:
        """Владельцы и сохранившие колоды, включая смену видимости."""
        if not deck_ids:
            return []
        owner_ids = select(Deck.user_id.label("user_id")).where(
            Deck.id.in_(deck_ids),
            Deck.user_id.is_not(None),
        )
        saved_ids = (
            select(UserDeck.user_id)
            .join(Deck, Deck.id == UserDeck.deck_id)
            .where(
                Deck.id.in_(deck_ids),
                Deck.user_id.is_not(None),
                UserDeck.is_saved.is_(True),
            )
        )
        stmt = owner_ids.union(saved_ids).order_by("user_id")
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_user_deck_keys_by_deck_ids(
        self, deck_ids: list[int],
    ) -> list[UserDeckIdentity]:
        if not deck_ids:
            return []
        stmt = (
            select(UserDeck.user_id, UserDeck.deck_id)
            .where(UserDeck.deck_id.in_(deck_ids))
            .order_by(UserDeck.deck_id, UserDeck.user_id)
        )
        return [
            make_user_deck_identity(user_id=user_id, deck_id=deck_id)
            for user_id, deck_id in (await self.session.execute(stmt)).tuples().all()
        ]

    async def get_user_deck_keys_by_user_id(
        self,
        user_id: int,
    ) -> list[UserDeckIdentity]:
        stmt = (
            select(UserDeck.user_id, UserDeck.deck_id)
            .where(UserDeck.user_id == user_id)
            .order_by(UserDeck.deck_id)
        )
        return [
            make_user_deck_identity(user_id=user_id, deck_id=deck_id)
            for user_id, deck_id in (await self.session.execute(stmt)).tuples().all()
        ]

    @traced("decks.user_deck_repository.get_saved_decks_by_user_id")
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

    @traced("decks.repository.get_favourite_decks_by_user_id")
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
