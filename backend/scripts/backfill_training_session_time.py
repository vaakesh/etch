"""Backfill approximate active study time for legacy training sessions.

Run from the backend directory. Without ``--apply`` the command only calculates
and prints a report; it does not update the database.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.database import get_engine

DEFAULT_BATCH_SIZE = 500
DEFAULT_PAUSE_SECONDS = 0.25
MAX_INTERVAL_MS = 120_000

PREFLIGHT_SQL = text(
    """
    SELECT
        COALESCE(
            MAX(id) FILTER (WHERE finished_at IS NOT NULL),
            :after_id
        ) AS snapshot_max_id,
        COUNT(*) FILTER (WHERE finished_at IS NOT NULL) AS eligible_sessions,
        COUNT(*) FILTER (WHERE finished_at IS NULL) AS missing_finished_at_sessions
    FROM training_sessions
    WHERE status = 'completed'
      AND active_study_time_ms = 0
      AND id > :after_id
    """
)

CALCULATION_CTES = """
    WITH batch_sessions AS MATERIALIZED (
        SELECT
            id,
            started_at,
            finished_at
        FROM training_sessions
        WHERE status = 'completed'
          AND active_study_time_ms = 0
          AND finished_at IS NOT NULL
          AND id > :after_id
          AND id <= :snapshot_max_id
        ORDER BY id
        LIMIT :batch_size
    ),
    item_quality AS (
        SELECT
            bs.id AS session_id,
            COUNT(tsi.id) FILTER (
                WHERE tsi.answered_at IS NULL
            ) AS null_answered_at_count,
            COUNT(tsi.id) FILTER (
                WHERE tsi.answered_at IS NOT NULL
                  AND tsi.answered_at < bs.started_at
            ) AS before_started_at_count,
            COUNT(tsi.id) FILTER (
                WHERE tsi.answered_at IS NOT NULL
                  AND tsi.answered_at > bs.finished_at
            ) AS after_finished_at_count,
            COUNT(tsi.id) FILTER (
                WHERE tsi.answered_at IS NOT NULL
                  AND tsi.answered_at >= bs.started_at
                  AND tsi.answered_at <= bs.finished_at
            ) AS valid_answer_count
        FROM batch_sessions AS bs
        LEFT JOIN training_session_items AS tsi
          ON tsi.training_session_id = bs.id
        GROUP BY bs.id
    ),
    valid_answers AS (
        SELECT
            bs.id AS session_id,
            bs.started_at,
            tsi.id AS item_id,
            tsi.answered_at
        FROM batch_sessions AS bs
        JOIN training_session_items AS tsi
          ON tsi.training_session_id = bs.id
        WHERE tsi.answered_at IS NOT NULL
          AND tsi.answered_at >= bs.started_at
          AND tsi.answered_at <= bs.finished_at
    ),
    ordered_answers AS (
        SELECT
            session_id,
            started_at,
            answered_at,
            LAG(answered_at) OVER (
                PARTITION BY session_id
                ORDER BY answered_at, item_id
            ) AS previous_answered_at
        FROM valid_answers
    ),
    intervals AS (
        SELECT
            session_id,
            FLOOR(
                EXTRACT(
                    EPOCH FROM (
                        answered_at
                        - COALESCE(previous_answered_at, started_at)
                    )
                ) * 1000
            )::bigint AS raw_interval_ms
        FROM ordered_answers
    ),
    session_times AS (
        SELECT
            bs.id AS session_id,
            COALESCE(
                SUM(
                    LEAST(i.raw_interval_ms, :max_interval_ms)
                ) FILTER (WHERE i.raw_interval_ms IS NOT NULL),
                0
            )::bigint AS calculated_time_ms,
            COUNT(i.raw_interval_ms) FILTER (
                WHERE i.raw_interval_ms > :max_interval_ms
            ) AS capped_interval_count
        FROM batch_sessions AS bs
        LEFT JOIN intervals AS i
          ON i.session_id = bs.id
        GROUP BY bs.id
    ),
    session_results AS (
        SELECT
            st.session_id,
            st.calculated_time_ms,
            st.capped_interval_count,
            iq.valid_answer_count,
            iq.null_answered_at_count,
            iq.before_started_at_count,
            iq.after_finished_at_count
        FROM session_times AS st
        JOIN item_quality AS iq
          ON iq.session_id = st.session_id
    )
