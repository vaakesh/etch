from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

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

class CardCreate(BaseModel):

    front_text: CardText
    back_text: CardText

    front_lang: CardLang = "ru"
    back_lang: CardLang = "en"


class CardUpdate(BaseModel):
    front_text: CardText | None = None
    back_text: CardText | None = None

    front_lang: CardLang | None = None
    back_lang: CardLang | None = None


class CardDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID

    front_text: CardText
    back_text: CardText

    front_lang: CardLang
    back_lang: CardLang