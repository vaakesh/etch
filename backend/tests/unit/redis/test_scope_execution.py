from types import SimpleNamespace
from unittest.mock import call

import orjson
import pytest
from redis.exceptions import ConnectionError

from app.decks.utils import make_user_deck_identity
from app.redis.invalidation import (
    BumpGeneration,
    CacheInvalidator,
    DelKey,
    EntityIdentity,
    Scope,
    dump_scopes,
    load_scopes,
    scopes,
)
from tests.unit.redis.cases import CARD_UUID, DECK_UUID, USER_UUID


class TestDumpScopes:
    def test_serializes_scopes_and_all_supported_argument_types(self):
        identity = make_user_deck_identity(42, 200)
        entity = EntityIdentity(42, USER_UUID)

        payload = dump_scopes(
            scopes.cards(100, 101),
            scopes.deck_ids_by_uuids(DECK_UUID),
            scopes.user_decks(identity),
            scopes.users_removed(entity),
        )

        expected = {"scopes": [
            {"name": "cards", "args": [100, 101]},
            {"name": "deck_ids_by_uuids", "args": [str(DECK_UUID)]},
            {"name": "user_decks", "args": [[42, 200]]},
            {"name": "users_removed", "args": [{"id": 42, "uuid": str(USER_UUID)}]},
        ]}
        assert payload == expected
        assert orjson.loads(orjson.dumps(payload)) == expected

    def test_omits_scopes_without_arguments(self):
        payload = dump_scopes(scopes.cards(), scopes.library(42), scopes.decks())

        assert payload == {"scopes": [{"name": "library", "args": [42]}]}

    def test_serializes_only_empty_scopes_as_empty_payload(self):
        payload = dump_scopes(scopes.cards(), scopes.library())

        assert payload == {"scopes": []}

    def test_serializes_empty_calls(self):
        payload = dump_scopes()

        assert payload == {"scopes": []}


class TestScopeFn:
    def test_captures_entity_identity_before_entity_changes(self):
        entity = SimpleNamespace(id=42, uuid=USER_UUID)

        group = scopes.users_removed(entity)
        entity.id = 43
        entity.uuid = DECK_UUID

        assert group.args == (EntityIdentity(42, USER_UUID),)
        assert dump_scopes(group) == {"scopes": [
            {"name": "users_removed", "args": [{"id": 42, "uuid": str(USER_UUID)}]},
        ]}
        assert list(group) == [
            DelKey("user:42"), DelKey(f"user:id-by-uuid:{USER_UUID}"),
            DelKey("user:42:settings"),
            BumpGeneration("library:42:decks:generation"),
            BumpGeneration("library:42:cards:generation"),
        ]

    def test_captures_user_deck_identity_before_input_changes(self):
        identity = [42, 200]

        group = scopes.user_decks(identity)
        identity[:] = [43, 201]

        assert group.args == (make_user_deck_identity(42, 200),)
        assert list(group) == [DelKey("deck:user-deck:42:200")]

    def test_rejects_keyword_arguments(self):
        with pytest.raises(TypeError, match="positional args only"):
            scopes.cards(card_ids=[100])


