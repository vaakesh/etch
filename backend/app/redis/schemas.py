from dataclasses import dataclass
from typing import Hashable

from app.common.schemas import CursorPage

type UserDeckIdentity = tuple[int, int]

@dataclass(slots=True)
class CacheLookupResult[K: Hashable, T]:
    cached: dict[K, T]
    missing: list[K]

@dataclass(frozen=True, slots=True)
class LibraryPageCacheLookup:
    page: CursorPage | None
    generation: int | None
