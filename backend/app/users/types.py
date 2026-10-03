from typing import Annotated, Literal

from pydantic import EmailStr, Field, StringConstraints

type PasswordHash = Annotated[
    str,
    StringConstraints(min_length=1, max_length=255, pattern=r"^\S+$"),
]

type Theme = Annotated[
    Literal["light", "dark", "system"],
    Field(description="UI theme"),
]

type Locale = Annotated[
    str,
    StringConstraints(min_length=5, max_length=6, pattern=r"^[a-z]{2,3}-[A-Z]{2}$"),
    Field(description="Locale with a 2–3 letter language and a 2-letter region, e.g. ru-RU or fil-PH"),
]

type NormalizedEmail = Annotated[
    EmailStr,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=1,
        max_length=255,
    ),
]
