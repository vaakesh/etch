from typing import Annotated

from pydantic import StringConstraints


type CardText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=1,
        max_length=255,
    )
]

type CardLang = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=2,
        max_length=3,
    )
]