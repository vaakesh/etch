import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.card_memory.replay import MemoryKey, replay_reviews
from app.card_memory.utils import SCHEDULER
from app.common.utils import utcnow
from app.fsrs.scheduler import Scheduler
from app.service import UnitOfWork
from app.tracing import traced

DEFAULT_BATCH_SIZE = 500


@dataclass(slots=True)
class RebuildStats:
    batches: int = 0
    keys: int = 0
    events: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0

    def merge(self, other: "RebuildStats") -> None:
        self.batches += other.batches
        self.keys += other.keys
        self.events += other.events
        self.created += other.created
        self.updated += other.updated
        self.unchanged += other.unchanged


@traced("card_memory.rebuild.rebuild_batch")
async def rebuild_batch(
    uow: UnitOfWork,
    keys: Sequence[MemoryKey],
    *,
    apply: bool,
    scheduler: Scheduler,
) -> RebuildStats:
    """Пересобирает состояния памяти для ключей из журнала ответов.

    Безопасно при работающем приложении: память блокируется до чтения журнала,
    как в rate_answer. Параллельный ответ либо уже в журнале, либо ждёт батч
    и применяется поверх пересобранного состояния.
    """
    stats = RebuildStats(batches=1, keys=len(keys))
    repo = uow.card_memory_repo

    # В dry run ничего не пишется, поэтому и блокировать нечего
    states = await repo.get_states(keys, for_update=apply)
    missing = [key for key in keys if key not in states]
    stats.created = len(missing)
    if apply and missing:
        await repo.create_missing(missing, now=utcnow())
        states |= await repo.get_states(missing, for_update=True)

    events = await repo.get_review_events_for_keys(keys)
    stats.events = len(events)
    cards = replay_reviews(events, scheduler)

    for key in keys:
        card = cards.get(key)
        state = states.get(key)
        # Журнал по ключу мог исчезнуть между страницами (удалён пользователь)
        if card is None or state is None:
            continue
        if key not in missing:
            if state.to_fsrs_card() == card:
                stats.unchanged += 1
                continue
            stats.updated += 1
        if apply:
            state.apply_fsrs_card(card)

    if apply:
        await uow.commit()
    else:
        await uow.rollback()
    return stats


async def rebuild_card_memory(
    uow_factory: Callable[[], UnitOfWork],
    *,
    apply: bool,
    batch_size: int = DEFAULT_BATCH_SIZE,
    pause_seconds: float = 0.0,
    max_batches: int | None = None,
    scheduler: Scheduler = SCHEDULER,
    on_batch: Callable[[RebuildStats], None] | None = None,
) -> RebuildStats:
    """Проходит все ключи журнала батчами, каждый батч в своей транзакции.

    Повторный запуск идемпотентен: синхронные состояния не меняются.
    """
    total = RebuildStats()
    after: MemoryKey | None = None

    while max_batches is None or total.batches < max_batches:
        async with uow_factory() as uow:
            keys = await uow.card_memory_repo.get_journal_keys(
                after=after,
                limit=batch_size,
            )
            if not keys:
                break
            batch = await rebuild_batch(
                uow,
                keys,
                apply=apply,
                scheduler=scheduler,
            )

        total.merge(batch)
        after = keys[-1]
        if on_batch is not None:
            on_batch(batch)
        if len(keys) < batch_size:
            break
        if pause_seconds:
            await asyncio.sleep(pause_seconds)

    return total
