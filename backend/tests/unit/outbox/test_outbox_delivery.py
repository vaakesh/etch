from unittest.mock import AsyncMock, Mock, create_autospec

import pytest

from app.outbox.models import OutboxMessage
from app.outbox.repository import OutboxRepository
from app.outbox.service import OutboxPublisher
from app.service import UnitOfWork


@pytest.fixture
def delivery_context():
    uow = create_autospec(UnitOfWork, instance=True)
    uow.__aenter__.return_value = uow
    uow.__aexit__.return_value = False
    uow.outbox_repo = create_autospec(OutboxRepository, instance=True)
    uow.outbox_repo.mark_published.return_value = True
    uow.outbox_repo.get_pending.return_value = []
    handler = AsyncMock()
    publisher = OutboxPublisher(Mock(return_value=uow), {"example.v1": handler})
    message = OutboxMessage(
        id=17, event_type="example.v1", payload={"object_id": 42}, published=False,
    )
    return publisher, uow, handler, message


class TestPublish:
    async def test_commits_publication_only_after_handler_succeeds(self, delivery_context):
        publisher, uow, handler, message = delivery_context
        order = Mock()
        order.attach_mock(handler, "deliver")
        order.attach_mock(uow.outbox_repo.mark_published, "mark")
        order.attach_mock(uow.commit, "commit")

        published = await publisher.publish(message)

        assert published is True
        assert [call[0] for call in order.mock_calls] == ["deliver", "mark", "commit"]
        handler.assert_awaited_once_with({"object_id": 42})
        uow.outbox_repo.mark_published.assert_awaited_once_with(17)

    async def test_leaves_message_pending_when_delivery_fails(self, delivery_context):
        publisher, uow, handler, message = delivery_context
        handler.side_effect = RuntimeError("destination unavailable")

        with pytest.raises(RuntimeError, match="destination unavailable"):
            await publisher.publish(message)

        uow.outbox_repo.mark_published.assert_not_awaited()
        uow.commit.assert_not_awaited()

    async def test_allows_redelivery_after_publication_commit_fails(self, delivery_context):
        publisher, uow, handler, message = delivery_context
        uow.commit.side_effect = RuntimeError("database unavailable")

        with pytest.raises(RuntimeError, match="database unavailable"):
            await publisher.publish(message)
        uow.commit.side_effect = None
        published = await publisher.publish(message)

        assert published is True
        assert handler.await_count == 2
        assert uow.outbox_repo.mark_published.await_count == 2

    async def test_skips_already_published_message(self, delivery_context):
        publisher, uow, handler, message = delivery_context
        message.published = True

        published = await publisher.publish(message)

        assert published is False
        handler.assert_not_awaited()
        uow.commit.assert_not_awaited()

    async def test_does_not_publish_unregistered_type(self, delivery_context):
        publisher, uow, handler, message = delivery_context
        message.event_type = "another-worker.v1"

        with pytest.raises(KeyError, match="another-worker.v1"):
            await publisher.publish(message)

        handler.assert_not_awaited()
        uow.outbox_repo.mark_published.assert_not_awaited()


class TestPublishPending:
    async def test_selects_only_registered_event_types_and_delivers_pending_message(
        self, delivery_context,
    ):
        publisher, uow, handler, message = delivery_context
        uow.outbox_repo.get_pending.return_value = [message]

        published = await publisher.publish_pending(limit=25)

        assert published == 1
        uow.outbox_repo.get_pending.assert_awaited_once_with(
            event_types=["example.v1"], limit=25,
        )
        handler.assert_awaited_once_with({"object_id": 42})

    @pytest.mark.parametrize("limit", [0, 1001])
    async def test_rejects_invalid_batch_limit(self, delivery_context, limit):
        publisher, uow, handler, message = delivery_context

        with pytest.raises(ValueError, match="limit must be between"):
            await publisher.publish_pending(limit=limit)

        uow.outbox_repo.get_pending.assert_not_awaited()
