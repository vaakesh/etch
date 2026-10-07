from unittest.mock import create_autospec

import pytest

from app.bff.service import BffService


@pytest.fixture
def bff_service():
    return create_autospec(BffService, instance=True)
