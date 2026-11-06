from datetime import datetime
from uuid import UUID

from app.database import Base
from app.fsrs.types import Card, CardState
from app.training_sessions.models import CardSide
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy import (
    Enum as SQLAlchemyEnum,
)
from sqlalchemy.dialects.postgresql import UUID as postgresUUID
from sqlalchemy.orm import Mapped, mapped_column

card_state_enum = SQLAlchemyEnum(
    CardState,
    name="card_memory_state",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    values_callable=lambda enum_class: [member.value for member in enum_class],
)


class CardMemoryState(Base):
    """FSRS-состояние памяти пользователя о слове в одном направлении перевода."""

    __tablename__ = "card_memory_states"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    learning_key: Mapped[UUID] = mapped_column(
        postgresUUID(as_uuid=True),
        primary_key=True,
    )
    # Направление: "кот → cat" и "cat → кот" запоминаются по-разному
    prompt_side: Mapped[CardSide] = mapped_column(String(5), primary_key=True)

    state: Mapped[CardState] = mapped_column(card_state_enum, nullable=False)
    step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Double, чтобы значения из БД совпадали с float в Python бит в бит
    stability: Mapped[float | None] = mapped_column(Double, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Double, nullable=True)
    due: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_review: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("user_id > 0", name="ck_card_memory_user_id_positive"),
        CheckConstraint(
            "substring(learning_key::text from 15 for 1) = '7' "
            "AND substring(learning_key::text from 20 for 1) IN ('8', '9', 'a', 'b')",
            name="ck_card_memory_learning_key_v7",
        ),
        CheckConstraint(
            "prompt_side IN ('front', 'back')",
            name="ck_card_memory_prompt_side_valid",
        ),
        CheckConstraint(
            "(state = 'review') = (step IS NULL)",
            name="ck_card_memory_step_matches_state",
        ),
        CheckConstraint("step >= 0", name="ck_card_memory_step_non_negative"),
        CheckConstraint(
            "(stability IS NULL) = (difficulty IS NULL) "
            "AND (stability IS NULL) = (last_review IS NULL)",
            name="ck_card_memory_memory_fields_together",
        ),
        CheckConstraint(
            "stability >= 0.001",
            name="ck_card_memory_stability_min",
        ),
        CheckConstraint(
            "difficulty BETWEEN 1 AND 10",
            name="ck_card_memory_difficulty_range",
        ),
        CheckConstraint(
            "due >= last_review",
            name="ck_card_memory_due_after_last_review",
        ),
        # Слова к повторению: память пользователя в одном направлении по due
        Index("ix_card_memory_states_user_side_due", "user_id", "prompt_side", "due"),
    )

    def to_fsrs_card(self) -> Card:
        return Card(
            state=self.state,
            step=self.step,
            stability=self.stability,
            difficulty=self.difficulty,
            due=self.due,
            last_review=self.last_review,
        )

    def apply_fsrs_card(self, card: Card) -> None:
        self.state = card.state
        self.step = card.step
        self.stability = card.stability
        self.difficulty = card.difficulty
        self.due = card.due
        self.last_review = card.last_review
