from datetime import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        server_default=text("uuidv7()"),
        unique=True,
        nullable=False,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    deck_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("decks.id", ondelete="CASCADE"),
        index=True,
    )

    requested_count: Mapped[int] = mapped_column(Integer)
    actual_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))

    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)

    prompt_side: Mapped[str] = mapped_column(String(20), default="front")
    answer_side: Mapped[str] = mapped_column(String(20), default="back")

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


class TrainingSessionItem(Base):
    __tablename__ = "training_session_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
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

    original_card_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_lang: Mapped[str] = mapped_column(String(10), nullable=False)
    answer_lang: Mapped[str] = mapped_column(String(10), nullable=False)

    is_answered: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=text("false"),
        nullable=False,
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
            name="ck_training_session_items_sequence_ge_1",
        ),
    )
