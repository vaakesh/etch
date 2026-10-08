from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import UUID

import pytest

from app.decks.repository import DeckRepository
from app.redis.invalidation import CacheInvalidator
from app.training_sessions.errors import (
    TrainingSessionAlreadyFinishedError,
    TrainingSessionDeckArchivedError,
    TrainingSessionDeckUnavailableError,
    TrainingSessionNotFoundError,
)
from app.training_sessions.models import TrainingSessionStatus
from app.training_sessions.repository import (
    TrainingSessionItemRepository,
    TrainingSessionRepository,
)
from app.training_sessions.schemas import (
    ActiveTrainingSessionActivityRequest,
    SubmittedAnswerRequest,
)
from app.training_sessions.service import TrainingSessionService
from tests.unit.factories import (
    make_deck,
    make_training_session,
    make_training_session_item,
)

NOW = datetime(2026, 8, 15, 17, 0, tzinfo=UTC)
COPY_UUID = UUID("0198ad01-b200-7000-8000-000000000201")
TRACKER_UUID = UUID("0198ad01-b200-7000-8000-000000000600")


@pytest.fixture
def context(monkeypatch):
    monkeypatch.setattr("app.training_sessions.service.utcnow", lambda: NOW)
    deck = make_deck()
    session = make_training_session(deck=deck)
    item = make_training_session_item(sequence_number=4)
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.commit = AsyncMock()
    uow.deck_repo = create_autospec(DeckRepository, instance=True)
    uow.training_session_repo = create_autospec(
        TrainingSessionRepository, instance=True,
    )
    uow.training_session_item_repo = create_autospec(
        TrainingSessionItemRepository, instance=True,
    )
    uow.deck_repo.get_by_id.return_value = deck
    uow.training_session_repo.get_by_uuid.return_value = session
    uow.training_session_item_repo.get_next_cards.return_value = [item]
    uow.training_session_item_repo.get_item_by_sequence_number_and_session_id.return_value = item
    invalidator = create_autospec(CacheInvalidator, instance=True)
    service = TrainingSessionService(
        uow_factory=lambda: uow, cache_invalidator=invalidator,
    )
    return SimpleNamespace(
        service=service, uow=uow, session=session, item=item, deck=deck,
    )


@pytest.fixture(params=[
    pytest.param("archived", id="unexpired_archive"),
    pytest.param("expired", id="expired_archive"),
    pytest.param("expires_now", id="archive_expiration_boundary"),
    pytest.param("missing_expiration", id="archive_without_expiration"),
    pytest.param("deleted", id="deleted_deck"),
    pytest.param("missing", id="missing_deck"),
])
def blocked_session(context, request):
    case = request.param
    expected_error = TrainingSessionDeckUnavailableError
    if case == "deleted":
        context.session.deck_id = None
    elif case == "missing":
        context.uow.deck_repo.get_by_id.return_value = None
    else:
        context.deck.state = "archived"
        context.deck.user_id = None
        context.deck.is_public = False
        context.deck.expires_at = {
            "archived": NOW + timedelta(days=1),
            "expired": NOW - timedelta(seconds=1),
            "expires_now": NOW,
            "missing_expiration": None,
        }[case]
        if case == "archived":
            expected_error = TrainingSessionDeckArchivedError
    return context, expected_error


class TestResumePracticeSession:
    async def test_rejects_unavailable_deck_without_loading_cards(self, blocked_session):
        context, expected_error = blocked_session

        with pytest.raises(expected_error):
            await context.service.resume_practice_session(42, context.session.uuid)

        context.uow.training_session_item_repo.get_next_cards.assert_not_awaited()
        assert context.session.status == TrainingSessionStatus.IN_PROGRESS
        assert context.session.finished_at is None

    async def test_resumes_same_session_after_transfer_to_active_copy(self, context):
        context.deck.state = "archived"
        context.deck.expires_at = NOW + timedelta(days=1)
        copy = make_deck(id=201, uuid=COPY_UUID, is_public=False)
        context.uow.deck_repo.get_by_id.side_effect = [context.deck, copy]

        with pytest.raises(TrainingSessionDeckArchivedError):
            await context.service.resume_practice_session(42, context.session.uuid)
        context.session.deck_id = copy.id
        result = await context.service.resume_practice_session(42, context.session.uuid)

        assert result.model_dump() == {
            "training_session_uuid": context.session.uuid,
            "deck_uuid": COPY_UUID,
            "prompt_side": "front",
            "answer_side": "back",
            "total_count": 10,
            "answered_count": 3,
            "correct_count": 2,
            "wrong_count": 1,
            "started_at": datetime(2026, 8, 15, 16, 0, tzinfo=UTC),
            "cards": [{
                "sequence_number": 4,
                "prompt_text": "привет",
                "prompt_language": "ru",
                "answer_language": "en",
            }],
        }
        context.uow.deck_repo.get_by_id.assert_awaited_with(deck_id=201)
        context.uow.training_session_repo.get_by_uuid.assert_awaited_with(
            context.session.uuid, for_update=True,
        )

    async def test_checks_session_owner_before_deck_availability(self, context):
        with pytest.raises(TrainingSessionNotFoundError):
            await context.service.resume_practice_session(99, context.session.uuid)

        context.uow.deck_repo.get_by_id.assert_not_awaited()


