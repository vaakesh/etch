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

    source_lang: CardLang = "ru"
    target_lang: CardLang = "en"


class CardUpdate(BaseModel):
    front_text: CardText | None = None
    back_text: CardText | None = None

    source_lang: CardLang | None = None
    target_lang: CardLang | None = None


class CardDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID

    front_text: CardText
    back_text: CardText

    source_lang: CardLang
    target_lang: CardLang