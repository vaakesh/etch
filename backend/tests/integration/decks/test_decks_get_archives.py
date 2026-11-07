from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.utils import utcnow
from app.decks.models import Deck
from tests.integration.reviews.conftest import create_deck
from tests.integration.training_sessions.conftest import start_practice
from tests.integration.users.conftest import AuthClientFactory, UserFactory

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def archive_studied_deck(client: AsyncClient, deck_uuid: str) -> None:
    # Начатая тренировка делает владельца получателем архива при удалении
    await start_practice(client, deck_uuid, "front", 1)
    response = await client.delete(f"/decks/{deck_uuid}")
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def get_archives(client: AsyncClient) -> list[dict[str, Any]]:
    response = await client.get("/decks/archives")
    assert response.status_code == status.HTTP_200_OK
    return response.json()


async def preserve(client: AsyncClient, archive_uuid: str) -> str:
    response = await client.post(f"/decks/{archive_uuid}/preserve")
    assert response.status_code == status.HTTP_200_OK
    return response.json()["uuid"]


async def get_archive_uuids_by_source(
    async_session_maker: async_sessionmaker[AsyncSession],
    source_deck_uuid: str,
) -> list[str]:
    async with async_session_maker() as session:
        rows = await session.scalars(
            select(Deck.uuid)
            .where(
                Deck.state == "archived",
                Deck.source_deck_uuid_snapshot == UUID(source_deck_uuid),
            )
            .order_by(Deck.id)
        )
        return [str(deck_uuid) for deck_uuid in rows]


class TestGetArchives:
    async def test_not_preserved_archive_returns_offer(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        client = await auth_client_factory(await user_factory())
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat")])

        await archive_studied_deck(client, deck_uuid)
        archives = await get_archives(client)

        [archive_uuid] = await get_archive_uuids_by_source(async_session_maker, deck_uuid)
        assert len(archives) == 1
        assert archives[0]["uuid"] == archive_uuid
        assert archives[0]["title"] == "Animals"
        assert archives[0]["preserved_deck_uuid"] is None

    async def test_preserved_archive_with_live_copy_returns_copy_uuid(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        client = await auth_client_factory(await user_factory())
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat")])
        await archive_studied_deck(client, deck_uuid)
        [archive_uuid] = await get_archive_uuids_by_source(async_session_maker, deck_uuid)

        copy_uuid = await preserve(client, archive_uuid)
        archives = await get_archives(client)

        assert len(archives) == 1
        assert archives[0]["uuid"] == archive_uuid
        assert archives[0]["title"] == "Animals"
        assert archives[0]["preserved_deck_uuid"] == copy_uuid

    async def test_preserved_archive_with_deleted_copy_is_hidden(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        client = await auth_client_factory(await user_factory())
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat")])
        await archive_studied_deck(client, deck_uuid)
        [first_archive_uuid] = await get_archive_uuids_by_source(
            async_session_maker,
            deck_uuid,
        )
        copy_uuid = await preserve(client, first_archive_uuid)

        await archive_studied_deck(client, copy_uuid)
        archives = await get_archives(client)

        [second_archive_uuid] = await get_archive_uuids_by_source(
            async_session_maker,
            copy_uuid,
        )
        assert len(archives) == 1
        assert archives[0]["uuid"] == second_archive_uuid
        assert archives[0]["title"] == "Animals"
        assert archives[0]["preserved_deck_uuid"] is None

    async def test_expired_archive_is_hidden(
        self,
        user_factory: UserFactory,
        auth_client_factory: AuthClientFactory,
        async_session_maker: async_sessionmaker[AsyncSession],
    ):
        client = await auth_client_factory(await user_factory())
        deck_uuid = await create_deck(client, "Animals", [("кот", "cat")])
        await archive_studied_deck(client, deck_uuid)
        [archive_uuid] = await get_archive_uuids_by_source(async_session_maker, deck_uuid)
        now = utcnow()
        async with async_session_maker() as session:
            # ck_deck_archive_lifecycle требует archived_at < expires_at
            await session.execute(
                update(Deck)
                .where(Deck.uuid == UUID(archive_uuid))
                .values(
                    archived_at=now - timedelta(days=31),
                    expires_at=now - timedelta(minutes=1),
                )
            )
            await session.commit()

        archives = await get_archives(client)

        assert archives == []
