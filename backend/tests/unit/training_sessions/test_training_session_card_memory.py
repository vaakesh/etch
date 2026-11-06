from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, create_autospec
from uuid import UUID

import pytest

from app.card_memory.models import CardMemoryState
from app.card_memory.replay import ReviewEvent
from app.card_memory.repository import CardMemoryRepository
from app.decks.repository import DeckRepository
from app.fsrs.types import CardState, Rating
from app.redis.invalidation import CacheInvalidator
from app.training_sessions.repository import (
    TrainingSessionItemRepository,
    TrainingSessionRepository,
)
from app.training_sessions.errors import (
    CardNotAnsweredError,
    TrainingSessionItemNotFoundError,
    TrainingSessionNotFoundError,
)
from app.training_sessions.models import TrainingSessionStatus
from app.training_sessions.schemas import (
    RateAnswerResponse,
    SkipAnswerRequest,
    SubmittedAnswerRequest,
)
from app.training_sessions.service import TrainingSessionService

from tests.unit.factories import (
    make_deck,
    make_training_session,
    make_training_session_item,
)

NOW = datetime(2026, 8, 15, 17, 0, tzinfo=UTC)
LEARNING_KEY = UUID("019a0000-0000-7000-8000-000000000001")


def make_new_memory(prompt_side: str = "front") -> CardMemoryState:
    # Так строку создаёт get_or_create_for_update при первом ответе
    return CardMemoryState(
        user_id=42,
        learning_key=LEARNING_KEY,
        prompt_side=prompt_side,
        state=CardState.LEARNING,
        step=0,
        stability=None,
        difficulty=None,
        due=NOW,
        last_review=None,
    )


@pytest.fixture
def memory_context(monkeypatch):
    monkeypatch.setattr("app.training_sessions.service.utcnow", lambda: NOW)
    deck = make_deck()
    session = make_training_session(deck=deck)
    item = make_training_session_item(
        sequence_number=4,
        learning_key_snapshot=LEARNING_KEY,
    )
    memory = make_new_memory()

    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    uow.commit = AsyncMock()
    uow.flush = AsyncMock()
    uow.deck_repo = create_autospec(DeckRepository, instance=True)
    uow.training_session_repo = create_autospec(TrainingSessionRepository, instance=True)
    uow.training_session_item_repo = create_autospec(
        TrainingSessionItemRepository, instance=True,
    )
    uow.card_memory_repo = create_autospec(CardMemoryRepository, instance=True)
    uow.deck_repo.get_by_id.return_value = deck
    uow.training_session_repo.get_by_uuid.return_value = session
    uow.training_session_item_repo.get_item_by_sequence_number_and_session_id.return_value = (
        item
    )
    uow.card_memory_repo.get_or_create_for_update.return_value = memory

    service = TrainingSessionService(
        uow_factory=lambda: uow,
        cache_invalidator=create_autospec(CacheInvalidator, instance=True),
    )
    return SimpleNamespace(
        service=service, uow=uow, session=session, item=item, memory=memory,
    )


async def submit(ctx, user_answer):
    return await ctx.service.submit_answer(
        user_id=42,
        training_session_uuid=ctx.session.uuid,
        sequence_number=4,
        user_answer=user_answer,
    )


