from datetime import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Deck(Base):
    __tablename__ = "decks"

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

    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)

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

    user = relationship("User", back_populates="decks")
    card_links = relationship("DeckCard", back_populates="deck", cascade="all, delete-orphan")
    training_sessions = relationship("TrainingSession", back_populates="deck")


class DeckCard(Base):
    __tablename__ = "deck_cards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        index=True
    )

    deck_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("decks.id", ondelete="CASCADE"),
        index=True,
    )

    card_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("cards.id", ondelete="CASCADE"),
        index=True,
    )

    position: Mapped[int] = mapped_column(Integer, default=0)
    
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

    deck = relationship("Deck", back_populates="card_links")
    card = relationship("Card", back_populates="deck_links")

    __table_args__ = (
        UniqueConstraint("deck_id", "card_id", name="uq_deck_card"),
    )


class UserDeck(Base):
    __tablename__ = "user_decks"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    deck_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("decks.id", ondelete="CASCADE"),
        primary_key=True,
    )

    sessions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_studied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
