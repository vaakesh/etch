from dataclasses import dataclass
import functools
from itertools import batched
import logging
from collections.abc import Callable, Iterable, Iterator
from typing import Any, Mapping, Protocol
from uuid import UUID

import orjson
from redis import RedisError
from redis.asyncio import Redis

from app.decks.utils import make_user_deck_identity
from app.redis.keys import (
    make_card_cache_key,
    make_card_uuid_cache_key,
    make_deck_cache_key,
    make_deck_cards_cache_key,
    make_deck_uuid_cache_key,
    make_library_cards_page_generation_cache_key,
    make_library_deck_page_generation_cache_key,
    make_user_cache_key,
    make_user_deck_cache_key,
    make_user_settings_cache_key,
    make_user_uuid_cache_key,
)
from app.redis.schemas import UserDeckIdentity
from app.tracing import traced

logger = logging.getLogger(__name__)
UNLINK_BATCH_SIZE = 500

@dataclass(frozen=True, slots=True)
class DelKey:
    key: str

@dataclass(frozen=True, slots=True)
class BumpGeneration:
    # Счётчик живёт без TTL: после истечения INCR снова выдал бы номер,
    # под которым ещё лежит старая страница.
    key: str

type CacheOp = DelKey | BumpGeneration


class _Entity(Protocol):
    id: int
    uuid: UUID


@dataclass(frozen=True, slots=True)
class EntityIdentity:
    id: int
    uuid: UUID


@dataclass(frozen=True, slots=True)
class ArgCodec[T]:
    """
    как один аргумент скоупа превращается в json и обратно
    normalize - приводит аргумент к храниомому виду в момент вызова скоупа
    например, ORM -> EntityIdentity(id, uuid)
    """
    encode: Callable[[T], Any]
    decode: Callable[[Any], T]
    normalize: Callable[[Any], T] = lambda value: value

INT = ArgCodec[int](encode=int, decode=int)
UUID_ARG = ArgCodec[UUID](encode=str, decode=UUID)
USER_DECK = ArgCodec[UserDeckIdentity](
    encode=list,
    decode=lambda value: make_user_deck_identity(*value),
    normalize=lambda value: make_user_deck_identity(*value),
)
ENTITY = ArgCodec[EntityIdentity](
    encode=lambda e: {"id": e.id, "uuid": str(e.uuid)},
    decode=lambda v: EntityIdentity(id=int(v["id"]), uuid=UUID(v["uuid"])),
    normalize=lambda e: EntityIdentity(id=e.id, uuid=e.uuid),
)

class ScopeFn[**P]:
    """Функция-скоуп вместе со своим кодеком аргументов.
 
    Вызов не генерирует операции, а возвращает ленивый Scope (функция + аргументы).
    Имя берётся из атрибута класса scopes (__set_name__), по нему же
    load_scopes находит скоуп обратно через vars(scopes).
    """
 
    def __init__(self, fn: Callable[P, Iterator[CacheOp]], codec: ArgCodec[Any]) -> None:
        self.fn = fn
        self.codec = codec
        self.name = fn.__name__
        functools.update_wrapper(self, fn)
 
    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name
 
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> "Scope":
        if kwargs:
            raise TypeError("cache scopes accept positional args only")
        return Scope(fn=self, args=tuple(map(self.codec.normalize, args)))
 
    def __repr__(self) -> str:
        return f"<scope {self.name}>"


def scope[**P](codec: ArgCodec) -> Callable[[Callable[P, Iterator[CacheOp]]], ScopeFn[P]]:
    def decorator(fn: Callable[P, Iterator[CacheOp]]) -> ScopeFn[P]:
        return ScopeFn(fn, codec)
    return decorator

@dataclass(frozen=True, slots=True)
class Scope:
    """Запомненный вызов скоупа. Итерируется в CacheOp."""
 
    fn: ScopeFn[...]
    args: tuple[Any, ...]
 
    @property
    def name(self) -> str:
        return self.fn.name
 
    def __iter__(self) -> Iterator[CacheOp]:
        return self.fn.fn(*self.args)


