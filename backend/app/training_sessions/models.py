from datetime import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
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
    actual_count: Mapped[int] = mapped_column(Integer)

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