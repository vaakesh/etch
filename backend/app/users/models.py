

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.database import Base
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as postgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.auth.models import UserSession
    from app.cards.models import Card
    from app.decks.models import Deck
    from app.training_sessions.models import TrainingSession


class UserSettings(Base):
    __tablename__ = "users_settings"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    locale: Mapped[str] = mapped_column(
        String(10),
        default="ru-RU",
        server_default="ru-RU",
        nullable=False,
    )
    theme: Mapped[str] = mapped_column(
        String(10),
        default="system",
        server_default="system",
        nullable=False,
    )
    show_previews_for_long: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
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

    user: Mapped[User] = relationship(
        back_populates="settings",
        lazy="raise",
        single_parent=True,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        BigInteger, 
        primary_key=True,
    )

    uuid: Mapped[UUID] = mapped_column(
        postgresUUID(as_uuid=True),
        server_default=text("uuidv7()"),
        nullable=False,
    )

    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
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

    cards: Mapped[list["Card"]] = relationship(
        back_populates="user",
        passive_deletes=True,
        lazy="raise",
    )
    decks: Mapped[list["Deck"]] = relationship(
        back_populates="user",
        passive_deletes=True,
        lazy="raise",
    )
    training_sessions: Mapped[list["TrainingSession"]] = relationship(
        back_populates="user",
        passive_deletes=True,
        lazy="raise",
    )
    user_sessions: Mapped[list["UserSession"]] = relationship(
        foreign_keys="UserSession.user_id",
        back_populates="user",
        passive_deletes=True,
        lazy="raise",
    )
    settings: Mapped["UserSettings"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="raise",
        single_parent=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "uuid",
            name="uq_users_uuid",
        ),
        UniqueConstraint(
            "username",
            name="uq_users_username",
        ),
        UniqueConstraint(
            "email",
            name="uq_users_email",
        ),

        CheckConstraint(
            "char_length(username) >= 3",
            name="username_min_length",
        ),
        CheckConstraint(
            "username = btrim(username)",
            name="username_trimmed",
        ),
        CheckConstraint(
            "email = btrim(email)",
            name="email_trimmed",
        ),
    )
