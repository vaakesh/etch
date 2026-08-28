from unittest.mock import create_autospec

import pytest
from fastapi import FastAPI

from app.auth.deps import get_current_user
from app.bff.deps import get_bff_service
from app.bff.service import BffService


@pytest.fixture
def bff_service():
    return create_autospec(BffService, instance=True)


@pytest.fixture(autouse=True)
def override_bff_route_dependencies(
    app: FastAPI,
    current_user,
    bff_service,
):
    async def provide_current_user():
        return current_user

    async def provide_bff_service():
        return bff_service

    overrides = {
        get_current_user: provide_current_user,
        get_bff_service: provide_bff_service,
    }
    app.dependency_overrides.update(overrides)

    yield

    for dependency in overrides:
        app.dependency_overrides.pop(dependency, None)
