from typing import Annotated, Literal
from zoneinfo import available_timezones

from pydantic import AfterValidator, EmailStr, Field, StringConstraints

from app.errors import RequestValueError

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
    Field(
        description=(
            "Locale with a 2–3 letter language and a 2-letter region, e.g. ru-RU or fil-PH"
        )
    ),
]

AVAILABLE_TIMEZONES = frozenset(available_timezones())
DEFAULT_TIMEZONE = "UTC"


def _validate_timezone(value: str) -> str:
    # RequestValueError, а не ValueError: ValueError попадает в ctx ответа 422,
    # а обработчик ошибок не умеет его сериализовать
    if value not in AVAILABLE_TIMEZONES:
        raise RequestValueError(
            message="Unknown IANA timezone",
            failed_field="timezone",
        )
    return value


type Timezone = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64),
    AfterValidator(_validate_timezone),
    Field(description="IANA timezone, e.g. Europe/Moscow or UTC"),
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
