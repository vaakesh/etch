from typing import TYPE_CHECKING
import uuid
from datetime import datetime

from app.database import Base
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.limits import MAX_DECK_SIZE
from app.common.utils import utcnow
if TYPE_CHECKING:
    from app.cards.models import Card
    from app.users.models import User
    from app.training_sessions.models import TrainingSession


class Deck(Base):
    __tablename__ = "decks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        server_default=text("uuidv7()"),
        unique=True,
        nullable=False,
        index=True,
    )

    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )

    state: Mapped[str] = mapped_column(
        String(8),
        default="active",
        server_default=text("'active'"),
        nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    archive_reason: Mapped[str | None] = mapped_column(String(13), nullable=True)
    source_deck_uuid_snapshot: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    words_count: Mapped[int] = mapped_column(
        Integer, 
        default=0,
        server_default="0",
        nullable=False,
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, 
        default=False,
        server_default=text("false"),
        nullable=False,
    )

    saves_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
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
        nullable=False,
    )

    user: Mapped["User | None"] = relationship("User", back_populates="decks", lazy="raise")
    card_links: Mapped[list["DeckCard"]] = relationship(
        "DeckCard", 
        back_populates="deck", 
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
    )
    archive_recipients: Mapped[list["DeckArchiveRecipient"]] = relationship(
        "DeckArchiveRecipient",
        foreign_keys="DeckArchiveRecipient.archive_deck_id",
        back_populates="archive_deck",
        passive_deletes="all",
        lazy="raise",
    )
    training_sessions: Mapped[list["TrainingSession"]] = relationship(
        "TrainingSession", 
        back_populates="deck",
        passive_deletes="all",
        lazy="raise",
    )

    @property
    def owner_uuid(self) -> uuid.UUID | None:
        return self.user.uuid if self.user is not None else None

    @property
    def owner_username(self) -> str | None:
        return self.user.username if self.user is not None else None

    def mark_content_changed(self) -> None:
        self.version += 1
        self.updated_at = utcnow()

    __table_args__ = (
        CheckConstraint("id > 0", name="ck_deck_id_positive"),
        CheckConstraint("user_id > 0", name="ck_deck_user_id_positive"),
        CheckConstraint("state IN ('active', 'archived')", name="ck_deck_state"),
        CheckConstraint(
            "archive_reason IS NULL OR archive_reason IN "
            "('deleted', 'owner_deleted', 'made_private')",
            name="ck_deck_archive_reason",
        ),
        CheckConstraint(
            "(state = 'active' AND user_id IS NOT NULL "
            "AND archived_at IS NULL AND expires_at IS NULL "
            "AND archive_reason IS NULL) OR "
            "(state = 'archived' AND user_id IS NULL AND is_public = false "
            "AND archived_at IS NOT NULL AND expires_at IS NOT NULL "
            "AND archive_reason IS NOT NULL AND expires_at > archived_at)",
            name="ck_deck_archive_lifecycle",
        ),
        CheckConstraint(
            "source_deck_uuid_snapshot IS NULL OR "
            "(substring(source_deck_uuid_snapshot::text from 15 for 1) = '7' "
            "AND substring(source_deck_uuid_snapshot::text from 20 for 1) "
            "IN ('8', '9', 'a', 'b'))",
            name="ck_deck_source_uuid_snapshot_v7",
        ),
        CheckConstraint(
            "substring(uuid::text from 15 for 1) = '7' "
            "AND substring(uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')",
            name="ck_deck_uuid_v7",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="ck_deck_dates_order",
        ),
        CheckConstraint(
            "saves_count >= 0",
            name="ck_deck_saves_count_ge_0",
        ),
        CheckConstraint(
            "words_count >= 0",
            name="ck_deck_words_count_ge_0",
        ),
        CheckConstraint(
            f"words_count <= {MAX_DECK_SIZE}",
            name="ck_deck_words_count_le_max",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_deck_version_ge_1",
        ),
        CheckConstraint(
            'char_length(title) BETWEEN 3 AND 50',
            name="ck_deck_title_length",
        ),
        CheckConstraint(
            "title = btrim(title, U&'\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')",
            name="ck_deck_title_trimmed",
        ),
        CheckConstraint(
            "title = translate(title, U&'\\0009\\000A\\000B\\000C\\000D\\0085\\2028\\2029', '')",
            name="ck_deck_title_single_line",
        ),
        CheckConstraint(
            'description IS NULL OR char_length(description) BETWEEN 1 AND 3000',
            name="ck_deck_description_length",
        ),
        CheckConstraint(
            "description IS NULL OR description = btrim(description, U&'\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')",
            name="ck_deck_description_trimmed",
        ),
        Index(
            "ix_decks_archived_expires_at_id",
            "expires_at",
            "id",
            postgresql_where=text("state = 'archived'"),
        ),
    )


