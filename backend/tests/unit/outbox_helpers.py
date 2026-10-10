from unittest.mock import create_autospec

from app.outbox.repository import OutboxRepository
from app.redis.invalidation import load_scopes

OUTBOX_MESSAGE_ID = 900


def make_outbox_repo():
    repo = create_autospec(OutboxRepository, instance=True)

    def add(message):
        message.id = OUTBOX_MESSAGE_ID

    repo.add.side_effect = add
    return repo


def first_commit_precedes_invalidation(uow, invalidator):
    """side_effect для uow.commit: изменения фиксируются до сброса кэша."""

    def check():
        # второй commit закрывает событие уже после сброса
        if not uow.outbox_repo.mark_published.await_count:
            invalidator.invalidate.assert_not_awaited()

    return check


def staged_message(uow):
    uow.outbox_repo.add.assert_called_once()
    return uow.outbox_repo.add.call_args.args[0]


def assert_invalidation_delivered_from_outbox(uow, invalidator):
    """Событие в outbox описывает те же операции, что ушли в Redis, и закрыто."""
    message = staged_message(uow)
    invalidator.invalidate.assert_awaited_once()
    invalidated = {op for group in invalidator.invalidate.await_args.args for op in group}
    staged = {op for group in load_scopes(message.payload) for op in group}

    assert message.event_type == "cache.invalidation.v1"
    assert staged == invalidated
    uow.outbox_repo.mark_published.assert_awaited_once_with(OUTBOX_MESSAGE_ID)


def assert_no_invalidation_staged(uow, invalidator):
    uow.outbox_repo.add.assert_not_called()
    invalidator.invalidate.assert_not_awaited()
    uow.outbox_repo.mark_published.assert_not_awaited()