class TestSubmitAnswer:
    async def test_rejects_unavailable_deck_without_mutating_answer(self, blocked_session):
        context, expected_error = blocked_session

        with pytest.raises(expected_error):
            await context.service.submit_answer(
                user_id=42,
                training_session_uuid=context.session.uuid,
                sequence_number=4,
                user_answer=SubmittedAnswerRequest(action="answer", answer="hello"),
            )

        assert context.session.answered_count == 3
        assert context.item.is_answered is False
        assert context.item.answered_at is None
        context.uow.commit.assert_not_awaited()

    async def test_accepts_answer_after_transfer_to_active_copy(self, context):
        context.session.deck_id = 201
        context.uow.deck_repo.get_by_id.return_value = make_deck(
            id=201, uuid=COPY_UUID, is_public=False,
        )

        result = await context.service.submit_answer(
            user_id=42,
            training_session_uuid=context.session.uuid,
            sequence_number=4,
            user_answer=SubmittedAnswerRequest(action="answer", answer="hello"),
        )

        assert result.model_dump() == {
            "is_correct": True,
            "answer_text": "hello",
            "answered_count": 4,
            "correct_count": 3,
            "total_count": 10,
            "is_finished": False,
            "time_to_complete": None,
        }
        assert context.item.answered_at == NOW
        context.uow.commit.assert_awaited_once()

    @pytest.mark.parametrize(
        "session_status",
        [TrainingSessionStatus.COMPLETED, TrainingSessionStatus.ABANDONED],
    )
    @pytest.mark.parametrize("deck_id", [200, None])
    async def test_rejects_finished_session_before_loading_deck_or_answer(
        self, context, session_status, deck_id,
    ):
        context.session.status = session_status
        context.session.finished_at = NOW
        context.session.deck_id = deck_id
        context.session.answered_count = 10
        context.session.correct_count = 7
        context.session.wrong_count = 3
        context.item.is_answered = True
        context.item.is_correct = True
        context.item.user_typed_text = "hello"
        context.item.answered_at = NOW

        with pytest.raises(TrainingSessionAlreadyFinishedError):
            await context.service.submit_answer(
                user_id=42,
                training_session_uuid=context.session.uuid,
                sequence_number=4,
                user_answer=SubmittedAnswerRequest(action="answer", answer="hello"),
            )

        assert context.session.answered_count == 10
        assert context.session.correct_count == 7
        assert context.session.wrong_count == 3
        context.uow.deck_repo.get_by_id.assert_not_awaited()
        context.uow.training_session_item_repo.get_item_by_sequence_number_and_session_id.assert_not_awaited()
        context.uow.commit.assert_not_awaited()

    async def test_returns_repeated_answer_for_in_progress_session(self, context):
        context.item.sequence_number = 3
        context.item.is_answered = True
        context.item.is_correct = True
        context.item.user_typed_text = "hello"
        context.item.answered_at = NOW

        result = await context.service.submit_answer(
            user_id=42,
            training_session_uuid=context.session.uuid,
            sequence_number=3,
            user_answer=SubmittedAnswerRequest(action="answer", answer="hello"),
        )

        assert result.model_dump() == {
            "is_correct": True,
            "answer_text": "hello",
            "answered_count": 3,
            "correct_count": 2,
            "total_count": 10,
            "is_finished": False,
            "time_to_complete": None,
        }
        context.uow.commit.assert_not_awaited()


class TestRecordActivity:
    @pytest.mark.parametrize("event", ["resume", "heartbeat", "pause"])
    async def test_rejects_unavailable_deck_without_accruing_time(
        self, blocked_session, event,
    ):
        context, expected_error = blocked_session
        context.session.activity_tracker_uuid = TRACKER_UUID
        context.session.activity_last_seen_at = NOW - timedelta(seconds=10)
        if event == "resume":
            from app.training_sessions.schemas import ResumeTrainingSessionActivityRequest
            payload = ResumeTrainingSessionActivityRequest(event="resume")
        else:
            payload = ActiveTrainingSessionActivityRequest(
                event=event, tracker_uuid=TRACKER_UUID,
            )

        with pytest.raises(expected_error):
            await context.service.record_activity(42, context.session.uuid, payload)

        assert context.session.active_study_time_ms == 0
        assert context.session.activity_last_seen_at == NOW - timedelta(seconds=10)
        assert context.session.activity_tracker_uuid == TRACKER_UUID
        context.uow.commit.assert_not_awaited()

    async def test_records_activity_for_active_copy(self, context):
        context.session.deck_id = 201
        context.uow.deck_repo.get_by_id.return_value = make_deck(
            id=201, uuid=COPY_UUID, is_public=False,
        )
        context.session.activity_tracker_uuid = TRACKER_UUID
        context.session.activity_last_seen_at = NOW - timedelta(seconds=10)
        payload = ActiveTrainingSessionActivityRequest(
            event="heartbeat", tracker_uuid=TRACKER_UUID,
        )

        result = await context.service.record_activity(42, context.session.uuid, payload)

        assert result.model_dump() == {"tracker_uuid": TRACKER_UUID}
        assert context.session.active_study_time_ms == 10_000
        assert context.session.activity_last_seen_at == NOW
        context.uow.commit.assert_awaited_once()

    async def test_ignores_activity_for_completed_session_without_deck(self, context):
        context.session.status = TrainingSessionStatus.COMPLETED
        context.session.finished_at = NOW
        context.session.deck_id = None
        payload = ActiveTrainingSessionActivityRequest(
            event="heartbeat", tracker_uuid=TRACKER_UUID,
        )

        result = await context.service.record_activity(42, context.session.uuid, payload)

        assert result.model_dump() == {"tracker_uuid": None}
        context.uow.deck_repo.get_by_id.assert_not_awaited()
        context.uow.commit.assert_not_awaited()