class TestLoadScopes:
    @pytest.mark.parametrize(("group", "expected"), [
        (scopes.users(42), [DelKey("user:42")]),
        (scopes.users_settings(42), [DelKey("user:42:settings")]),
        (scopes.user_ids_by_uuids(USER_UUID), [DelKey(f"user:id-by-uuid:{USER_UUID}")]),
        (scopes.user_decks(make_user_deck_identity(42, 200)), [
            DelKey("deck:user-deck:42:200"),
        ]),
        (scopes.decks(200), [DelKey("deck:200")]),
        (scopes.deck_cards(200), [DelKey("deck:200:card-ids")]),
        (scopes.deck_ids_by_uuids(DECK_UUID), [DelKey(f"deck:id-by-uuid:{DECK_UUID}")]),
        (scopes.cards(100), [DelKey("card:100")]),
        (scopes.card_ids_by_uuids(CARD_UUID), [DelKey(f"card:id-by-uuid:{CARD_UUID}")]),
        (scopes.library_deck_pages(42), [BumpGeneration("library:42:decks:generation")]),
        (scopes.library_card_pages(42), [BumpGeneration("library:42:cards:generation")]),
        (scopes.library(42), [
            BumpGeneration("library:42:decks:generation"),
            BumpGeneration("library:42:cards:generation"),
        ]),
        (scopes.deck_with_cards(200), [DelKey("deck:200"), DelKey("deck:200:card-ids")]),
        (scopes.users_removed(EntityIdentity(42, USER_UUID)), [
            DelKey("user:42"), DelKey(f"user:id-by-uuid:{USER_UUID}"), DelKey("user:42:settings"),
            BumpGeneration("library:42:decks:generation"),
            BumpGeneration("library:42:cards:generation"),
        ]),
        (scopes.decks_removed(EntityIdentity(200, DECK_UUID)), [
            DelKey("deck:200"), DelKey("deck:200:card-ids"), DelKey(f"deck:id-by-uuid:{DECK_UUID}"),
        ]),
        (scopes.cards_removed(EntityIdentity(100, CARD_UUID)), [
            DelKey("card:100"), DelKey(f"card:id-by-uuid:{CARD_UUID}"),
        ]),
    ])
    def test_restores_scope_and_operations_after_json_round_trip(self, group, expected):
        payload = orjson.loads(orjson.dumps(dump_scopes(group)))

        restored = load_scopes(payload)

        assert len(restored) == 1
        assert isinstance(restored[0], Scope)
        assert restored[0] == group
        assert list(restored[0]) == expected

    @pytest.mark.parametrize("name", ["unknown", "__dict__", "__class__", "__init__"])
    def test_rejects_unknown_or_non_scope_name(self, name):
        with pytest.raises(ValueError, match="Unknown cache scope"):
            load_scopes({"scopes": [
                {"name": "cards", "args": [100]},
                {"name": name, "args": []},
            ]})

    def test_returns_empty_list_for_empty_payload(self):
        restored = load_scopes({"scopes": []})

        assert restored == []


class TestCacheInvalidatorInvalidateScopes:
    async def test_executes_unpacked_loaded_scopes_and_deduplicates_operations(
        self, redis_client, redis_pipeline,
    ):
        invalidator = CacheInvalidator(redis_client)
        loaded = load_scopes({"scopes": [
            {"name": "cards", "args": [100]},
            {"name": "library_card_pages", "args": [42, 42]},
        ]})

        await invalidator.invalidate(*loaded, scopes.cards(100))

        assert redis_pipeline.method_calls == [
            call.unlink("card:100"),
            call.incr("library:42:cards:generation"),
            call.execute(),
        ]

    async def test_replays_same_loaded_scopes_after_redis_failure(self, redis_client, redis_pipeline):
        invalidator = CacheInvalidator(redis_client)
        loaded = load_scopes({"scopes": [
            {"name": "cards", "args": [100]},
            {"name": "library_card_pages", "args": [42]},
        ]})
        redis_pipeline.execute.side_effect = ConnectionError("Redis unavailable")

        with pytest.raises(ConnectionError):
            await invalidator.invalidate(*loaded)
        redis_pipeline.execute.side_effect = None
        await invalidator.invalidate(*loaded)

        assert redis_pipeline.unlink.call_args_list == [call("card:100"), call("card:100")]
        assert redis_pipeline.incr.call_args_list == [
            call("library:42:cards:generation"), call("library:42:cards:generation"),
        ]

    @pytest.mark.parametrize("payload", [
        {"scopes": []},
        {"scopes": [{"name": "cards", "args": []}]},
    ])
    async def test_empty_loaded_scopes_do_not_contact_redis(self, redis_client, payload):
        invalidator = CacheInvalidator(redis_client)

        await invalidator.invalidate(*load_scopes(payload))

        redis_client.pipeline.assert_not_called()
