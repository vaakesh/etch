from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.training_sessions.schemas import InternalTrainingSession
from tests.unit.factories import make_training_session


class TestTrainingSessionId:
    @pytest.mark.parametrize("value", [0, -1])
    def test_rejects_nonpositive_id(self, value):
        session = make_training_session(
            id=value, started_at=datetime(2020, 1, 1, tzinfo=UTC),
        )

        with pytest.raises(ValidationError) as error:
            InternalTrainingSession.model_validate(session)

        assert error.value.errors(include_url=False) == [{
            "type": "greater_than_equal",
            "loc": ("id",),
            "msg": "Input should be greater than or equal to 1",
            "input": value,
            "ctx": {"ge": 1},
        }]

    def test_accepts_smallest_positive_id(self):
        session = make_training_session(
            id=1, started_at=datetime(2020, 1, 1, tzinfo=UTC),
        )

        result = InternalTrainingSession.model_validate(session)

        assert result.id == 1
