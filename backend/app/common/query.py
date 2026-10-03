from datetime import datetime

from sqlalchemy import Select, and_, or_
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement


def apply_search[T: tuple](
    stmt: Select[T],
    query: str | None,
    *columns: InstrumentedAttribute[str] | ColumnElement[str],
) -> Select[T]:
    """Require every search term to match at least one of the given columns."""
    if not columns:
        raise ValueError("Search requires at least one column")

    for term in (query or "").split():
        stmt = stmt.where(
            or_(*(column.icontains(term, autoescape=True) for column in columns))
        )
    return stmt


def apply_date_pagination[T: tuple](
    stmt: Select[T],
    *,
    date_column: (
        InstrumentedAttribute[datetime]
        | InstrumentedAttribute[datetime | None]
        | ColumnElement[datetime]
        | ColumnElement[datetime | None]
    ),
    id_column: InstrumentedAttribute[int] | ColumnElement[int],
    cursor_at: datetime | None,
    cursor_id: int | None,
    limit: int,
) -> Select[T]:
    """Order by date/id descending and fetch one extra row.

    A complete cursor is required to apply the boundary. Nullable dates need
    filtering in the caller or a separate pagination policy.
    """
    if cursor_at is not None and cursor_id is not None:
        stmt = stmt.where(
            or_(
                date_column < cursor_at,
                and_(date_column == cursor_at, id_column < cursor_id),
            )
        )

    return (
        stmt.order_by(None)
        .order_by(date_column.desc(), id_column.desc())
        .limit(limit + 1)
    )
