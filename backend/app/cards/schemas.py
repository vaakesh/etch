from datetime import datetime
from typing import Any

from app.cards.models import Card
from app.cards.types import CardImportBatch
from app.common.types import CardLang, CardText, Counter, DeckPosition, PositiveInt
from app.errors import RequestValueError
from pydantic import UUID7, BaseModel, ConfigDict, PastDatetime, ValidationInfo, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema


class InternalCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: PositiveInt
    uuid: UUID7
    user_id: PositiveInt
    front_text: CardText
    back_text: CardText
    front_lang: CardLang
    back_lang: CardLang
    created_at: PastDatetime
    updated_at: PastDatetime

    @field_validator("updated_at")
    @classmethod
    def validate_dates_order(cls, value: datetime, info: ValidationInfo) -> datetime:
        created_at = info.data.get("created_at")
        if created_at is not None:
            try:
                valid_order = value >= created_at
            except TypeError:
                raise RequestValueError(
                    message="Dates must have compatible timezone information",
                    failed_field="updated_at",
                ) from None
            if not valid_order:
                raise RequestValueError(
                    message="updated_at must be greater than or equal to created_at",
                    failed_field="updated_at",
                )
        return value

    @classmethod
    def from_entity(cls, card: Card) -> InternalCard:
        return cls(
            id=card.id,
            uuid=card.uuid,
            user_id=card.user_id,
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
    front_text: CardText | SkipJsonSchema[None] = None
    back_text: CardText | SkipJsonSchema[None] = None

    front_lang: CardLang | SkipJsonSchema[None] = None
    back_lang: CardLang | SkipJsonSchema[None] = None

    @model_validator(mode="before")
    @classmethod
    def validate_not_nullable_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for field in ("front_text", "back_text", "front_lang", "back_lang"):
                if field in data and data[field] is None:
                    raise RequestValueError(
                        message=f"{field} value cannot be null",
                        failed_field=field,
                    )
        return data

class CardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID7

    front_text: CardText
    back_text: CardText

    front_lang: CardLang
    back_lang: CardLang

    updated_at: PastDatetime

class LoadCardsRequest(BaseModel):
    cards: CardImportBatch[CreateCardRequest]

class LoadedCardResponse(BaseModel):
    uuid: UUID7
    position: DeckPosition

class LoadCardsResponse(BaseModel):
    imported_count: Counter
    cards: list[LoadedCardResponse]
