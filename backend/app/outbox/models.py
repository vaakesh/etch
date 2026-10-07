from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    published: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("char_length(btrim(event_type)) > 0", name="ck_outbox_event_type_present"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_outbox_payload_object"),
        CheckConstraint(
            "published = (published_at IS NOT NULL)", name="ck_outbox_publication_state",
        ),
        Index(
            "ix_outbox_pending_event_type_id", "event_type", "id",
            postgresql_where=text("published = false"),
        ),
    )