class scopes:
    """
    класс, чтобы в удобном формате совершать инвалидацию
    """

    # users

    @scope(INT)
    def users(*user_ids: int) -> Iterator[CacheOp]:
        for user_id in user_ids:
            yield DelKey(
                key=make_user_cache_key(
                    user_id=user_id,
                ),
            )

    @scope(UUID_ARG)
    def user_ids_by_uuids(*user_uuids: UUID) -> Iterator[CacheOp]:
        for user_uuid in user_uuids:
            yield DelKey(
                key=make_user_uuid_cache_key(
                    user_uuid=user_uuid,
                ),
            )
 
    @scope(INT)
    def users_settings(*user_ids: int) -> Iterator[CacheOp]:
        for user_id in user_ids:
            yield DelKey(
                key=make_user_settings_cache_key(
                    user_id=user_id,
                ),
            )
 
    @scope(USER_DECK)
    def user_decks(*identities: UserDeckIdentity) -> Iterator[CacheOp]:
        for identity in identities:
            yield DelKey(
                key=make_user_deck_cache_key(
                    identity=identity
                ),
            )

    # library pages (generation)

    @scope(INT)
    def library_deck_pages(*user_ids: int) -> Iterator[CacheOp]:
        for user_id in user_ids:
            yield BumpGeneration(
                key=make_library_deck_page_generation_cache_key(user_id=user_id),
            )
 
    @scope(INT)
    def library_card_pages(*user_ids: int) -> Iterator[CacheOp]:
        for user_id in user_ids:
            yield BumpGeneration(
                key=make_library_cards_page_generation_cache_key(user_id=user_id),
            )

    # decks

    @scope(INT)
    def decks(*deck_ids: int) -> Iterator[CacheOp]:
        for deck_id in deck_ids:
            yield DelKey(make_deck_cache_key(deck_id=deck_id))
 
    @scope(UUID_ARG)
    def deck_ids_by_uuids(*deck_uuids: UUID) -> Iterator[CacheOp]:
        for deck_uuid in deck_uuids:
            yield DelKey(make_deck_uuid_cache_key(deck_uuid))
 
    @scope(INT)
    def deck_cards(*deck_ids: int) -> Iterator[CacheOp]:
        for deck_id in deck_ids:
            yield DelKey(make_deck_cards_cache_key(deck_id=deck_id))


    # cards

    @scope(INT)
    def cards(*card_ids: int) -> Iterator[CacheOp]:
        for card_id in card_ids:
            yield DelKey(make_card_cache_key(card_id=card_id))
 
    @scope(UUID_ARG)
    def card_ids_by_uuids(*card_uuids: UUID) -> Iterator[CacheOp]:
        for card_uuid in card_uuids:
            yield DelKey(make_card_uuid_cache_key(card_uuid))


    # combined
    @scope(INT)
    def library(*user_ids: int) -> Iterator[CacheOp]:
        """both library deck and card pages"""
        yield from scopes.library_deck_pages(*user_ids)
        yield from scopes.library_card_pages(*user_ids)
 
    @scope(INT)
    def deck_with_cards(*deck_ids: int) -> Iterator[CacheOp]:
        """decks and its cards"""
        yield from scopes.decks(*deck_ids)
        yield from scopes.deck_cards(*deck_ids)

    # cases
    @scope(ENTITY)
    def users_removed(*entities: _Entity) -> Iterator[CacheOp]:
        user_ids = [e.id for e in entities]
        user_uuids = [e.uuid for e in entities]
        yield from scopes.users(*user_ids)
        yield from scopes.user_ids_by_uuids(*user_uuids)
        yield from scopes.users_settings(*user_ids)
        yield from scopes.library(*user_ids)

    @scope(ENTITY)
    def decks_removed(*entities: _Entity) -> Iterator[CacheOp]:
        deck_ids = [e.id for e in entities]
        deck_uuids = [e.uuid for e in entities]
        yield from scopes.deck_with_cards(*deck_ids)
        yield from scopes.deck_ids_by_uuids(*deck_uuids)

    @scope(ENTITY)
    def cards_removed(*entities: _Entity) -> Iterator[CacheOp]:
        card_ids = [e.id for e in entities]
        card_uuids = [e.uuid for e in entities]
        yield from scopes.cards(*card_ids)
        yield from scopes.card_ids_by_uuids(*card_uuids)

def dump_scopes(*items: Scope) -> dict[str, Any]:
    """Scope -> JSON-совместимый dict (готов для JSONB)."""
    return {
        "scopes": [
            {
                "name": item.name,
                "args": [item.fn.codec.encode(a) for a in item.args],
            }
            for item in items
            if item.args
        ],
    }

def load_scopes(payload: Mapping[str, Any]) -> list[Scope]:
    """dict из JSONB -> Scope для invalidate(*load_scopes(payload))."""
 
    result: list[Scope] = []
    for item in payload["scopes"]:
        name = item["name"]
        fn = vars(scopes).get(name)
        if not isinstance(fn, ScopeFn):
            raise ValueError(f"Unknown cache scope: {name}")
        result.append(Scope(fn=fn, args=tuple(fn.codec.decode(v) for v in item["args"])))
    return result


class CacheInvalidator:
    def __init__(self, redis: Redis, *, raise_errors: bool = False):
        self.redis = redis
        self.raise_errors = raise_errors

    @traced("redis.cache.invalidate")
    async def invalidate(
        self,
        *groups: Iterable[CacheOp],
    ) -> None:
        # ordered unique list of operations
        ops = list(dict.fromkeys(op for group in groups for op in group))
        if not ops:
            return

        del_keys: list[str] = []
        generations: list[BumpGeneration] = []
        for op in ops:
            match op:
                # key - это нулевой аргумент op, соответственно key=op.key, это не вызов
                # DelKey.__match_args__ определяет порядок аргументов
                case DelKey(key):
                    del_keys.append(key)
                case BumpGeneration():
                    generations.append(op)

        try:
            pipe = self.redis.pipeline(transaction=False)

            # чанками, чтобы другие операции долго не ждали
            for chunk in batched(del_keys, UNLINK_BATCH_SIZE):
                pipe.unlink(*chunk)

            for gen in generations:
                pipe.incr(gen.key)

            await pipe.execute()

        except RedisError:
            logger.warning(
                "Redis cache invalidation failed",
                extra={"cache_operation": f"INVALIDATE {len(ops)} ops"},
                exc_info=True,
            )
            if self.raise_errors:
                raise
