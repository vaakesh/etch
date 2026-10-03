from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from app.database import Base
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as postgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.limits import MAX_SESSION_SIZE
from app.common.types import DeckTitle

if TYPE_CHECKING:
    from app.decks.models import Deck
    from app.users.models import User

type CardSide = Literal["front", "back"]

card_side_enum = SQLAlchemyEnum(
    "front",
    "back",
    name="card_side",
    native_enum=False,
    create_constraint=True,
)

class TrainingSessionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"

session_status_enum = SQLAlchemyEnum(
    TrainingSessionStatus,
    name="training_session_status",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum_class: [
        member.value for member in enum_class
    ],
)

class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[UUID] = mapped_column(
        postgresUUID(as_uuid=True),
        server_default=text("uuidv7()"),
        unique=True,
        nullable=False,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    deck_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("decks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    deck_title_snapshot: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    status: Mapped[TrainingSessionStatus] = mapped_column(
        session_status_enum,
        nullable=False,
        default=TrainingSessionStatus.IN_PROGRESS,
        server_default=TrainingSessionStatus.IN_PROGRESS.value,
        index=True,
    )

    requested_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    answered_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    correct_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    wrong_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        default=0,
    )

    prompt_side: Mapped[CardSide] = mapped_column(
        String(5),
        nullable=False,
        default="front",
        server_default="front",
    )
    answer_side: Mapped[CardSide] = mapped_column(
        String(5),
        nullable=False, 
        default="back",
        server_default="back",
    )

    active_study_time_ms: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    activity_last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    activity_tracker_uuid: Mapped[UUID | None] = mapped_column(
        postgresUUID(as_uuid=True),
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="training_sessions", lazy="raise")
    deck: Mapped["Deck | None"] = relationship("Deck", back_populates="training_sessions", lazy="raise")
    items: Mapped[list["TrainingSessionItem"]] = relationship(
        "TrainingSessionItem",
        back_populates="training_session",
        cascade="all, delete-orphan",
        order_by="TrainingSessionItem.sequence_number",
        passive_deletes=True,
        lazy="raise",
    )

    __table_args__ = (
        CheckConstraint("user_id > 0", name="ck_training_session_user_id_positive"),
        CheckConstraint("deck_id > 0", name="ck_training_session_deck_id_positive"),
        CheckConstraint(
            "deck_id IS NULL OR deck_title_snapshot IS NOT NULL",
            name="ck_training_session_deck_title_snapshot_present",
        ),
        CheckConstraint(
            "char_length(deck_title_snapshot) BETWEEN 3 AND 50",
            name="ck_training_session_deck_title_snapshot_length",
        ),
        CheckConstraint(
            "deck_title_snapshot = btrim(deck_title_snapshot, U&'\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')",
            name="ck_training_session_deck_title_snapshot_trimmed",
        ),
        CheckConstraint(
            "deck_title_snapshot = translate(deck_title_snapshot, U&'\\0009\\000A\\000B\\000C\\000D\\0085\\2028\\2029', '')",
            name="ck_training_session_deck_title_snapshot_single_line",
        ),
        CheckConstraint(
            "substring(uuid::text from 15 for 1) = '7' "
            "AND substring(uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')",
            name="ck_training_session_uuid_v7",
        ),
        CheckConstraint(
            "answered_count BETWEEN 0 AND requested_count",
            name="ck_training_session_answered_count_range",
        ),
        CheckConstraint(
            "correct_count >= 0 AND wrong_count >= 0 "
            "AND correct_count::bigint + wrong_count::bigint = answered_count",
            name="ck_training_session_answer_counts",
        ),
        CheckConstraint(
            "(status = 'in_progress') = (finished_at IS NULL)",
            name="ck_training_session_finish_state",
        ),
        CheckConstraint(
            "finished_at >= started_at",
            name="ck_training_session_dates_order",
        ),
        CheckConstraint(
            "status <> 'completed' OR answered_count = requested_count",
            name="ck_training_session_completed_count",
        ),
        CheckConstraint(
            "substring(activity_tracker_uuid::text from 15 for 1) = '7' "
            "AND substring(activity_tracker_uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')",
            name="ck_training_session_tracker_uuid_v7",
        ),
        CheckConstraint(
            "activity_last_seen_at >= started_at",
            name="ck_training_session_activity_dates_order",
        ),
        CheckConstraint(
            "status = 'in_progress' OR "
            "(activity_tracker_uuid IS NULL AND activity_last_seen_at IS NULL)",
            name="ck_training_session_finished_activity_empty",
        ),
        CheckConstraint(
            "id > 0",
            name="ck_training_session_id_positive",
        ),
        CheckConstraint(
            """
            prompt_side IN ('front', 'back')
            AND answer_side IN ('front', 'back')
            AND prompt_side <> answer_side
            """,
            name="ck_training_session_card_sides_valid_and_different",
        ),
        CheckConstraint(
            "requested_count >= 1",
            name="ck_training_session_requested_count_ge_1",
        ),
        CheckConstraint(
            f"requested_count <= {MAX_SESSION_SIZE}",
            name="ck_training_session_requested_count_le_max",
        ),
        CheckConstraint(
            "active_study_time_ms >= 0",
            name="ck_training_session_active_study_time_ms_non_negative",
        ),
        CheckConstraint(
            """
            (activity_tracker_uuid IS NULL)
            = (activity_last_seen_at IS NULL)
            """,
            name="ck_training_session_activity_state_consistent",
        ),
    )

    @property
    def deck_uuid(self) -> UUID | None:
        return self.deck.uuid if self.deck is not None else None

    @property
    def deck_title(self) -> DeckTitle | None:
        return self.deck_title_snapshot


