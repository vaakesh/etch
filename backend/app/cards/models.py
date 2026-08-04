import uuid
from datetime import datetime

from app.database import Base
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


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

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
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

    user = relationship("User", back_populates="cards")
    deck_links = relationship(
        "DeckCard",
        back_populates="card", 
        cascade="all, delete-orphan",
    )