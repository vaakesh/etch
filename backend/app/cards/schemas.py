from uuid import UUID

from pydantic import BaseModel, ConfigDict, PastDatetime

from app.cards.models import Card
from app.cards.types import CardLang, CardText



class InternalCard(BaseModel):
    id: int
    uuid: UUID
    front_text: CardText
    back_text: CardText
    front_lang: CardLang
    back_lang: CardLang
    created_at: PastDatetime
    updated_at: PastDatetime

    @classmethod
    def from_entity(cls, card: Card) -> InternalCard:
        return cls(
            id=card.id,
            uuid=card.uuid,
            front_text=card.front_text,
            back_text=card.back_text,
            front_lang=card.front_lang,
            back_lang=card.back_lang,
            created_at=card.created_at,
            updated_at=card.updated_at,
        )

class CreateCardRequest(BaseModel):
    front_text: CardText
    back_text: CardText

    front_lang: CardLang = "ru"
    back_lang: CardLang = "en"

class UpdateCardRequest(BaseModel):
    front_text: CardText | None = None
    back_text: CardText | None = None

    front_lang: CardLang | None = None
    back_lang: CardLang | None = None

class CardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID

    front_text: CardText
    back_text: CardText

    front_lang: CardLang
    back_lang: CardLang

    updated_at: PastDatetime