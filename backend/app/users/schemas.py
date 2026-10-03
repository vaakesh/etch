from datetime import datetime
from typing import TypedDict

from app.common.types import Counter, Password, PositiveInt, Username
from app.errors import RequestValueError
from app.users.types import Locale, NormalizedEmail, PasswordHash, Theme
from pydantic import UUID7, BaseModel, ConfigDict, PastDatetime, StrictBool, ValidationInfo, field_validator
from pydantic.json_schema import SkipJsonSchema

from app.users.models import User

class UserTimestamps(BaseModel):
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


# internal models
class InternalUser(UserTimestamps):
    model_config = ConfigDict(from_attributes=True)

    id: PositiveInt
    uuid: UUID7
    username: Username
    email: NormalizedEmail
    hashed_password: PasswordHash

class InternalUserSettings(UserTimestamps):
    model_config = ConfigDict(from_attributes=True)

    user_id: PositiveInt
    locale: Locale
    theme: Theme
    show_previews_for_long: StrictBool

class InternalUserWithSettings(UserTimestamps):
    model_config = ConfigDict(from_attributes=True)

    id: PositiveInt
    uuid: UUID7
    username: Username
    email: NormalizedEmail
    hashed_password: PasswordHash
    settings: InternalUserSettings

    @classmethod
    def from_parts(
        cls,
        user: InternalUser, 
        settings: InternalUserSettings,
    ) -> InternalUserWithSettings:
        return cls(
            id=user.id,
            uuid=user.uuid,
            username=user.username,
            email=user.email,
            hashed_password=user.hashed_password,
            created_at=user.created_at,
            updated_at=user.updated_at,
            settings=settings,
        )

# external models
class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID7
    username: Username
    created_at: PastDatetime
    deck_count: Counter
    total_saves_count: Counter

class UserSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    locale: Locale
    theme: Theme
    show_previews_for_long: StrictBool

class PrivateUserResponse(UserTimestamps):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID7
    username: Username
    email: NormalizedEmail
    settings: UserSettingsResponse

    @classmethod
    def from_user_with_settings(
        cls,
        user: InternalUserWithSettings,
    ) -> PrivateUserResponse:
        return PrivateUserResponse(
            uuid=user.uuid,
            username=user.username,
            email=user.email,
            created_at=user.created_at,
            updated_at=user.updated_at,
            settings=UserSettingsResponse(
                locale=user.settings.locale,
                theme=user.settings.theme,
                show_previews_for_long=user.settings.show_previews_for_long,
            )
        )

class CreateUserRequest(BaseModel):
    username: Username
    email: NormalizedEmail
    password: Password

class UpdateUserRequest(BaseModel):
    username: Username | SkipJsonSchema[None] = None
    email: NormalizedEmail | SkipJsonSchema[None] = None

    @field_validator("username", "email")
    @classmethod
    def reject_explicit_null(cls, value, info: ValidationInfo):
        if value is None:
            raise RequestValueError(
                message="Field must not be null",
                failed_field=info.field_name,
            )
        return value

class UserUpdateData(TypedDict, total=False):
    username: Username
    email: NormalizedEmail

class UpdateUserSettingsRequest(BaseModel):
    locale: Locale | SkipJsonSchema[None] = None
    theme: Theme | SkipJsonSchema[None] = None
    show_previews_for_long: StrictBool | SkipJsonSchema[None] = None

    @field_validator("locale", "theme", "show_previews_for_long")
    @classmethod
    def reject_explicit_null(cls, value, info: ValidationInfo):
        if value is None:
            raise RequestValueError(
                message="Field must not be null",
                failed_field=info.field_name,
            )
        return value

class UserSettingsUpdateData(TypedDict, total=False):
    locale: Locale
    theme: Theme
    show_previews_for_long: StrictBool
