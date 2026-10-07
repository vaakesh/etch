"""Add a generic transactional outbox.

Revision ID: 94f1c7d3a8b2
Revises: 3c8a7f26d9e1
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "94f1c7d3a8b2"
down_revision = "3c8a7f26d9e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("char_length(btrim(event_type)) > 0", name="ck_outbox_event_type_present"),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_outbox_payload_object"),
        sa.CheckConstraint("published = (published_at IS NOT NULL)", name="ck_outbox_publication_state"),
    )
    op.create_index(
        "ix_outbox_pending_event_type_id", "outbox_messages", ["event_type", "id"],
        postgresql_where=sa.text("published = false"),
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_pending_event_type_id", table_name="outbox_messages")
    op.drop_table("outbox_messages")
