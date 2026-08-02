import uuid
from datetime import datetime

from app.database import Base
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Deck(Base):
    __tablename__ = "decks"

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
        nullable=False,
    )

    source_deck_id: Mapped[int | None] = mapped_column(
        ForeignKey("decks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(150),
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
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="decks", lazy="raise")
    card_links = relationship(
        "DeckCard", 
        back_populates="deck", 
        cascade="all, delete-orphan",
    )
    training_sessions = relationship(
        "TrainingSession", 
        back_populates="deck",
        passive_deletes=True,
    )

    @property
    def owner_uuid(self) -> UUID:
        return self.user.uuid


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

    deck = relationship("Deck", back_populates="card_links")
    card = relationship("Card", back_populates="deck_links")

    __table_args__ = (
        UniqueConstraint("deck_id", "card_id", name="uq_deck_card"),
        CheckConstraint(
            "position >= 1",
            name="ck_deck_cards_position_ge_1",
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

    sessions_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_studied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_favourite: Mapped[bool] = mapped_column(
        Boolean, 
        default=False,
        server_default=text("false"),
        nullable=False,
    )
    is_following: Mapped[bool] = mapped_column(
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