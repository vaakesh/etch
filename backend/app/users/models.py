

from datetime import datetime
import uuid

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        unique=True,
        nullable=False,
        index=True
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

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

    cards = relationship("Card", back_populates="user")
    decks = relationship("Deck", back_populates="user")
    training_sessions = relationship("TrainingSession", back_populates="user")
    user_sessions = relationship(
        "UserSession", 
        foreign_keys="UserSession.user_id", 
        back_populates="user"
    )