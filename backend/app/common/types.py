from typing import Annotated

from app.common.limits import MAX_DECK_SIZE, MAX_SESSION_SIZE
from fastapi import Query
from pydantic import AfterValidator, Field, StringConstraints

type CardText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=False,
        min_length=1,
        max_length=255,
    ),
]

type CardLang = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=2,
        max_length=3,
        pattern=r"^[A-Za-z]{2,3}$",
    ),
]

type Counter = Annotated[int, Field(ge=0)]
type Percent = Annotated[int, Field(ge=0, le=100)]
type PositiveInt = Annotated[int, Field(ge=1)]
type Seconds = Annotated[int, Field(ge=0)]

type DeckSize = Annotated[int, Field(ge=0, le=MAX_DECK_SIZE)]
type DeckPosition = Annotated[int, Field(ge=1, le=MAX_DECK_SIZE)]
type SessionSize = Annotated[int, Field(ge=1, le=MAX_SESSION_SIZE)]

type DeckTitle = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=50,
        pattern=r"^[^\t\n\r\v\f\x85\u2028\u2029]*$",
    ),
]

def _empty_description_to_none(value: str | None) -> str | None:
    return None if value == "" else value


type DeckDescription = Annotated[
    Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            max_length=3000,
        ),
    ]
    | None,
    AfterValidator(_empty_description_to_none),
]

type Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=False,
        min_length=3,
        max_length=18,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
]

type Password = Annotated[
    str,
    StringConstraints(
        min_length=8,
        max_length=128,
        pattern=r"^\S+$",
    ),
]

type NormalizedSearch = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=1,
        max_length=50,
    ),
]

type SearchQuery = Annotated[
    NormalizedSearch | None,
    Query(alias="q"),
]

type PageLimit = Annotated[int, Query(ge=1, le=100)]
type PaginationCursor = Annotated[str | None, Query(max_length=512)]
