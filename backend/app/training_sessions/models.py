from datetime import datetime
from enum import StrEnum
from typing import Literal
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
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as postgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.limits import MAX_SESSION_SIZE
from app.common.types import DeckTitle

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

    deck_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("decks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    actual_count: Mapped[int] = mapped_column(
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

    user = relationship("User", back_populates="training_sessions")
    deck = relationship("Deck", back_populates="training_sessions")
    items = relationship(
        "TrainingSessionItem",
        back_populates="training_session",
        cascade="all, delete-orphan",
        order_by="TrainingSessionItem.sequence_number",
    )

    __table_args__ = (
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
    def deck_uuid(self) -> UUID:
        return self.deck.uuid

    @property
    def deck_title(self) -> DeckTitle:
        return self.deck.title


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

    original_card_uuid: Mapped[UUID] = mapped_column(
        postgresUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    user_typed_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
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

    training_session = relationship("TrainingSession", back_populates="items")

    __table_args__ = (
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
