import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid7

from app.database import Base
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.decks.models import DeckCard
    from app.users.models import User

class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        server_default=text("uuidv7()"),
        unique=True,
        nullable=False,
        index=True
    )
    learning_key: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid7,
        server_default=text("uuidv7()"),
        nullable=False,
    )

    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    front_text: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    back_text: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    front_lang: Mapped[str] = mapped_column(
        String(3),
        default="ru",
        server_default="ru",
        nullable=False,
        )
    back_lang: Mapped[str] = mapped_column(
        String(3), 
        default="en",
        server_default="en",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User | None"] = relationship("User", back_populates="cards", lazy="raise")
    deck_links: Mapped[list["DeckCard"]] = relationship(
        "DeckCard",
        back_populates="card", 
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )

    __table_args__ = (
        CheckConstraint("id > 0", name="ck_cards_id_positive"),
        CheckConstraint("user_id > 0", name="ck_cards_user_id_positive"),
        CheckConstraint(
            "substring(uuid::text from 15 for 1) = '7' "
            "AND substring(uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')",
            name="ck_cards_uuid_v7",
        ),
        CheckConstraint(
            "substring(learning_key::text from 15 for 1) = '7' "
            "AND substring(learning_key::text from 20 for 1) IN ('8', '9', 'a', 'b')",
            name="ck_cards_learning_key_v7",
        ),
        CheckConstraint("updated_at >= created_at", name="ck_cards_dates_order"),
        CheckConstraint(
            "front_lang ~ '^[a-z]{2,3}$' AND char_length(front_lang) BETWEEN 2 AND 3",
            name="ck_cards_front_lang_format",
        ),
        CheckConstraint(
            "back_lang ~ '^[a-z]{2,3}$' AND char_length(back_lang) BETWEEN 2 AND 3",
            name="ck_cards_back_lang_format",
        ),
        CheckConstraint(
            "char_length(front_text) BETWEEN 1 AND 255",
            name="ck_cards_front_text_length",
        ),
        CheckConstraint(
            "char_length(back_text) BETWEEN 1 AND 255",
            name="ck_cards_back_text_length",
        ),
        CheckConstraint(
            "front_text = btrim(front_text, U&'\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')",
            name="ck_cards_front_text_trimmed",
        ),
        CheckConstraint(
            "back_text = btrim(back_text, U&'\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')",
            name="ck_cards_back_text_trimmed",
        ),
    )
