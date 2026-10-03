"""Add deck archive lifecycle and preserve the source UUID.

Revision ID: 19e4a62c0d5b
Revises: 8c91e2f7b4a0
"""

import sqlalchemy as sa
from alembic import op

revision = "19e4a62c0d5b"
down_revision = "8c91e2f7b4a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "decks",
        sa.Column("state", sa.String(8), server_default="active", nullable=False),
    )
    op.add_column(
        "decks", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "decks", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "decks", sa.Column("archive_reason", sa.String(13), nullable=True),
    )
    op.add_column(
        "decks", sa.Column("source_deck_uuid_snapshot", sa.UUID(), nullable=True),
    )
    op.execute("""
        UPDATE decks AS target
        SET source_deck_uuid_snapshot = source.uuid
        FROM decks AS source
        WHERE target.source_deck_id = source.id
    """)

    op.drop_constraint("ck_deck_source_not_self", "decks", type_="check")
    op.drop_constraint("ck_deck_source_id_positive", "decks", type_="check")
    op.drop_index("ix_decks_source_deck_id", table_name="decks")
    op.drop_column("decks", "source_deck_id")
    op.alter_column(
        "decks", "user_id", existing_type=sa.BigInteger(), nullable=True,
    )

    op.create_check_constraint(
        "ck_deck_state", "decks", "state IN ('active', 'archived')",
    )
    op.create_check_constraint(
        "ck_deck_archive_reason", "decks",
        "archive_reason IS NULL OR archive_reason IN "
        "('deleted', 'owner_deleted', 'made_private')",
    )
    op.create_check_constraint(
        "ck_deck_archive_lifecycle", "decks",
        "(state = 'active' AND user_id IS NOT NULL "
        "AND archived_at IS NULL AND expires_at IS NULL "
        "AND archive_reason IS NULL) OR "
        "(state = 'archived' AND user_id IS NULL AND is_public = false "
        "AND archived_at IS NOT NULL AND expires_at IS NOT NULL "
        "AND archive_reason IS NOT NULL AND expires_at > archived_at)",
    )
    op.create_check_constraint(
        "ck_deck_source_uuid_snapshot_v7", "decks",
        "source_deck_uuid_snapshot IS NULL OR "
        "(substring(source_deck_uuid_snapshot::text from 15 for 1) = '7' "
        "AND substring(source_deck_uuid_snapshot::text from 20 for 1) "
        "IN ('8', '9', 'a', 'b'))",
    )
    op.create_index(
        "ix_decks_archived_expires_at_id", "decks", ["expires_at", "id"],
        postgresql_where=sa.text("state = 'archived'"),
    )


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM decks WHERE state = 'archived') THEN
                RAISE EXCEPTION 'Cannot downgrade while archived decks exist';
            END IF;
        END;
        $$
    """)

    op.add_column("decks", sa.Column("source_deck_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "decks_source_deck_id_fkey", "decks", "decks",
        ["source_deck_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_decks_source_deck_id", "decks", ["source_deck_id"])
    op.execute("""
        UPDATE decks AS target
        SET source_deck_id = source.id
        FROM decks AS source
        WHERE target.source_deck_uuid_snapshot = source.uuid
          AND target.id <> source.id
    """)
    op.create_check_constraint(
        "ck_deck_source_id_positive", "decks",
        "source_deck_id IS NULL OR source_deck_id > 0",
    )
    op.create_check_constraint(
        "ck_deck_source_not_self", "decks",
        "source_deck_id IS NULL OR source_deck_id <> id",
    )

    op.drop_index("ix_decks_archived_expires_at_id", table_name="decks")
    op.drop_constraint("ck_deck_source_uuid_snapshot_v7", "decks", type_="check")
    op.drop_constraint("ck_deck_archive_lifecycle", "decks", type_="check")
    op.drop_constraint("ck_deck_archive_reason", "decks", type_="check")
    op.drop_constraint("ck_deck_state", "decks", type_="check")
    op.alter_column(
        "decks", "user_id", existing_type=sa.BigInteger(), nullable=False,
    )
    op.drop_column("decks", "source_deck_uuid_snapshot")
    op.drop_column("decks", "archive_reason")
    op.drop_column("decks", "expires_at")
    op.drop_column("decks", "archived_at")
    op.drop_column("decks", "state")
