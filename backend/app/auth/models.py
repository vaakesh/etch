import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from app.database import Base
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.users.models import User

class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        server_default=text("uuidv7()"),
        unique=True,
        nullable=False,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    refresh_token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
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

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    replaced_by_session_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("user_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    user: Mapped["User"] = relationship(
        "User", 
        foreign_keys=[user_id], 
        back_populates="user_sessions",
        lazy="raise",
    )

    __table_args__ = (
        CheckConstraint("id > 0", name="ck_user_sessions_id_positive"),
        CheckConstraint("user_id > 0", name="ck_user_sessions_user_id_positive"),
        CheckConstraint(
            "substring(uuid::text from 15 for 1) = '7' "
            "AND substring(uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')",
            name="ck_user_sessions_uuid_v7",
        ),
        CheckConstraint(
            "updated_at >= created_at",
            name="ck_user_sessions_dates_order",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_user_sessions_expiry_after_creation",
        ),
        CheckConstraint(
            "revoked_at >= created_at",
            name="ck_user_sessions_revocation_after_creation",
        ),
        CheckConstraint(
            "replaced_by_session_id > 0",
            name="ck_user_sessions_replacement_id_positive",
        ),
        CheckConstraint(
            "replaced_by_session_id <> id",
            name="ck_user_sessions_replacement_not_self",
        ),
        CheckConstraint(
            "replaced_by_session_id IS NULL OR revoked_at IS NOT NULL",
            name="ck_user_sessions_replacement_requires_revocation",
        ),
        Index(
            "ix_user_sessions_replaced_by_session_id",
            "replaced_by_session_id",
            postgresql_where=text("replaced_by_session_id IS NOT NULL"),
        ),
    )