class TrainingSessionItem(Base):
    __tablename__ = "training_session_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[UUID] = mapped_column(
        postgresUUID(as_uuid=True),
        server_default=text("uuidv7()"),
        unique=True,
        nullable=False,
        index=True,
    )

    training_session_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("training_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    original_card_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    learning_key_snapshot: Mapped[UUID | None] = mapped_column(
        postgresUUID(as_uuid=True),
        nullable=True,
    )

    user_typed_text: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    prompt_text: Mapped[str] = mapped_column(String(255), nullable=False)
    answer_text: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_lang: Mapped[str] = mapped_column(String(3), nullable=False)
    answer_lang: Mapped[str] = mapped_column(String(3), nullable=False)

    is_answered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    training_session: Mapped["TrainingSession"] = relationship("TrainingSession", back_populates="items", lazy="raise")

    __table_args__ = (
        CheckConstraint("id > 0", name="ck_training_session_item_id_positive"),
        CheckConstraint("training_session_id > 0", name="ck_training_session_item_session_id_positive"),
        CheckConstraint("original_card_id > 0", name="ck_training_session_item_card_id_positive"),
        CheckConstraint(
            "substring(uuid::text from 15 for 1) = '7' "
            "AND substring(uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')",
            name="ck_training_session_item_uuid_v7",
        ),
        CheckConstraint(
            "substring(learning_key_snapshot::text from 15 for 1) = '7' "
            "AND substring(learning_key_snapshot::text from 20 for 1) IN ('8', '9', 'a', 'b')",
            name="ck_training_session_item_learning_key_snapshot_v7",
        ),
        UniqueConstraint(
            "training_session_id", "original_card_id",
            name="uq_training_session_item_original_card",
        ),
        CheckConstraint(
            f"sequence_number <= {MAX_SESSION_SIZE}",
            name="ck_training_session_item_sequence_le_max",
        ),
        CheckConstraint(
            "is_answered = (answered_at IS NOT NULL)",
            name="ck_training_session_item_answer_date_state",
        ),
        CheckConstraint(
            "(is_answered OR user_typed_text IS NULL) "
            "AND (is_correct IS NOT TRUE OR user_typed_text IS NOT NULL)",
            name="ck_training_session_item_answer_text_state",
        ),
        *(
            CheckConstraint(
                f"char_length({field}) BETWEEN 1 AND 255",
                name=f"ck_training_session_item_{field}_length",
            )
            for field in ("prompt_text", "answer_text", "user_typed_text")
        ),
        *(
            CheckConstraint(
                f"{field} = btrim({field}, U&'\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')",
                name=f"ck_training_session_item_{field}_trimmed",
            )
            for field in ("prompt_text", "answer_text", "user_typed_text")
        ),
        *(
            CheckConstraint(
                f"{field} ~ '^[a-z]{{2,3}}$' AND char_length({field}) BETWEEN 2 AND 3",
                name=f"ck_training_session_item_{field}_format",
            )
            for field in ("prompt_lang", "answer_lang")
        ),
        UniqueConstraint(
            "training_session_id",
            "sequence_number",
            name="uq_training_session_item_sequence",
        ),
        CheckConstraint(
            "sequence_number >= 1",
            name="ck_training_session_item_sequence_ge_1",
        ),
        CheckConstraint(
            "is_answered = (is_correct IS NOT NULL)",
            name="ck_training_session_item_answer_correct_state"
        )
    )