class TestSubmitAnswerCardMemory:
    async def test_correct_answer_reviews_memory_as_good(self, memory_context):
        ctx = memory_context

        result = await submit(ctx, SubmittedAnswerRequest(action="answer", answer="hello"))

        assert result.next_review_at == NOW + timedelta(minutes=10)
        assert ctx.memory.state == CardState.LEARNING
        assert ctx.memory.step == 1
        assert ctx.memory.stability == 2.3065
        assert ctx.memory.difficulty == pytest.approx(2.118103970459016, rel=1e-12)
        assert ctx.memory.due == NOW + timedelta(minutes=10)
        assert ctx.memory.last_review == NOW

    @pytest.mark.parametrize(
        "user_answer",
        [
            SubmittedAnswerRequest(action="answer", answer="wrong"),
            SkipAnswerRequest(action="skip"),
        ],
        ids=["wrong-answer", "skip"],
    )
    async def test_wrong_answer_or_skip_reviews_memory_as_again(
        self, memory_context, user_answer,
    ):
        ctx = memory_context

        result = await submit(ctx, user_answer)

        assert ctx.memory.state == CardState.LEARNING
        assert ctx.memory.step == 0
        assert ctx.memory.stability == 0.212
        assert ctx.memory.difficulty == 6.4133
        assert ctx.memory.due == NOW + timedelta(minutes=1)
        assert ctx.memory.last_review == NOW
        assert result.next_review_at == NOW + timedelta(minutes=1)

    async def test_locks_memory_for_user_word_and_prompt_side(self, memory_context):
        ctx = memory_context
        ctx.session.prompt_side = "back"
        ctx.session.answer_side = "front"

        await submit(ctx, SubmittedAnswerRequest(action="answer", answer="hello"))

        ctx.uow.card_memory_repo.get_or_create_for_update.assert_awaited_once_with(
            user_id=42,
            learning_key=LEARNING_KEY,
            prompt_side="back",
            now=NOW,
        )
        ctx.uow.commit.assert_awaited_once()

    async def test_updates_existing_review_memory(self, memory_context):
        ctx = memory_context
        ctx.memory.state = CardState.REVIEW
        ctx.memory.step = None
        ctx.memory.stability = 10.971048263078135
        ctx.memory.difficulty = 2.1043313908464483
        ctx.memory.last_review = NOW - timedelta(days=11)
        ctx.memory.due = NOW

        await submit(ctx, SubmittedAnswerRequest(action="answer", answer="hello"))

        assert ctx.memory.state == CardState.REVIEW
        assert ctx.memory.stability == pytest.approx(46.316858440073425, rel=1e-12)
        assert ctx.memory.due == NOW + timedelta(days=46)

    async def test_takes_answer_time_after_waiting_for_memory_lock(
        self, memory_context, monkeypatch,
    ):
        ctx = memory_context
        lock_released_at = NOW + timedelta(seconds=1)
        clock = {"now": NOW}
        monkeypatch.setattr(
            "app.training_sessions.service.utcnow", lambda: clock["now"],
        )

        async def wait_for_lock(**kwargs):
            # Пока ждём блокировку, параллельный ответ на слово коммитится
            clock["now"] = lock_released_at
            return ctx.memory

        ctx.uow.card_memory_repo.get_or_create_for_update.side_effect = wait_for_lock

        await submit(ctx, SubmittedAnswerRequest(action="answer", answer="hello"))

        assert ctx.item.answered_at == lock_released_at
        assert ctx.memory.last_review == lock_released_at
        assert ctx.memory.due == lock_released_at + timedelta(minutes=10)

    async def test_shifts_answer_after_review_from_clock_ahead(self, memory_context):
        ctx = memory_context
        # Прошлый ответ записал инстанс, чьи часы спешат на 5 мс
        last_review = NOW + timedelta(milliseconds=5)
        ctx.memory.step = 1
        ctx.memory.stability = 2.3065
        ctx.memory.difficulty = 2.118103970459016
        ctx.memory.last_review = last_review
        ctx.memory.due = last_review + timedelta(minutes=10)

        await submit(ctx, SubmittedAnswerRequest(action="answer", answer="hello"))

        shifted = last_review + timedelta(microseconds=1)
        assert ctx.item.answered_at == shifted
        assert ctx.memory.last_review == shifted
        assert ctx.memory.state == CardState.REVIEW
        assert ctx.memory.step is None
        assert ctx.memory.due == shifted + timedelta(days=2)
        ctx.uow.commit.assert_awaited_once()

    async def test_skips_memory_for_item_without_learning_key(self, memory_context):
        ctx = memory_context
        ctx.item.learning_key_snapshot = None

        result = await submit(ctx, SubmittedAnswerRequest(action="answer", answer="hello"))

        assert result.next_review_at is None
        ctx.uow.card_memory_repo.get_or_create_for_update.assert_not_awaited()
        ctx.uow.commit.assert_awaited_once()

    async def test_repeated_submit_does_not_review_memory_again(self, memory_context):
        ctx = memory_context
        ctx.item.is_answered = True
        ctx.item.is_correct = True
        ctx.item.answered_at = NOW

        result = await submit(ctx, SubmittedAnswerRequest(action="answer", answer="hello"))

        assert result.next_review_at is None
        ctx.uow.card_memory_repo.get_or_create_for_update.assert_not_awaited()
        ctx.uow.commit.assert_not_awaited()


