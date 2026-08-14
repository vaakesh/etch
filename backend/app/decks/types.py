


from typing import Annotated

from pydantic import StringConstraints


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