class DeckCard(Base):
    __tablename__ = "deck_cards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        server_default=text("uuidv7()"),
        unique=True,
        nullable=False,
        index=True
    )

    deck_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("decks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    card_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("cards.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
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

    deck: Mapped["Deck"] = relationship("Deck", back_populates="card_links", lazy="raise")
    card: Mapped["Card"] = relationship("Card", back_populates="deck_links", lazy="raise")

    __table_args__ = (
        UniqueConstraint("deck_id", "card_id", name="uq_deck_card"),
        CheckConstraint("id > 0", name="ck_deck_cards_id_positive"),
        CheckConstraint("deck_id > 0", name="ck_deck_cards_deck_id_positive"),
        CheckConstraint("card_id > 0", name="ck_deck_cards_card_id_positive"),
        CheckConstraint(
            "substring(uuid::text from 15 for 1) = '7' "
            "AND substring(uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')",
            name="ck_deck_cards_uuid_v7",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="ck_deck_cards_dates_order",
        ),
        CheckConstraint(
            "position >= 1",
            name="ck_deck_cards_position_ge_1",
        ),
        CheckConstraint(
            f"position <= {MAX_DECK_SIZE}",
            name="ck_deck_cards_position_le_max",
        ),
        UniqueConstraint(
            "deck_id",
            "position",
            name="uq_deck_cards_deck_position",
            deferrable=True,
            initially="DEFERRED",
        )
    )


class UserDeck(Base):
    __tablename__ = "user_decks"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    deck_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("decks.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )

    sessions_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )
    correct_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )
    wrong_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False,
    )
    last_studied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_favourite: Mapped[bool] = mapped_column(
        Boolean, 
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    is_saved: Mapped[bool] = mapped_column(
        Boolean,
        default=False, 
        server_default=text("false"),
        nullable=False,
    )

    last_seen_version: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("user_id > 0", name="ck_user_decks_user_id_positive"),
        CheckConstraint("deck_id > 0", name="ck_user_decks_deck_id_positive"),
        CheckConstraint(
            "sessions_count >= 0", name="ck_user_decks_sessions_count_ge_0",
        ),
        CheckConstraint(
            "correct_count >= 0", name="ck_user_decks_correct_count_ge_0",
        ),
        CheckConstraint(
            "wrong_count >= 0", name="ck_user_decks_wrong_count_ge_0",
        ),
        CheckConstraint(
            "sessions_count > 0 OR (correct_count = 0 AND wrong_count = 0)",
            name="ck_user_decks_answers_require_sessions",
        ),
        CheckConstraint(
            "(sessions_count = 0 AND last_studied_at IS NULL) OR "
            "(sessions_count > 0 AND last_studied_at IS NOT NULL)",
            name="ck_user_decks_study_matches_sessions",
        ),
        CheckConstraint(
            "last_studied_at IS NULL OR last_studied_at >= added_at",
            name="ck_user_decks_study_dates_order",
        ),
        Index("ix_user_decks_deck_id", "deck_id"),
    )


class DeckArchiveRecipient(Base):
    __tablename__ = "deck_archive_recipients"

    archive_deck_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("decks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    preserved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    preserved_deck_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("decks.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    preserved_deck_uuid_snapshot: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )

    archive_deck: Mapped["Deck"] = relationship(
        "Deck",
        foreign_keys=[archive_deck_id],
        back_populates="archive_recipients",
        lazy="raise",
    )
    preserved_deck: Mapped["Deck | None"] = relationship(
        "Deck", foreign_keys=[preserved_deck_id], lazy="raise",
    )
    user: Mapped["User"] = relationship("User", lazy="raise")

    __table_args__ = (
        CheckConstraint(
            "archive_deck_id > 0",
            name="ck_deck_archive_recipient_archive_deck_id_positive",
        ),
        CheckConstraint(
            "user_id > 0",
            name="ck_deck_archive_recipient_user_id_positive",
        ),
        CheckConstraint(
            "preserved_deck_id > 0",
            name="ck_deck_archive_recipient_preserved_deck_id_positive",
        ),
        CheckConstraint(
            "preserved_deck_id IS NULL OR preserved_deck_id <> archive_deck_id",
            name="ck_deck_archive_recipient_distinct_decks",
        ),
        CheckConstraint(
            "(preserved_at IS NULL AND preserved_deck_id IS NULL "
            "AND preserved_deck_uuid_snapshot IS NULL) OR "
            "(preserved_at IS NOT NULL "
            "AND preserved_deck_uuid_snapshot IS NOT NULL)",
            name="ck_deck_archive_recipient_preservation_state",
        ),
        CheckConstraint(
            "substring(preserved_deck_uuid_snapshot::text from 15 for 1) = '7' "
            "AND substring(preserved_deck_uuid_snapshot::text from 20 for 1) "
            "IN ('8', '9', 'a', 'b')",
            name="ck_deck_archive_recipient_preserved_uuid_v7",
        ),
        Index("ix_deck_archive_recipients_user_id", "user_id"),
    )
