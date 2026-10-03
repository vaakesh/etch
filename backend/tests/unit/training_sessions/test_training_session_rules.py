from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from app.errors import RequestValueError
from app.training_sessions.schemas import (
    InternalTrainingSession, InternalTrainingSessionItem, SubmittedAnswerRequest,
    TrainingSessionResponse,
)
from tests.unit.factories import make_training_session, make_training_session_item

START = datetime(2020, 1, 1, tzinfo=UTC)
END = datetime(2020, 1, 2, tzinfo=UTC)
UUID7 = UUID("0198ad01-b200-7000-8000-000000000400")


class TestTrainingSessionState:
    @pytest.mark.parametrize("values, field", [
        ({"answered_count": 11}, "answered_count"),
        ({"correct_count": 1}, "answered_count"),
        ({"answer_side": "front"}, "answer_side"),
        ({"finished_at": END}, "finished_at"),
        ({"status": "completed"}, "finished_at"),
        ({"status": "completed", "finished_at": END}, "answered_count"),
        ({"status": "abandoned", "finished_at": datetime(2019, 1, 1, tzinfo=UTC)}, "finished_at"),
        ({"status": "abandoned", "finished_at": datetime(2020, 1, 2)}, "finished_at"),
        ({"activity_tracker_uuid": UUID7}, "activity_tracker_uuid"),
        ({"activity_last_seen_at": END}, "activity_tracker_uuid"),
        ({"activity_tracker_uuid": UUID7, "activity_last_seen_at": datetime(2019, 1, 1, tzinfo=UTC)}, "activity_last_seen_at"),
        ({"status": "abandoned", "finished_at": END, "activity_tracker_uuid": UUID7, "activity_last_seen_at": END}, "activity_tracker_uuid"),
    ])
    def test_rejects_inconsistent_state(self, values, field):
        session = make_training_session(started_at=START, **values)

        with pytest.raises(RequestValueError) as error:
            InternalTrainingSession.model_validate(session)

        assert error.value.failed_field == field

    @pytest.mark.parametrize("values, field", [
        ({"user_id": 0}, "user_id"), ({"deck_id": 0}, "deck_id"),
        ({"requested_count": 501}, "requested_count"), ({"requested_count": 0}, "requested_count"),
        ({"answered_count": -1}, "answered_count"), ({"correct_count": -1}, "correct_count"),
        ({"wrong_count": -1}, "wrong_count"), ({"active_study_time_ms": -1}, "active_study_time_ms"),
        ({"uuid": UUID(int=1, version=4)}, "uuid"),
        ({"activity_tracker_uuid": UUID(int=1, version=4)}, "activity_tracker_uuid"),
    ])
    def test_rejects_invalid_field(self, values, field):
        session = make_training_session(started_at=START, **values)

        with pytest.raises(ValidationError) as error:
            InternalTrainingSession.model_validate(session)

        assert error.value.errors()[0]["loc"] == (field,)

    @pytest.mark.parametrize("status, count, finished", [
        ("in_progress", 0, None), ("completed", 10, START), ("abandoned", 0, END),
    ])
    def test_accepts_valid_state_without_deck(self, status, count, finished):
        session = make_training_session(
            started_at=START, status=status, finished_at=finished,
            answered_count=count, correct_count=count, wrong_count=0, deck_id=None,
        )
        session.deck_uuid = session.deck_title = None

        result = InternalTrainingSession.model_validate(session)
        response = TypeAdapter(TrainingSessionResponse).dump_python(result)

        assert result.deck_id is None
        assert response["deck_uuid"] is None
        assert response["deck_title"] is None
        assert response["answered_count"] == count
        assert "actual_count" not in response
        assert "activity_tracker_uuid" not in response
        assert "id" not in response


class TestTrainingSessionItemState:
    @pytest.mark.parametrize("values, field", [
        ({"is_correct": True}, "is_correct"),
        ({"answered_at": END}, "answered_at"),
        ({"user_typed_text": "answer"}, "user_typed_text"),
        ({"is_answered": True, "is_correct": True, "answered_at": END}, "is_correct"),
        ({"is_answered": True, "is_correct": False}, "answered_at"),
    ])
    def test_rejects_inconsistent_answer(self, values, field):
        item = make_training_session_item(**values)

        with pytest.raises(RequestValueError) as error:
            InternalTrainingSessionItem.model_validate(item)

        assert error.value.failed_field == field

    @pytest.mark.parametrize("values, field", [
        ({"id": 0}, "id"), ({"training_session_id": -1}, "training_session_id"),
        ({"original_card_id": 0}, "original_card_id"),
        ({"uuid": UUID(int=1, version=4)}, "uuid"),
        ({"sequence_number": 0}, "sequence_number"), ({"sequence_number": 501}, "sequence_number"),
        ({"is_answered": 1}, "is_answered"), ({"is_correct": "false"}, "is_correct"),
        ({"prompt_text": " "}, "prompt_text"), ({"answer_text": "x" * 256}, "answer_text"),
        ({"prompt_lang": "english"}, "prompt_lang"), ({"answer_lang": "1a"}, "answer_lang"),
    ])
    def test_rejects_invalid_field(self, values, field):
        item = make_training_session_item(**values)

        with pytest.raises(ValidationError) as error:
            InternalTrainingSessionItem.model_validate(item)

        assert error.value.errors()[0]["loc"] == (field,)

    def test_accepts_skip_after_original_card_deletion(self):
        item = make_training_session_item(
            original_card_id=None, is_answered=True, is_correct=False, answered_at=END,
        )

        result = InternalTrainingSessionItem.model_validate(item)

        assert result.original_card_id is None
        assert result.user_typed_text is None
        assert result.is_correct is False


class TestSubmittedAnswer:
    def test_trims_edges_and_preserves_case_and_internal_whitespace(self):
        result = SubmittedAnswerRequest(action="answer", answer=" \tHello\n  World 🙂\u2003")

        assert result.answer == "Hello\n  World 🙂"
