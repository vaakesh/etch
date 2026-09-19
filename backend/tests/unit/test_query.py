from datetime import datetime

import pytest
from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, create_engine, select

from app.common.query import apply_date_pagination, apply_search
from app.decks.models import Deck, UserDeck
from app.decks.query import apply_library_pagination
from app.decks.schemas import LibraryCursor


@pytest.fixture
def query_db():
    metadata = MetaData()
    decks = Table(
        "decks", metadata,
        Column("id", Integer, primary_key=True),
        Column("title", String), Column("description", String),
        Column("updated_at", DateTime),
    )
    links = Table(
        "user_decks", metadata,
        Column("deck_id", Integer, primary_key=True),
        Column("last_studied_at", DateTime), Column("added_at", DateTime),
    )
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(decks.insert(), [
            dict(id=1, title="Red", description="blue", updated_at=datetime(2026, 1, 1)),
            dict(id=2, title="red blue", description="", updated_at=datetime(2026, 1, 2)),
            dict(id=3, title="red", description="green", updated_at=datetime(2026, 1, 2)),
            dict(id=4, title="100%_done", description="", updated_at=datetime(2026, 1, 3)),
            dict(id=5, title="100XXdone", description="", updated_at=datetime(2026, 1, 3)),
        ])
        connection.execute(links.insert(), [
            dict(deck_id=1, last_studied_at=None, added_at=datetime(2026, 1, 1)),
            dict(deck_id=2, last_studied_at=None, added_at=datetime(2026, 1, 2)),
            dict(deck_id=3, last_studied_at=None, added_at=datetime(2026, 1, 2)),
            dict(deck_id=4, last_studied_at=datetime(2026, 1, 3), added_at=datetime(2026, 1, 2)),
            dict(deck_id=5, last_studied_at=datetime(2026, 1, 3), added_at=datetime(2026, 1, 2)),
        ])
        yield connection, decks
    engine.dispose()


class TestApplySearch:
    @pytest.mark.parametrize("query", ["red blue", "  RED\tblue  "])
    def test_requires_every_term_across_fields(self, query_db, query):
        connection, decks = query_db

        stmt = apply_search(select(decks.c.id), query, decks.c.title, decks.c.description)

        assert connection.scalars(stmt.order_by(decks.c.id)).all() == [1, 2]

    def test_searches_only_selected_field(self, query_db):
        connection, decks = query_db

        stmt = apply_search(select(decks.c.id), "red blue", decks.c.title)

        assert connection.scalars(stmt).all() == [2]

    def test_treats_wildcards_as_literal_characters(self, query_db):
        connection, decks = query_db

        stmt = apply_search(select(decks.c.id), "%_", decks.c.title)

        assert connection.scalars(stmt).all() == [4]

    @pytest.mark.parametrize("query", [None, "", "  \t "])
    def test_keeps_all_rows_without_terms(self, query_db, query):
        connection, decks = query_db

        stmt = apply_search(select(decks.c.id), query, decks.c.title)

        assert connection.scalars(stmt.order_by(decks.c.id)).all() == [1, 2, 3, 4, 5]

    def test_rejects_missing_search_columns(self):
        with pytest.raises(ValueError, match="at least one column"):
            apply_search(select(Deck.id), "red")


class TestApplyDatePagination:
    @pytest.mark.parametrize(("at", "cursor_id", "expected"), [
        (None, None, [5, 4, 3]),
        (datetime(2026, 1, 3), 5, [4, 3, 2]),
        (datetime(2026, 1, 2), 3, [2, 1]),
        (datetime(2026, 1, 1), 1, []),
        (None, 3, [5, 4, 3]),
        (datetime(2026, 1, 2), None, [5, 4, 3]),
    ])
    def test_returns_rows_after_boundary_with_one_extra(self, query_db, at, cursor_id, expected):
        connection, decks = query_db

        stmt = apply_date_pagination(
            select(decks.c.id).order_by(decks.c.id),
            date_column=decks.c.updated_at, id_column=decks.c.id,
            cursor_at=at, cursor_id=cursor_id, limit=2,
        )

        assert connection.scalars(stmt).all() == expected

    def test_preserves_filters_when_combined_with_search(self, query_db):
        connection, decks = query_db
        stmt = apply_search(select(decks.c.id).where(decks.c.id != 2), "red", decks.c.title)

        stmt = apply_date_pagination(
            stmt, date_column=decks.c.updated_at, id_column=decks.c.id,
            cursor_at=None, cursor_id=None, limit=1,
        )

        assert connection.scalars(stmt).all() == [3, 1]


class TestApplyLibraryPagination:
    @pytest.mark.parametrize(("cursor", "expected"), [
        (None, [5, 4, 3]),
        (LibraryCursor(last_studied_at=datetime(2026, 1, 3), added_at=datetime(2026, 1, 2), id=5), [4, 3, 2]),
        (LibraryCursor(last_studied_at=datetime(2026, 1, 3), added_at=datetime(2026, 1, 2), id=4), [3, 2, 1]),
        (LibraryCursor(last_studied_at=None, added_at=datetime(2026, 1, 2), id=3), [2, 1]),
        (LibraryCursor(last_studied_at=None, added_at=datetime(2026, 1, 1), id=1), []),
    ])
    def test_pages_through_studied_and_unstudied_decks(self, query_db, cursor, expected):
        connection, _ = query_db
        stmt = select(Deck.id).join(UserDeck, UserDeck.deck_id == Deck.id)

        stmt = apply_library_pagination(stmt, cursor=cursor, limit=2)

        assert connection.scalars(stmt).all() == expected
