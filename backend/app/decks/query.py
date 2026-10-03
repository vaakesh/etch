from sqlalchemy import Select, and_, or_

from app.decks.models import Deck, UserDeck
from app.decks.schemas import LibraryCursor


def apply_library_pagination[T: tuple](
    stmt: Select[T],
    *,
    cursor: LibraryCursor | None,
    limit: int,
) -> Select[T]:
    """Order studied decks first, then by added date and unique deck ID."""
    if cursor is not None:
        if cursor.last_studied_at is not None:
            stmt = stmt.where(
                or_(
                    UserDeck.last_studied_at < cursor.last_studied_at,

                    and_(
                        UserDeck.last_studied_at == cursor.last_studied_at,
                        UserDeck.added_at < cursor.added_at,
                    ),

                    and_(
                        UserDeck.last_studied_at == cursor.last_studied_at,
                        UserDeck.added_at == cursor.added_at,
                        Deck.id < cursor.id,
                    ),

                    UserDeck.last_studied_at.is_(None),
                )
            )
        else:
            stmt = stmt.where(
                and_(
                    UserDeck.last_studied_at.is_(None),
                    or_(
                        UserDeck.added_at < cursor.added_at,
                        and_(
                            UserDeck.added_at == cursor.added_at,
                            Deck.id < cursor.id,
                        )
                    )
                )
            )

    stmt = stmt.order_by(
        UserDeck.last_studied_at.desc().nulls_last(),
        UserDeck.added_at.desc(),
        Deck.id.desc(),
    ).limit(limit + 1)

    return stmt
