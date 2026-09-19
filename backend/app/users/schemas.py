from uuid import UUID

from app.common.types import Counter, Password, Username
from app.users.types import Locale, NormalizedEmail, Theme
from pydantic import BaseModel, ConfigDict, PastDatetime

# internal models
class InternalUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: UUID
    username: Username
    email: NormalizedEmail
    hashed_password: str
    created_at: PastDatetime
    updated_at: PastDatetime

class InternalUserSettings(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    locale: Locale
    theme: Theme
    show_previews_for_long: bool
    created_at: PastDatetime
    updated_at: PastDatetime

class InternalUserWithSettings(InternalUser):
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

    uuid: UUID
    username: Username
    created_at: PastDatetime
    deck_count: Counter
    total_saves_count: Counter

class UserSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    locale: Locale
    theme: Theme
    show_previews_for_long: bool

class PrivateUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    username: Username
    email: NormalizedEmail
    created_at: PastDatetime
    updated_at: PastDatetime
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
    username: Username | None = None
    email: NormalizedEmail | None = None

class UpdateUserSettingsRequest(BaseModel):
    locale: Locale | None = None
    theme: Theme | None = None
    show_previews_for_long: bool | None = None
