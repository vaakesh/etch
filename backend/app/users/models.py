

from datetime import datetime
from uuid import UUID

from app.database import Base
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID as postgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class UserSettings(Base):
    __tablename__ = "users_settings"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    locale: Mapped[str] = mapped_column(
        String(10),
        default="ru-RU",
        server_default="ru-RU",
    )
    theme: Mapped[str] = mapped_column(
        String(10),
        default="system",
        server_default="system",
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

    user = relationship("User", back_populates="settings")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger, 
        primary_key=True,
        nullable=False,
    )
    uuid: Mapped[UUID] = mapped_column(
        postgresUUID(as_uuid=True),
        server_default=text("uuidv7()"),
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

    cards = relationship("Card", back_populates="user", passive_deletes=True)
    decks = relationship("Deck", back_populates="user", passive_deletes=True)
    training_sessions = relationship(
        "TrainingSession", 
        back_populates="user", 
        passive_deletes=True,
    )
    user_sessions = relationship(
        "UserSession", 
        foreign_keys="UserSession.user_id", 
        back_populates="user",
        passive_deletes=True,
    )
    settings = relationship(
        "UserSettings",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