"""

DRY_RUN_BATCH_SQL = text(
    CALCULATION_CTES
    + """
    SELECT
        session_id,
        calculated_time_ms,
        capped_interval_count,
        valid_answer_count,
        null_answered_at_count,
        before_started_at_count,
        after_finished_at_count,
        FALSE AS was_updated
    FROM session_results
    ORDER BY session_id
    """
)

APPLY_BATCH_SQL = text(
    CALCULATION_CTES
    + """,
    updated_sessions AS (
        UPDATE training_sessions AS ts
        SET active_study_time_ms = sr.calculated_time_ms
        FROM session_results AS sr
        WHERE ts.id = sr.session_id
          AND ts.status = 'completed'
          AND ts.active_study_time_ms = 0
        RETURNING ts.id AS session_id
    )
    SELECT
        sr.session_id,
        sr.calculated_time_ms,
        sr.capped_interval_count,
        sr.valid_answer_count,
        sr.null_answered_at_count,
        sr.before_started_at_count,
        sr.after_finished_at_count,
        (us.session_id IS NOT NULL) AS was_updated
    FROM session_results AS sr
    LEFT JOIN updated_sessions AS us
      ON us.session_id = sr.session_id
    ORDER BY sr.session_id
    """
)


@dataclass(slots=True)
class BackfillStats:
    selected_sessions: int = 0
    updated_sessions: int = 0
    valid_answers: int = 0
    null_answered_at: int = 0
    before_started_at: int = 0
    after_finished_at: int = 0
    capped_intervals: int = 0
    sessions_without_valid_answers: int = 0
    zero_time_sessions: int = 0
    total_time_ms: int = 0
    minimum_time_ms: int | None = None
    maximum_time_ms: int | None = None

    def add_rows(self, rows: list[RowMapping]) -> None:
        for row in rows:
            calculated_time_ms = int(row["calculated_time_ms"])
            valid_answer_count = int(row["valid_answer_count"])

            self.selected_sessions += 1
            self.updated_sessions += int(bool(row["was_updated"]))
            self.valid_answers += valid_answer_count
            self.null_answered_at += int(row["null_answered_at_count"])
            self.before_started_at += int(row["before_started_at_count"])
            self.after_finished_at += int(row["after_finished_at_count"])
            self.capped_intervals += int(row["capped_interval_count"])
            self.sessions_without_valid_answers += int(valid_answer_count == 0)
            self.zero_time_sessions += int(calculated_time_ms == 0)
            self.total_time_ms += calculated_time_ms

            if (
                self.minimum_time_ms is None
                or calculated_time_ms < self.minimum_time_ms
            ):
                self.minimum_time_ms = calculated_time_ms
            if (
                self.maximum_time_ms is None
                or calculated_time_ms > self.maximum_time_ms
            ):
                self.maximum_time_ms = calculated_time_ms


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill active_study_time_ms for completed legacy training "
            "sessions. The default mode is read-only."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist calculated values. Without this flag only a report is built.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Sessions per transaction (default: {DEFAULT_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--after-id",
        type=int,
        default=0,
        help="Process only training sessions with id greater than this value.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=DEFAULT_PAUSE_SECONDS,
        help=(
            "Pause between committed batches "
            f"(default: {DEFAULT_PAUSE_SECONDS})."
        ),
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Stop after this number of batches; useful for a canary run.",
    )

    args = parser.parse_args(argv)
    if args.batch_size <= 0:
        parser.error("--batch-size must be greater than zero")
    if args.after_id < 0:
        parser.error("--after-id must not be negative")
    if args.pause_seconds < 0:
        parser.error("--pause-seconds must not be negative")
    if args.max_batches is not None and args.max_batches <= 0:
        parser.error("--max-batches must be greater than zero")
    return args


async def get_preflight(
    engine: AsyncEngine,
    after_id: int,
) -> RowMapping:
    async with engine.connect() as connection:
        result = await connection.execute(PREFLIGHT_SQL, {"after_id": after_id})
        return result.mappings().one()


async def process_batch(
    engine: AsyncEngine,
    *,
    apply: bool,
    after_id: int,
    snapshot_max_id: int,
    batch_size: int,
) -> list[RowMapping]:
    statement = APPLY_BATCH_SQL if apply else DRY_RUN_BATCH_SQL
    parameters = {
        "after_id": after_id,
        "snapshot_max_id": snapshot_max_id,
        "batch_size": batch_size,
        "max_interval_ms": MAX_INTERVAL_MS,
    }
    async with engine.begin() as connection:
        result = await connection.execute(statement, parameters)
        return list(result.mappings().all())


def format_duration(milliseconds: int | None) -> str:
    if milliseconds is None:
        return "n/a"
    return f"{milliseconds / 1000:.3f}s"


def print_report(
    stats: BackfillStats,
    *,
    apply: bool,
    eligible_sessions: int,
    missing_finished_at_sessions: int,
    last_processed_id: int,
) -> None:
    average_time_ms = (
        stats.total_time_ms // stats.selected_sessions
        if stats.selected_sessions
        else None
    )
    print("\nBackfill report")
    print(f"  mode: {'APPLY' if apply else 'DRY RUN'}")
    print(f"  eligible sessions at snapshot: {eligible_sessions}")
    print(f"  selected sessions: {stats.selected_sessions}")
    if apply:
        print(f"  updated sessions: {stats.updated_sessions}")
    print(
        "  completed sessions missing finished_at (skipped): "
        f"{missing_finished_at_sessions}"
    )
    print(f"  valid answers: {stats.valid_answers}")
    print(f"  answers with NULL answered_at (skipped): {stats.null_answered_at}")
    print(f"  answers before started_at (skipped): {stats.before_started_at}")
    print(f"  answers after finished_at (skipped): {stats.after_finished_at}")
    print(f"  intervals capped at 120 seconds: {stats.capped_intervals}")
    print(
        "  sessions without valid answers: "
        f"{stats.sessions_without_valid_answers}"
    )
    print(f"  sessions with calculated zero time: {stats.zero_time_sessions}")
    print(f"  total calculated time: {format_duration(stats.total_time_ms)}")
    print(f"  minimum session time: {format_duration(stats.minimum_time_ms)}")
    print(f"  average session time: {format_duration(average_time_ms)}")
    print(f"  maximum session time: {format_duration(stats.maximum_time_ms)}")
    print(f"  last processed session id: {last_processed_id}")


async def run(args: argparse.Namespace) -> int:
    engine = get_engine()
    stats = BackfillStats()
    cursor = args.after_id

    try:
        preflight = await get_preflight(engine, after_id=args.after_id)
        snapshot_max_id = int(preflight["snapshot_max_id"])
        eligible_sessions = int(preflight["eligible_sessions"])
        missing_finished_at_sessions = int(
            preflight["missing_finished_at_sessions"]
        )

        print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
        print(f"Snapshot maximum session id: {snapshot_max_id}")
        print(f"Eligible sessions: {eligible_sessions}")
        print(f"Batch size: {args.batch_size}")

        batch_number = 0
        while cursor < snapshot_max_id:
            rows = await process_batch(
                engine,
                apply=args.apply,
                after_id=cursor,
                snapshot_max_id=snapshot_max_id,
                batch_size=args.batch_size,
            )
            if not rows:
                break

            batch_number += 1
            stats.add_rows(rows)
            cursor = max(int(row["session_id"]) for row in rows)
            updated_in_batch = sum(bool(row["was_updated"]) for row in rows)
            print(
                f"Batch {batch_number}: selected={len(rows)}, "
                f"updated={updated_in_batch}, resume_after_id={cursor}",
                flush=True,
            )

            if args.max_batches is not None and batch_number >= args.max_batches:
                print("Stopped because --max-batches was reached.")
                break
            if args.pause_seconds:
                await asyncio.sleep(args.pause_seconds)

        print_report(
            stats,
            apply=args.apply,
            eligible_sessions=eligible_sessions,
            missing_finished_at_sessions=missing_finished_at_sessions,
            last_processed_id=cursor,
        )
        if cursor < snapshot_max_id:
            print(f"Resume with: --after-id {cursor}")
        elif not args.apply:
            print("Dry run completed. Re-run with --apply to persist these values.")
        return 0
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nInterrupted. Use the last printed resume_after_id to continue.")
        return 130
    except SQLAlchemyError as exc:
        print(f"Database error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
