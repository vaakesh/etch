from unittest.mock import AsyncMock

import pytest
from sqlalchemy import Boolean, Column, Integer, MetaData, Table, create_engine

from app.decks.repository import UserDeckRepository


@pytest.fixture
def library_users_context():
    metadata = MetaData()
    decks = Table(
        "decks", metadata,
        Column("id", Integer, primary_key=True),
        Column("user_id", Integer),
        Column("is_public", Boolean),
    )
    states = Table(
        "user_decks", metadata,
        Column("user_id", Integer, primary_key=True),
        Column("deck_id", Integer, primary_key=True),
        Column("is_saved", Boolean),
        Column("sessions_count", Integer),
    )
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(decks.insert(), [
            dict(id=200, user_id=42, is_public=True),
            dict(id=201, user_id=43, is_public=False),
            dict(id=202, user_id=None, is_public=False),
        ])
        connection.execute(states.insert(), [
            dict(user_id=42, deck_id=200, is_saved=False, sessions_count=0),
            dict(user_id=7, deck_id=200, is_saved=True, sessions_count=0),
            dict(user_id=8, deck_id=200, is_saved=False, sessions_count=3),
            dict(user_id=9, deck_id=200, is_saved=False, sessions_count=0),
            dict(user_id=7, deck_id=201, is_saved=True, sessions_count=0),
            dict(user_id=7, deck_id=202, is_saved=True, sessions_count=3),
        ])
        session = AsyncMock()
        session.execute.side_effect = connection.execute
        yield UserDeckRepository(session), session
    engine.dispose()


class TestGetLibraryUserIdsByDeckIds:
    async def test_returns_owner_and_savers_without_unsaved_training_users(self, library_users_context):
        repository, _ = library_users_context

        result = await repository.get_library_user_ids_by_deck_ids([200])

        assert result == [7, 42]

    async def test_includes_owner_without_user_deck_and_savers_before_publication(self, library_users_context):
        repository, _ = library_users_context

        result = await repository.get_library_user_ids_by_deck_ids([201])

        assert result == [7, 43]

    async def test_deduplicates_users_across_decks(self, library_users_context):
        repository, _ = library_users_context

        result = await repository.get_library_user_ids_by_deck_ids([200, 201])

        assert result == [7, 42, 43]

    @pytest.mark.parametrize("deck_ids", [[202], [999]])
    async def test_excludes_archives_and_missing_decks(self, library_users_context, deck_ids):
        repository, _ = library_users_context

        result = await repository.get_library_user_ids_by_deck_ids(deck_ids)

        assert result == []

    async def test_does_not_query_for_empty_deck_ids(self, library_users_context):
        repository, session = library_users_context

        result = await repository.get_library_user_ids_by_deck_ids([])

        assert result == []
        session.execute.assert_not_awaited()
