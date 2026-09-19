from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient

from app.decks.errors import UserDeckNotFoundError
from app.training_sessions.errors import (
    TrainingSessionAlreadyFinishedError,
    TrainingSessionItemNotFoundError,
    TrainingSessionNotFinishedYet,
    TrainingSessionNotFoundError,
)
from app.training_sessions.models import TrainingSessionStatus
from app.training_sessions.schemas import (
    SkipAnswerRequest,
    SubmittedAnswerRequest,
)
from tests.unit.factories import (
    make_training_session,
    make_training_session_item,
)


class TestGetTrainingSession:
    async def test_returns_session_for_authenticated_viewer(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        training_session_service: AsyncMock,
    ):
        training_session_service.get_by_uuid.return_value = training_session

        response = await client.get(f"/training-sessions/{training_session.uuid}")

        expected = {
            "uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
            "deck_uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "deck_title": "Test deck",
            "status": "in_progress",
            "requested_count": 10,
            "actual_count": 3,
            "correct_count": 2,
            "wrong_count": 1,
            "prompt_side": "front",
            "answer_side": "back",
            "started_at": "2026-08-15T16:00:00Z",
            "finished_at": None,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        training_session_service.get_by_uuid.assert_awaited_once_with(
            session_uuid=training_session.uuid,
            current_user_id=current_user.id,
        )

    @pytest.mark.parametrize("optional_current_user", [None], indirect=True)
    async def test_returns_completed_session_for_anonymous_viewer(
        self,
        client: AsyncClient,
        training_session_service: AsyncMock,
    ):
        training_session = make_training_session(
            status=TrainingSessionStatus.COMPLETED,
            finished_at=datetime(2026, 8, 15, 17, 0, tzinfo=UTC),
        )
        training_session_service.get_by_uuid.return_value = training_session

        response = await client.get(f"/training-sessions/{training_session.uuid}")

        expected = {
            "uuid": "dddddddd-dddd-dddd-dddd-dddddddddddd",
            "deck_uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "deck_title": "Test deck",
            "status": "completed",
            "requested_count": 10,
            "actual_count": 3,
            "correct_count": 2,
            "wrong_count": 1,
            "prompt_side": "front",
            "answer_side": "back",
            "started_at": "2026-08-15T16:00:00Z",
            "finished_at": "2026-08-15T17:00:00Z",
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        training_session_service.get_by_uuid.assert_awaited_once_with(
            session_uuid=training_session.uuid,
            current_user_id=None,
        )

    async def test_returns_404_when_session_not_found(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        training_session_service: AsyncMock,
    ):
        training_session_service.get_by_uuid.side_effect = (
            TrainingSessionNotFoundError()
        )

        response = await client.get(f"/training-sessions/{training_session.uuid}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["message"] == "Training session not found"

        training_session_service.get_by_uuid.assert_awaited_once_with(
            session_uuid=training_session.uuid,
            current_user_id=current_user.id,
        )

    async def test_rejects_invalid_session_uuid(
        self,
        client: AsyncClient,
        training_session_service: AsyncMock,
    ):
        response = await client.get("/training-sessions/not-a-uuid")

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "session_uuid"],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        training_session_service.get_by_uuid.assert_not_awaited()


class TestGetTrainingSessionHistory:
    async def test_returns_session_history_with_default_filters(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        training_session_service: AsyncMock,
    ):
        first_item = make_training_session_item()
        second_item = make_training_session_item(
            uuid=UUID("11111111-1111-1111-1111-111111111111"),
            sequence_number=2,
            original_card_uuid=UUID("22222222-2222-2222-2222-222222222222"),
            user_typed_text="bye",
            prompt_text="пока",
            answer_text="bye",
            is_answered=True,
            is_correct=False,
            answered_at=datetime(2026, 8, 15, 16, 5, tzinfo=UTC),
        )
        training_session_service.get_session_history.return_value = [
            first_item,
            second_item,
        ]

        response = await client.get(
            f"/training-sessions/{training_session.uuid}/history"
        )

        expected = [
            {
                "item_uuid": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
                "sequence_number": 1,
                "prompt_text": "привет",
                "answer_text": "hello",
                "prompt_lang": "ru",
                "answer_lang": "en",
                "user_typed_text": None,
                "is_answered": False,
                "is_correct": None,
            },
            {
                "item_uuid": "11111111-1111-1111-1111-111111111111",
                "sequence_number": 2,
                "prompt_text": "пока",
                "answer_text": "bye",
                "prompt_lang": "ru",
                "answer_lang": "en",
                "user_typed_text": "bye",
                "is_answered": True,
                "is_correct": False,
            },
        ]

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        training_session_service.get_session_history.assert_awaited_once_with(
            user_id=current_user.id,
            session_uuid=training_session.uuid,
            only_answered_items=False,
            page_size=30,
            page_number=1,
        )

    async def test_returns_empty_history(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        training_session_service: AsyncMock,
    ):
        training_session_service.get_session_history.return_value = []

        response = await client.get(
            f"/training-sessions/{training_session.uuid}/history"
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

        training_session_service.get_session_history.assert_awaited_once_with(
            user_id=current_user.id,
            session_uuid=training_session.uuid,
            only_answered_items=False,
            page_size=30,
            page_number=1,
        )

    @pytest.mark.parametrize(
        ("page_size", "page_number"),
        [
            pytest.param(1, 1, id="minimum_values"),
            pytest.param(100, 3, id="maximum_page_size"),
        ],
    )
    async def test_passes_history_filters_and_pagination(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        page_size,
        page_number,
        training_session_service: AsyncMock,
    ):
        training_session_service.get_session_history.return_value = []

        response = await client.get(
            f"/training-sessions/{training_session.uuid}/history",
            params={
                "only_answered_items": True,
                "ps": page_size,
                "pn": page_number,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

        training_session_service.get_session_history.assert_awaited_once_with(
            user_id=current_user.id,
            session_uuid=training_session.uuid,
            only_answered_items=True,
            page_size=page_size,
            page_number=page_number,
        )

    @pytest.mark.parametrize(
        ("params", "expected_detail"),
        [
            pytest.param(
                {"ps": 0},
                {
                    "type": "greater_than_equal",
                    "loc": ["query", "ps"],
                    "msg": "Input should be greater than or equal to 1",
                    "input": "0",
                    "ctx": {"ge": 1},
                },
                id="page_size_below_minimum",
            ),
            pytest.param(
                {"ps": 101},
                {
                    "type": "less_than_equal",
                    "loc": ["query", "ps"],
                    "msg": "Input should be less than or equal to 100",
                    "input": "101",
                    "ctx": {"le": 100},
                },
                id="page_size_above_maximum",
            ),
            pytest.param(
                {"pn": 0},
                {
                    "type": "greater_than_equal",
                    "loc": ["query", "pn"],
                    "msg": "Input should be greater than or equal to 1",
                    "input": "0",
                    "ctx": {"ge": 1},
                },
                id="page_number_below_minimum",
            ),
            pytest.param(
                {"only_answered_items": "not-a-bool"},
                {
                    "type": "bool_parsing",
                    "loc": ["query", "only_answered_items"],
                    "msg": (
                        "Input should be a valid boolean, unable to interpret input"
                    ),
                    "input": "not-a-bool",
                },
                id="invalid_only_answered_items",
            ),
        ],
    )
    async def test_rejects_invalid_query(
        self,
        client: AsyncClient,
        training_session,
        params,
        expected_detail,
        training_session_service: AsyncMock,
    ):
        response = await client.get(
            f"/training-sessions/{training_session.uuid}/history",
            params=params,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        training_session_service.get_session_history.assert_not_awaited()

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                TrainingSessionNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Training session not found",
                id="session_not_found",
            ),
            pytest.param(
                TrainingSessionNotFinishedYet(),
                status.HTTP_409_CONFLICT,
                "Training session not finished yet",
                id="session_not_finished",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        service_error,
        expected_status,
        expected_message,
        training_session_service: AsyncMock,
    ):
        training_session_service.get_session_history.side_effect = service_error

        response = await client.get(
            f"/training-sessions/{training_session.uuid}/history"
        )

        assert response.status_code == expected_status
        assert response.json()["message"] == expected_message

        training_session_service.get_session_history.assert_awaited_once_with(
            user_id=current_user.id,
            session_uuid=training_session.uuid,
            only_answered_items=False,
            page_size=30,
            page_number=1,
        )

    async def test_rejects_invalid_session_uuid(
        self,
        client: AsyncClient,
        training_session_service: AsyncMock,
    ):
        response = await client.get("/training-sessions/not-a-uuid/history")

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "session_uuid"],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        training_session_service.get_session_history.assert_not_awaited()


class TestSubmitAnswer:
    async def test_submits_correct_answer(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        training_session_service: AsyncMock,
    ):
        payload = {
            "action": "answer",
            "answer": "hello",
        }
        training_session_service.submit_answer.return_value = {
            "is_correct": True,
            "answer_text": "hello",
            "answered_count": 4,
            "correct_count": 3,
            "total_count": 10,
            "is_finished": False,
            "time_to_complete": None,
        }

        response = await client.put(
            (f"/training-sessions/{training_session.uuid}/items/1/submit"),
            json=payload,
        )

        expected = {
            "is_correct": True,
            "answer_text": "hello",
            "answered_count": 4,
            "correct_count": 3,
            "total_count": 10,
            "is_finished": False,
            "time_to_complete": None,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        training_session_service.submit_answer.assert_awaited_once_with(
            user_id=current_user.id,
            training_session_uuid=training_session.uuid,
            sequence_number=1,
            user_answer=SubmittedAnswerRequest(**payload),
        )

    async def test_skips_answer(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        training_session_service: AsyncMock,
    ):
        payload = {"action": "skip"}
        training_session_service.submit_answer.return_value = {
            "is_correct": False,
            "answer_text": "hello",
            "answered_count": 4,
            "correct_count": 2,
            "total_count": 10,
            "is_finished": False,
            "time_to_complete": None,
        }

        response = await client.put(
            (f"/training-sessions/{training_session.uuid}/items/2/submit"),
            json=payload,
        )

        expected = {
            "is_correct": False,
            "answer_text": "hello",
            "answered_count": 4,
            "correct_count": 2,
            "total_count": 10,
            "is_finished": False,
            "time_to_complete": None,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        training_session_service.submit_answer.assert_awaited_once_with(
            user_id=current_user.id,
            training_session_uuid=training_session.uuid,
            sequence_number=2,
            user_answer=SkipAnswerRequest(action="skip", answer=None),
        )

    async def test_returns_finished_answer_result(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        training_session_service: AsyncMock,
    ):
        payload = {
            "action": "answer",
            "answer": "hello",
        }
        training_session_service.submit_answer.return_value = {
            "is_correct": True,
            "answer_text": "hello",
            "answered_count": 10,
            "correct_count": 7,
            "total_count": 10,
            "is_finished": True,
            "time_to_complete": 60,
        }

        response = await client.put(
            (f"/training-sessions/{training_session.uuid}/items/10/submit"),
            json=payload,
        )

        expected = {
            "is_correct": True,
            "answer_text": "hello",
            "answered_count": 10,
            "correct_count": 7,
            "total_count": 10,
            "is_finished": True,
            "time_to_complete": 60,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        training_session_service.submit_answer.assert_awaited_once_with(
            user_id=current_user.id,
            training_session_uuid=training_session.uuid,
            sequence_number=10,
            user_answer=SubmittedAnswerRequest(**payload),
        )

    async def test_normalizes_answer(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        training_session_service: AsyncMock,
    ):
        payload = {
            "action": "answer",
            "answer": "  HeLLo  ",
        }
        training_session_service.submit_answer.return_value = {
            "is_correct": True,
            "answer_text": "hello",
            "answered_count": 1,
            "correct_count": 1,
            "total_count": 10,
            "is_finished": False,
            "time_to_complete": None,
        }

        response = await client.put(
            (f"/training-sessions/{training_session.uuid}/items/1/submit"),
            json=payload,
        )

        expected = {
            "is_correct": True,
            "answer_text": "hello",
            "answered_count": 1,
            "correct_count": 1,
            "total_count": 10,
            "is_finished": False,
            "time_to_complete": None,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        training_session_service.submit_answer.assert_awaited_once_with(
            user_id=current_user.id,
            training_session_uuid=training_session.uuid,
            sequence_number=1,
            user_answer=SubmittedAnswerRequest(
                action="answer",
                answer="hello",
            ),
        )

    @pytest.mark.parametrize(
        "answer",
        [
            pytest.param("a", id="minimum_length"),
            pytest.param("a" * 255, id="maximum_length"),
        ],
    )
    async def test_accepts_answer_boundary_values(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        answer,
        training_session_service: AsyncMock,
    ):
        payload = {
            "action": "answer",
            "answer": answer,
        }
        training_session_service.submit_answer.return_value = {
            "is_correct": False,
            "answer_text": "hello",
            "answered_count": 1,
            "correct_count": 0,
            "total_count": 10,
            "is_finished": False,
            "time_to_complete": None,
        }

        response = await client.put(
            (f"/training-sessions/{training_session.uuid}/items/1/submit"),
            json=payload,
        )

        expected = {
            "is_correct": False,
            "answer_text": "hello",
            "answered_count": 1,
            "correct_count": 0,
            "total_count": 10,
            "is_finished": False,
            "time_to_complete": None,
        }

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == expected

        training_session_service.submit_answer.assert_awaited_once_with(
            user_id=current_user.id,
            training_session_uuid=training_session.uuid,
            sequence_number=1,
            user_answer=SubmittedAnswerRequest(**payload),
        )

    @pytest.mark.parametrize(
        ("payload", "expected_detail"),
        [
            pytest.param(
                {"action": "answer", "answer": ""},
                {
                    "type": "string_too_short",
                    "loc": ["body", "answer", "answer"],
                    "msg": "String should have at least 1 character",
                    "input": "",
                    "ctx": {"min_length": 1},
                },
                id="answer_empty",
            ),
            pytest.param(
                {"action": "answer", "answer": "a" * 256},
                {
                    "type": "string_too_long",
                    "loc": ["body", "answer", "answer"],
                    "msg": "String should have at most 255 characters",
                    "input": "a" * 256,
                    "ctx": {"max_length": 255},
                },
                id="answer_too_long",
            ),
            pytest.param(
                {"action": "answer", "answer": None},
                {
                    "type": "string_type",
                    "loc": ["body", "answer", "answer"],
                    "msg": "Input should be a valid string",
                    "input": None,
                },
                id="answer_null",
            ),
            pytest.param(
                {"action": "skip", "answer": "hello"},
                {
                    "type": "none_required",
                    "loc": ["body", "skip", "answer"],
                    "msg": "Input should be None",
                    "input": "hello",
                },
                id="skip_answer_not_null",
            ),
        ],
    )
    async def test_rejects_invalid_answer_payload(
        self,
        client: AsyncClient,
        training_session,
        payload,
        expected_detail,
        training_session_service: AsyncMock,
    ):
        response = await client.put(
            (f"/training-sessions/{training_session.uuid}/items/1/submit"),
            json=payload,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [expected_detail],
        }

        training_session_service.submit_answer.assert_not_awaited()

    async def test_rejects_missing_action(
        self,
        client: AsyncClient,
        training_session,
        training_session_service: AsyncMock,
    ):
        payload = {"answer": "hello"}

        response = await client.put(
            (f"/training-sessions/{training_session.uuid}/items/1/submit"),
            json=payload,
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "union_tag_not_found",
                    "loc": ["body"],
                    "msg": "Unable to extract tag using discriminator 'action'",
                    "input": payload,
                    "ctx": {"discriminator": "'action'"},
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        training_session_service.submit_answer.assert_not_awaited()

    async def test_rejects_invalid_action(
        self,
        client: AsyncClient,
        training_session,
        training_session_service: AsyncMock,
    ):
        payload = {
            "action": "invalid",
            "answer": "hello",
        }

        response = await client.put(
            (f"/training-sessions/{training_session.uuid}/items/1/submit"),
            json=payload,
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "union_tag_invalid",
                    "loc": ["body"],
                    "msg": (
                        "Input tag 'invalid' found using 'action' does not match "
                        "any of the expected tags: 'skip', 'answer'"
                    ),
                    "input": payload,
                    "ctx": {
                        "discriminator": "'action'",
                        "tag": "invalid",
                        "expected_tags": "'skip', 'answer'",
                    },
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        training_session_service.submit_answer.assert_not_awaited()

    async def test_rejects_missing_answer_for_answer_action(
        self,
        client: AsyncClient,
        training_session,
        training_session_service: AsyncMock,
    ):
        payload = {"action": "answer"}

        response = await client.put(
            (f"/training-sessions/{training_session.uuid}/items/1/submit"),
            json=payload,
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "missing",
                    "loc": ["body", "answer", "answer"],
                    "msg": "Field required",
                    "input": payload,
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        training_session_service.submit_answer.assert_not_awaited()

    @pytest.mark.parametrize(
        ("service_error", "expected_status", "expected_message"),
        [
            pytest.param(
                TrainingSessionNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Training session not found",
                id="session_not_found",
            ),
            pytest.param(
                TrainingSessionItemNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "Training session item not found",
                id="session_item_not_found",
            ),
            pytest.param(
                UserDeckNotFoundError(),
                status.HTTP_404_NOT_FOUND,
                "User deck progress not found",
                id="user_deck_not_found",
            ),
            pytest.param(
                TrainingSessionAlreadyFinishedError(),
                status.HTTP_409_CONFLICT,
                "Training session already finished",
                id="session_already_finished",
            ),
        ],
    )
    async def test_returns_service_error(
        self,
        client: AsyncClient,
        current_user,
        training_session,
        service_error,
        expected_status,
        expected_message,
        training_session_service: AsyncMock,
    ):
        payload = {
            "action": "answer",
            "answer": "hello",
        }
        training_session_service.submit_answer.side_effect = service_error

        response = await client.put(
            (f"/training-sessions/{training_session.uuid}/items/1/submit"),
            json=payload,
        )

        assert response.status_code == expected_status
        assert response.json()["message"] == expected_message

        training_session_service.submit_answer.assert_awaited_once_with(
            user_id=current_user.id,
            training_session_uuid=training_session.uuid,
            sequence_number=1,
            user_answer=SubmittedAnswerRequest(**payload),
        )

    async def test_rejects_sequence_number_below_minimum(
        self,
        client: AsyncClient,
        training_session,
        training_session_service: AsyncMock,
    ):
        response = await client.put(
            (f"/training-sessions/{training_session.uuid}/items/0/submit"),
            json={"action": "skip"},
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "greater_than_equal",
                    "loc": ["path", "sequence_number"],
                    "msg": "Input should be greater than or equal to 1",
                    "input": "0",
                    "ctx": {"ge": 1},
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        training_session_service.submit_answer.assert_not_awaited()

    async def test_rejects_invalid_training_session_uuid(
        self,
        client: AsyncClient,
        training_session_service: AsyncMock,
    ):
        response = await client.put(
            "/training-sessions/not-a-uuid/items/1/submit",
            json={"action": "skip"},
        )

        expected = {
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": [
                {
                    "type": "uuid_parsing",
                    "loc": ["path", "training_session_uuid"],
                    "msg": (
                        "Input should be a valid UUID, invalid character: "
                        "found `n` at 1"
                    ),
                    "input": "not-a-uuid",
                    "ctx": {"error": "invalid character: found `n` at 1"},
                }
            ],
        }

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == expected

        training_session_service.submit_answer.assert_not_awaited()
