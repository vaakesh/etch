"""Архивация и восстановление колод в открытом UnitOfWork.

Вызывающий сервис проверяет права, делает commit и инвалидирует кеши.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from app.cards.models import Card
from app.common.utils import utcnow
from app.decks.errors import DeckNotFoundError, PermissionDeniedError
from app.decks.models import Deck, DeckArchiveRecipient, DeckCard, UserDeck
from app.decks.utils import make_user_deck_identity
from app.service import UnitOfWork
from app.tracing import traced
from app.training_sessions.models import TrainingSession, TrainingSessionStatus


class DeckContentCopier:
    def __init__(
        self,
        uow: UnitOfWork,
    ):
        self.uow = uow

    async def _lock_source_graph(
        self,
        source_deck_uuid: UUID,
    ) -> tuple[Deck, list[DeckCard], list[Card]]:
        result = await self.uow.deck_repo.lock_deck_graph(
            deck_uuid=source_deck_uuid,
        )
        if result is None:
            raise DeckNotFoundError()
        return result

    async def create_archive(
        self,
        source_deck_uuid: UUID,
        *,
        reason: "ArchiveReason",
        retention: timedelta = timedelta(days=30),
        now: datetime | None = None,
    ) -> "DeckCopyResult":
        if retention <= timedelta(0):
            raise ValueError("Archive retention must be positive")

        source, deck_cards, cards = await self._lock_source_graph(source_deck_uuid)
        if source.state != "active":
            raise ValueError("Only active decks can be archived")

        reason = ArchiveReason(reason)
        if reason == ArchiveReason.MADE_PRIVATE and not source.is_public:
            raise ValueError("The source deck is already private")

        now = now or utcnow()
        target = Deck(
            user_id=None,
            state="archived",
            is_public=False,
            archived_at=now,
            expires_at=now + retention,
            archive_reason=reason.value,
            version=source.version,
        )
        return await self.create_copy(source, deck_cards, cards, target, now=now)

    async def create_private_copy(
        self,
        source_deck_uuid: UUID,
        *,
        owner_id: int,
    ) -> "DeckCopyResult":
        if owner_id <= 0:
            raise ValueError("The new deck owner must have a positive ID")

        source, deck_cards, cards = await self._lock_source_graph(source_deck_uuid)
        if source.state != "active":
            raise ValueError("Only active decks can be copied")
        if source.user_id != owner_id and not source.is_public:
            raise PermissionDeniedError()

        target = Deck(
            user_id=owner_id,
            state="active",
            is_public=False,
            version=1,
        )
        return await self.create_copy(source, deck_cards, cards, target, now=utcnow())

    @traced("decks.content_copier.create_copy")
    async def create_copy(
        self,
        source: Deck,
        deck_cards: list[DeckCard],
        cards: list[Card],
        target: Deck,
        *,
        now: datetime,
    ) -> "DeckCopyResult":
        source_card_ids = {deck_card.card_id for deck_card in deck_cards}
        if len(cards) != len(deck_cards) or {card.id for card in cards} != source_card_ids:
            raise ValueError("The deck links and cards do not match")

        target.source_deck_uuid_snapshot = source.uuid
        target.title = source.title
        target.description = source.description
        target.words_count = len(deck_cards)
        target.saves_count = 0
        target.created_at = target.updated_at = now
        self.uow.deck_repo.add(deck=target)
        await self.uow.flush()

        new_cards_by_source_id = {
            card.id: Card(
                user_id=target.user_id,
                learning_key=card.learning_key,
                front_text=card.front_text,
                back_text=card.back_text,
                front_lang=card.front_lang,
                back_lang=card.back_lang,
                created_at=now,
                updated_at=now,
            )
            for card in cards
        }
        self.uow.card_repo.add_all(cards=list(new_cards_by_source_id.values()))
        await self.uow.flush()

        new_deck_cards = [
            DeckCard(
                deck_id=target.id,
                card_id=new_cards_by_source_id[deck_card.card_id].id,
                position=deck_card.position,
            ) for deck_card in deck_cards
        ]
        self.uow.deck_card_repo.add_all(deck_cards=new_deck_cards)
        await self.uow.flush()

        return DeckCopyResult(
            deck=target,
            card_id_map={source_id: card.id for source_id, card in new_cards_by_source_id.items()},
            changes=ArchiveChanges(
                deck_ids={source.id, target.id},
                deck_uuids={source.uuid, target.uuid},
                card_ids=source_card_ids | {card.id for card in new_cards_by_source_id.values()},
                card_uuids={card.uuid for card in cards}
                | {card.uuid for card in new_cards_by_source_id.values()},
            ),
            source_deck=source,
        )

    async def create_archives_batch(
        self,
        graphs: list[tuple[Deck, list[DeckCard], list[Card]]],
        *,
        reason: "ArchiveReason",
        retention: timedelta,
        now: datetime,
    ) -> list["DeckCopyResult"]:
        if retention <= timedelta(0):
            raise ValueError("Archive retention must be positive")
        if not graphs:
            return []

        targets: list[Deck] = []
        new_cards_by_source: list[dict[int, Card]] = []
        source_card_ids_by_deck: list[set[int]] = []
        for source, links, cards in graphs:
            if source.state != "active" or not source.is_public:
                raise ValueError("Only active public decks can be batch archived")
            source_card_ids = {link.card_id for link in links}
            if len(cards) != len(links) or {card.id for card in cards} != source_card_ids:
                raise ValueError("The deck links and cards do not match")
            target = Deck(
                user_id=None,
                state="archived",
                is_public=False,
                archived_at=now,
                expires_at=now + retention,
                archive_reason=ArchiveReason(reason).value,
                source_deck_uuid_snapshot=source.uuid,
                title=source.title,
                description=source.description,
                words_count=len(links),
                saves_count=0,
                version=source.version,
                created_at=now,
                updated_at=now,
            )
            targets.append(target)
            new_cards_by_source.append({
                card.id: Card(
                    user_id=None,
                    learning_key=card.learning_key,
                    front_text=card.front_text,
                    back_text=card.back_text,
                    front_lang=card.front_lang,
                    back_lang=card.back_lang,
                    created_at=now,
                    updated_at=now,
                )
                for card in cards
            })
            source_card_ids_by_deck.append(source_card_ids)

        self.uow.deck_repo.add_all(targets)
        await self.uow.flush()
        self.uow.card_repo.add_all([
            card
            for card_map in new_cards_by_source
            for card in card_map.values()
        ])
        await self.uow.flush()
        self.uow.deck_card_repo.add_all([
            DeckCard(
                deck_id=target.id,
                card_id=card_map[link.card_id].id,
                position=link.position,
            )
            for (_, links, _), target, card_map in zip(
                graphs, targets, new_cards_by_source, strict=True,
            )
            for link in links
        ])
        await self.uow.flush()

        return [
            DeckCopyResult(
                deck=target,
                card_id_map={old_id: card.id for old_id, card in card_map.items()},
                changes=ArchiveChanges(
                    deck_ids={source.id, target.id},
                    deck_uuids={source.uuid, target.uuid},
                    card_ids=source_card_ids | {card.id for card in card_map.values()},
                    card_uuids={card.uuid for card in cards}
                    | {card.uuid for card in card_map.values()},
                ),
                source_deck=source,
            )
            for (source, _, cards), target, card_map, source_card_ids in zip(
                graphs, targets, new_cards_by_source, source_card_ids_by_deck,
                strict=True,
            )
        ]

class DeckTransferUserProgress:
    """Переносит историю и состояние пользователей после копирования колоды."""

    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    @traced("decks.progress.transfer")
    async def transfer(
        self,
        copied: DeckCopyResult,
        *,
        user_ids: Iterable[int] | None = None,
    ) -> ArchiveChanges:
        source = copied.source_deck
        target = copied.deck
        if source.id == target.id or target.source_deck_uuid_snapshot != source.uuid:
            raise ValueError("Target must be a copy of the source deck")
        if target.state not in {"active", "archived"}:
            raise ValueError("Unsupported target deck state")

        ids = tuple(sorted(set(user_ids))) if user_ids is not None else None
        if ids is not None and any(user_id <= 0 for user_id in ids):
            raise ValueError("User IDs must be positive")
        if target.state == "active":
            if ids is None:
                ids = (target.user_id,)
            elif ids and ids != (target.user_id,):
                raise ValueError("A private copy can only receive its owner's progress")
        if ids == ():
            return ArchiveChanges()

        if (
            await self.uow.training_session_repo.has_by_deck_id(target.id, None)
            or await self.uow.user_deck_repo.get_user_ids_by_deck_ids([target.id])
        ):
            raise DeckProgressConflictError("Target deck already has user progress")

        sessions = await self.uow.training_session_repo.lock_for_transfer(source.id, ids)
        items = await self.uow.training_session_item_repo.lock_for_transfer(
            [session.id for session in sessions]
        )
        states = await self.uow.user_deck_repo.lock_for_transfer(source.id, ids)
        affected_user_ids = {session.user_id for session in sessions} | {
            state.user_id for state in states
        }
        if not affected_user_ids:
            return ArchiveChanges()

        new_cards = await self.uow.card_repo.get_by_ids(
            list(copied.card_id_map.values())
        )
        if {card.id for card in new_cards} != set(copied.card_id_map.values()):
            raise ValueError("Copied cards are missing")
        card_ids_by_learning_key: dict[UUID, set[int]] = {}
        for card in new_cards:
            card_ids_by_learning_key.setdefault(card.learning_key, set()).add(card.id)

        used_card_ids_by_session: dict[int, set[int]] = {}
        for item in items:
            mapped_by_id = copied.card_id_map.get(item.original_card_id)
            if item.learning_key_snapshot is None:
                new_card_id = mapped_by_id
            else:
                candidates = card_ids_by_learning_key.get(
                    item.learning_key_snapshot, set()
                )
                if mapped_by_id in candidates:
                    new_card_id = mapped_by_id
                elif len(candidates) == 1:
                    new_card_id = next(iter(candidates))
                else:
                    new_card_id = None

            used_ids = used_card_ids_by_session.setdefault(item.training_session_id, set())
            if new_card_id in used_ids:
                new_card_id = None
            if new_card_id is not None:
                used_ids.add(new_card_id)
            item.original_card_id = new_card_id

        sessions_by_user: dict[int, list[TrainingSession]] = {}
        for session in sessions:
            sessions_by_user.setdefault(session.user_id, []).append(session)
            session.deck_id = target.id

        existing_state_users = {state.user_id for state in states}
        for state in states:
            state.deck_id = target.id
            if target.state == "active":
                state.is_saved = False
                state.last_seen_version = target.version

        for user_id, user_sessions in sessions_by_user.items():
            if user_id in existing_state_users:
                continue
            completed = [
                session for session in user_sessions
                if session.status == TrainingSessionStatus.COMPLETED
                and session.finished_at is not None
            ]
            self.uow.user_deck_repo.add(UserDeck(
                user_id=user_id,
                deck_id=target.id,
                sessions_count=len(completed),
                correct_count=sum(session.correct_count for session in completed),
                wrong_count=sum(session.wrong_count for session in completed),
                last_studied_at=(
                    max(session.finished_at for session in completed)
                    if completed else None
                ),
                added_at=min(session.started_at for session in user_sessions),
                is_saved=False,
                is_favourite=False,
                last_seen_version=(target.version if target.state == "active" else None),
            ))

        await self.uow.flush()
        source.saves_count = (
            await self.uow.user_deck_repo.count_saved(source.id)
            if source.state == "active" else 0
        )
        target.saves_count = 0
        await self.uow.flush()
        return ArchiveChanges(
            deck_ids={source.id, target.id},
            deck_uuids={source.uuid, target.uuid},
            user_ids=affected_user_ids,
            user_deck_keys={
                make_user_deck_identity(user_id=user_id, deck_id=deck_id)
                for user_id in affected_user_ids
                for deck_id in (source.id, target.id)
            },
        )


class ArchiveReason(StrEnum):
    DELETED = "deleted"
    OWNER_DELETED = "owner_deleted"
    MADE_PRIVATE = "made_private"


class ArchiveExpiredError(Exception):
    pass


class DeckProgressConflictError(Exception):
    pass


@dataclass
class ArchiveChanges:
    """Ключи для кешей колод, карточек, библиотек, истории и статистики."""

    deck_ids: set[int] = field(default_factory=set)
    deck_uuids: set[UUID] = field(default_factory=set)
    card_ids: set[int] = field(default_factory=set)
    card_uuids: set[UUID] = field(default_factory=set)
    user_ids: set[int] = field(default_factory=set)
    user_deck_keys: set[tuple[int, int]] = field(default_factory=set)

    def include(self, other: "ArchiveChanges") -> None:
        self.deck_ids.update(other.deck_ids)
        self.deck_uuids.update(other.deck_uuids)
        self.card_ids.update(other.card_ids)
        self.card_uuids.update(other.card_uuids)
        self.user_ids.update(other.user_ids)
        self.user_deck_keys.update(other.user_deck_keys)


@dataclass
class DeckCopyResult:
    deck: Deck
    card_id_map: dict[int, int]
    changes: ArchiveChanges
    source_deck: Deck


@dataclass
class DeckArchiveResult:
    archive: Deck | None
    recipient_ids: tuple[int, ...]
    changes: ArchiveChanges


@dataclass
class DeckArchiveBatchResult:
    archives: list[DeckArchiveResult]
    recipient_ids: tuple[int, ...]
    changes: ArchiveChanges


@dataclass
class DeckPreservationResult:
    deck_id: int | None
    deck_uuid: UUID
    already_preserved: bool
    copy_deleted: bool
    changes: ArchiveChanges


class DeckArchiveWorkflow:
    """Собирает архивирование и восстановление в одном открытом UoW.

    Вызывающий сервис проверяет право владельца и делает commit. Блокировки
    колоды и получателя удерживаются до конца транзакции.
    """

    def __init__(
        self,
        uow: UnitOfWork,
        *,
        retention: timedelta = timedelta(days=30),
        clock: Callable[[], datetime] = utcnow,
    ):
        if retention <= timedelta(0):
            raise ValueError("Archive retention must be positive")
        self.uow = uow
        self.retention = retention
        self.clock = clock
        self.copier = DeckContentCopier(uow)
        self.progress = DeckTransferUserProgress(uow)

    @traced("decks.archiver.archive_deck")
    async def archive_deck(
        self,
        source_deck_uuid: UUID,
        *,
        reason: ArchiveReason,
    ) -> DeckArchiveResult:
        reason = ArchiveReason(reason)
        source, _, _ = await self.copier._lock_source_graph(source_deck_uuid)
        if source.state != "active":
            raise ValueError("Only active decks can be archived")
        if reason == ArchiveReason.MADE_PRIVATE and not source.is_public:
            raise ValueError("The source deck is already private")

        recipients = set(
            await self.uow.user_deck_repo.get_archive_recipient_user_ids(source.id)
        )
        recipients.update(
            await self.uow.training_session_repo.get_user_ids_by_deck_id(source.id)
        )
        if reason != ArchiveReason.DELETED:
            recipients.discard(source.user_id)
        recipient_ids = tuple(sorted(recipients))
        changes = ArchiveChanges(
            deck_ids={source.id},
            deck_uuids={source.uuid},
            user_ids={source.user_id} if source.user_id is not None else set(),
        )
        if not recipient_ids:
            return DeckArchiveResult(None, (), changes)

        copied = await self.copier.create_archive(
            source_deck_uuid,
            reason=reason,
            retention=self.retention,
            now=self.clock(),
        )
        self.uow.deck_repo.add_archive_recipients([
            DeckArchiveRecipient(
                archive_deck_id=copied.deck.id, user_id=user_id,
            )
            for user_id in recipient_ids
        ])
        changes.include(copied.changes)
        changes.include(await self.progress.transfer(copied, user_ids=recipient_ids))
        await self.uow.flush()
        return DeckArchiveResult(copied.deck, recipient_ids, changes)

    async def archive_owner_public_decks(
        self, owner_id: int,
    ) -> DeckArchiveBatchResult:
        """Пакетный снимок публичных колод перед удалением владельца."""
        if owner_id <= 0:
            raise ValueError("Owner ID must be positive")
        graphs = await self.uow.deck_repo.lock_owned_public_deck_graphs(owner_id)
        if not graphs:
            return DeckArchiveBatchResult([], (), ArchiveChanges())

        deck_ids = [source.id for source, _, _ in graphs]
        recipients_by_deck = {deck_id: set() for deck_id in deck_ids}
        for deck_id, user_id in (
            await self.uow.user_deck_repo.get_archive_recipient_pairs(deck_ids)
        ):
            if user_id != owner_id:
                recipients_by_deck[deck_id].add(user_id)
        for deck_id, user_id in (
            await self.uow.training_session_repo.get_archive_recipient_pairs(deck_ids)
        ):
            if user_id != owner_id:
                recipients_by_deck[deck_id].add(user_id)

        eligible = [
            graph for graph in graphs if recipients_by_deck[graph[0].id]
        ]
        if not eligible:
            return DeckArchiveBatchResult([], (), ArchiveChanges())

        copied_decks = await self.copier.create_archives_batch(
            eligible,
            reason=ArchiveReason.OWNER_DELETED,
            retention=self.retention,
            now=self.clock(),
        )
        recipients = [
            DeckArchiveRecipient(
                archive_deck_id=copied.deck.id, user_id=user_id,
            )
            for copied in copied_decks
            for user_id in sorted(recipients_by_deck[copied.source_deck.id])
        ]
        self.uow.deck_repo.add_archive_recipients(recipients)

        results: list[DeckArchiveResult] = []
        changes = ArchiveChanges()
        affected_users: set[int] = set()
        for copied in copied_decks:
            ids = tuple(sorted(recipients_by_deck[copied.source_deck.id]))
            deck_changes = copied.changes
            deck_changes.include(await self.progress.transfer(copied, user_ids=ids))
            results.append(DeckArchiveResult(copied.deck, ids, deck_changes))
            changes.include(deck_changes)
            affected_users.update(ids)
        await self.uow.flush()
        return DeckArchiveBatchResult(
            results, tuple(sorted(affected_users)), changes,
        )

    async def delete_deck(self, source_deck_uuid: UUID) -> DeckArchiveResult:
        result = await self.archive_deck(
            source_deck_uuid, reason=ArchiveReason.DELETED,
        )
        source = await self.uow.deck_repo.get_by_uuid(source_deck_uuid)
        await self.uow.deck_repo.delete(source)
        await self.uow.flush()
        return result

    async def make_private(self, source_deck_uuid: UUID) -> DeckArchiveResult:
        result = await self.archive_deck(
            source_deck_uuid, reason=ArchiveReason.MADE_PRIVATE,
        )
        source = await self.uow.deck_repo.get_by_uuid(source_deck_uuid)
        source.is_public = False
        source.saves_count = await self.uow.user_deck_repo.count_saved(source.id)
        await self.uow.flush()
        return result

    @traced("decks.archiver.preserve")
    async def preserve(
        self, archive_deck_uuid: UUID, *, user_id: int,
    ) -> DeckPreservationResult:
        if user_id <= 0:
            raise ValueError("User ID must be positive")
        archive, deck_cards, cards = await self.copier._lock_source_graph(
            archive_deck_uuid
        )
        if archive.state != "archived":
            raise DeckNotFoundError()
        recipient = await self.uow.deck_repo.get_archive_recipient_for_update(
            archive_deck_id=archive.id, user_id=user_id,
        )
        if (
            recipient is None
            or recipient.archive_deck_id != archive.id
            or recipient.user_id != user_id
        ):
            raise PermissionDeniedError()

        if recipient.preserved_at is not None:
            return DeckPreservationResult(
                recipient.preserved_deck_id,
                recipient.preserved_deck_uuid_snapshot,
                already_preserved=True,
                copy_deleted=recipient.preserved_deck_id is None,
                changes=ArchiveChanges(),
            )

        now = self.clock()
        if archive.expires_at is None or now >= archive.expires_at:
            raise ArchiveExpiredError("Archive preservation period has expired")
        target = Deck(
            user_id=user_id, state="active", is_public=False, version=1,
        )
        copied = await self.copier.create_copy(
            archive, deck_cards, cards, target, now=now,
        )
        changes = copied.changes
        changes.include(await self.progress.transfer(copied, user_ids=(user_id,)))
        recipient.preserved_at = now
        recipient.preserved_deck_id = copied.deck.id
        recipient.preserved_deck_uuid_snapshot = copied.deck.uuid
        await self.uow.flush()
        return DeckPreservationResult(
            copied.deck.id, copied.deck.uuid,
            already_preserved=False, copy_deleted=False, changes=changes,
        )