ANSWERED_AT = NOW - timedelta(hours=1)


@pytest.fixture
def rate_context(memory_context):
    ctx = memory_context
    ctx.item.is_answered = True
    ctx.item.is_correct = False
    ctx.item.answered_at = ANSWERED_AT
    # История слова из журнала — один ответ, уже с новой самооценкой
    ctx.uow.card_memory_repo.get_review_events.return_value = [
        ReviewEvent(
            user_id=42,
            learning_key=LEARNING_KEY,
            prompt_side="front",
            rating=Rating.EASY,
            answered_at=ANSWERED_AT,
        ),
    ]
    return ctx


async def rate(ctx, rating: int, user_id: int = 42):
    return await ctx.service.rate_answer(
        user_id=user_id,
        training_session_uuid=ctx.session.uuid,
        sequence_number=4,
        rating=rating,
    )


class TestRateAnswer:
    async def test_stores_self_rating_and_rebuilds_memory_from_history(self, rate_context):
        ctx = rate_context

        result = await rate(ctx, 4)

        assert result == RateAnswerResponse(
            rating=4,
            next_review_at=ANSWERED_AT + timedelta(days=8),
        )
        assert ctx.item.self_rating == 4
        assert ctx.memory.state == CardState.REVIEW
        assert ctx.memory.stability == 8.2956
        assert ctx.memory.due == ANSWERED_AT + timedelta(days=8)
        assert ctx.memory.last_review == ANSWERED_AT
        ctx.uow.commit.assert_awaited_once()

    async def test_reads_history_of_rated_word_after_flushing_rating(self, rate_context):
        ctx = rate_context
        ctx.session.prompt_side = "back"
        ctx.session.answer_side = "front"
        ctx.uow.card_memory_repo.get_review_events.return_value[0] = ReviewEvent(
            user_id=42,
            learning_key=LEARNING_KEY,
            prompt_side="back",
            rating=Rating.EASY,
            answered_at=ANSWERED_AT,
        )

        await rate(ctx, 4)

        ctx.uow.card_memory_repo.get_or_create_for_update.assert_awaited_once_with(
            user_id=42,
            learning_key=LEARNING_KEY,
            prompt_side="back",
            now=ANSWERED_AT,
        )
        ctx.uow.flush.assert_awaited_once()
        ctx.uow.card_memory_repo.get_review_events.assert_awaited_once_with(
            key=(42, LEARNING_KEY, "back"),
        )

    async def test_allows_rating_after_session_completed(self, rate_context):
        ctx = rate_context
        ctx.session.status = TrainingSessionStatus.COMPLETED
        ctx.session.finished_at = NOW

        result = await rate(ctx, 4)

        assert result.rating == 4
        ctx.uow.commit.assert_awaited_once()

    async def test_stores_rating_without_memory_for_item_without_learning_key(
        self, rate_context,
    ):
        ctx = rate_context
        ctx.item.learning_key_snapshot = None

        result = await rate(ctx, 2)

        assert result == RateAnswerResponse(rating=2, next_review_at=None)
        assert ctx.item.self_rating == 2
        ctx.uow.card_memory_repo.get_or_create_for_update.assert_not_awaited()
        ctx.uow.commit.assert_awaited_once()

    async def test_rejects_unanswered_item(self, rate_context):
        ctx = rate_context
        ctx.item.is_answered = False
        ctx.item.is_correct = None
        ctx.item.answered_at = None

        with pytest.raises(CardNotAnsweredError):
            await rate(ctx, 3)

        assert ctx.item.self_rating is None
        ctx.uow.commit.assert_not_awaited()

    async def test_hides_session_of_other_user(self, rate_context):
        ctx = rate_context

        with pytest.raises(TrainingSessionNotFoundError):
            await rate(ctx, 3, user_id=43)

        ctx.uow.training_session_item_repo.get_item_by_sequence_number_and_session_id.assert_not_awaited()
        ctx.uow.commit.assert_not_awaited()

    async def test_rejects_missing_item(self, rate_context):
        ctx = rate_context
        ctx.uow.training_session_item_repo.get_item_by_sequence_number_and_session_id.return_value = None

        with pytest.raises(TrainingSessionItemNotFoundError):
            await rate(ctx, 3)

        ctx.uow.commit.assert_not_awaited()
