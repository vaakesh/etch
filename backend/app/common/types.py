from typing import Annotated

from fastapi import Query
from pydantic import Field, StringConstraints

type CardText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
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
    ),
]

type Counter = Annotated[int, Field(ge=0)]
type Percent = Annotated[int, Field(ge=0, le=100)]
type PositiveInt = Annotated[int, Field(ge=1)]
type Seconds = Annotated[int, Field(ge=0)]

type DeckTitle = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=50,
    ),
]

type DeckDescription = (
    Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            max_length=3000,
        ),
    ]
    | None
)

type Username = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=3,
        max_length=18,
        pattern=r"^\S+$",
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
