from collections.abc import Awaitable
from dataclasses import dataclass, field
from itertools import count
from typing import Protocol, TypedDict, Unpack

from httpx import AsyncClient
import pytest
import pytest_asyncio
from tests.integration.conftest import ClientFactory

# Для двух отдельных сеансов ОДНОГО пользователя:
# account = await user_factory()
# phone_client = await authenticated_client_factory(account)
# laptop_client = await authenticated_client_factory(account)
#
# Для гостевого клиента:
# guest_client = await client_factory()
#
# Для нового payload без записи в БД:
# payload = user_payload_factory(username="valid_user")
#
# Для повторной регистрации с одинаковым email:
# await user_factory(email="taken@example.com")
# payload = user_payload_factory(email="taken@example.com")
# guest_client = await client_factory()
# response = await guest_client.post("/users/create", json=payload)
#
# Нет необходимости создавать отдельную фикстуру на каждого alice/bob/admin:
# нужные различия передаются аргументами фабрики внутри теста.

class UserOverrides(TypedDict, total=False):
    username: str
    email: str
    password: str

class UserPayload(TypedDict):
    username: str
    email: str
    password: str

@dataclass(frozen=True)
class CreatedSettings:
    locale: str
    theme: str
    show_previews_for_long: bool

@dataclass(frozen=True)
class CreatedUser:
    uuid: str
    username: str
    email: str
    created_at: str
    updated_at: str
    password: str = field(repr=False)
    settings: CreatedSettings

class UserPayloadFactory(Protocol):
    def __call__(
        self,
        **overrides: Unpack[UserOverrides],
    ) -> UserPayload:
        ...

@pytest.fixture(scope="function")
def user_payload_factory() -> UserPayloadFactory:
    sequence = count(start=1, step=1)

    def make_payload(
        **overrides: Unpack[UserOverrides],
    ) -> UserPayload:
        number = next(sequence)
        payload = UserPayload(
            username=f"user_{number}",
            email=f"user_{number}@example.com",
            password="Test-password-123",
        )
        payload.update(overrides)
        return payload

    return make_payload

class UserFactory(Protocol):
    def __call__(
        self,
        **overrides: Unpack[UserOverrides],
    ) -> Awaitable[CreatedUser]:
        ...

@pytest.fixture(scope="function")
def user_factory(
    client_factory: ClientFactory, 
    user_payload_factory: UserPayloadFactory,
) -> UserFactory:
    async def create_user(
            **overrides: Unpack[UserOverrides],
        ) -> CreatedUser:
        payload = user_payload_factory(**overrides)
        registration_client = await client_factory()
        response = await registration_client.post(
            "/users/create", 
            json=payload,
        )
        assert response.status_code == 201
        data = response.json()
        return CreatedUser(
            uuid=data["uuid"],
            username=data["username"],
            email=data["email"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            password=payload["password"],
            settings=CreatedSettings(
                locale="ru-RU",
                theme="system",
                show_previews_for_long=True,
            )
        )
    return create_user

class AuthClientFactory(Protocol):
    def __call__(
        self,
        user: CreatedUser,
    ) -> Awaitable[AsyncClient]:
        ...

@pytest.fixture(scope="function")
def auth_client_factory(
    client_factory: ClientFactory,
) -> AuthClientFactory:
    async def make_authenticated_client(
        user: CreatedUser
    ) -> AsyncClient:
        client = await client_factory()
        response = await client.post(
            url="/auth/login",
            json={
                "username": user.username,
                "password": user.password,
            }
        )
        assert response.status_code == 204
        return client
    return make_authenticated_client

@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def user(user_factory: UserFactory) -> CreatedUser:
    return await user_factory()

@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def auth_client(
    user: CreatedUser,
    auth_client_factory: AuthClientFactory,
) -> AsyncClient:
    return await auth_client_factory(user)