from datetime import datetime
import uuid

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Card(Base):
    __tablename__ = "cards"

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

    front_text: Mapped[str] = mapped_column(String(255))
    back_text: Mapped[str] = mapped_column(String(255))

    source_lang: Mapped[str] = mapped_column(String(10), default="ru")
    target_lang: Mapped[str] = mapped_column(String(10), default="en")

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
    deck_links = relationship("DeckCard", back_populates="card", cascade="all, delete-orphan")