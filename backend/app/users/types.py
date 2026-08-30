from typing import Annotated, Literal

from pydantic import EmailStr, Field, StringConstraints

type Theme = Annotated[
    Literal["light", "dark", "system"],
    Field(description="UI theme"),
]

type Locale = Annotated[
    Literal[
        "ru-RU",
        "en-US",
    ],
    Field(description="User locale in BCP 47 format"),
]

type NormalizedEmail = Annotated[
    EmailStr,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
    ),
]
