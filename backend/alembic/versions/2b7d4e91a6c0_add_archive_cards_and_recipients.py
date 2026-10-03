"""Add archive-owned cards and archive recipients.

Revision ID: 2b7d4e91a6c0
Revises: 19e4a62c0d5b
"""

import sqlalchemy as sa
from alembic import op

revision = "2b7d4e91a6c0"
down_revision = "19e4a62c0d5b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cards", sa.Column("archive_deck_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_cards_archive_deck_id_decks", "cards", "decks",
        ["archive_deck_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_cards_archive_deck_id", "cards", ["archive_deck_id"])
    op.alter_column(
        "cards", "user_id", existing_type=sa.BigInteger(), nullable=True,
    )
    op.create_check_constraint(
        "ck_cards_archive_deck_id_positive", "cards", "archive_deck_id > 0",
    )
    op.create_check_constraint(
        "ck_cards_owner_or_archive", "cards",
        "(user_id IS NOT NULL AND archive_deck_id IS NULL) OR "
        "(user_id IS NULL AND archive_deck_id IS NOT NULL)",
    )

    op.create_table(
        "deck_archive_recipients",
        sa.Column("archive_deck_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("preserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("preserved_deck_id", sa.BigInteger(), nullable=True),
        sa.Column("preserved_deck_uuid_snapshot", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["archive_deck_id"], ["decks.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["preserved_deck_id"], ["decks.id"], ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("archive_deck_id", "user_id"),
        sa.CheckConstraint(
            "archive_deck_id > 0",
            name="ck_deck_archive_recipient_archive_deck_id_positive",
        ),
        sa.CheckConstraint(
            "user_id > 0", name="ck_deck_archive_recipient_user_id_positive",
        ),
        sa.CheckConstraint(
            "preserved_deck_id > 0",
            name="ck_deck_archive_recipient_preserved_deck_id_positive",
        ),
        sa.CheckConstraint(
            "preserved_deck_id IS NULL OR preserved_deck_id <> archive_deck_id",
            name="ck_deck_archive_recipient_distinct_decks",
        ),
        sa.CheckConstraint(
            "(preserved_at IS NULL AND preserved_deck_id IS NULL "
            "AND preserved_deck_uuid_snapshot IS NULL) OR "
            "(preserved_at IS NOT NULL "
            "AND preserved_deck_uuid_snapshot IS NOT NULL)",
            name="ck_deck_archive_recipient_preservation_state",
        ),
        sa.CheckConstraint(
            "substring(preserved_deck_uuid_snapshot::text from 15 for 1) = '7' "
            "AND substring(preserved_deck_uuid_snapshot::text from 20 for 1) "
            "IN ('8', '9', 'a', 'b')",
            name="ck_deck_archive_recipient_preserved_uuid_v7",
        ),
    )
    op.create_index(
        "ix_deck_archive_recipients_user_id",
        "deck_archive_recipients",
        ["user_id"],
    )
    op.create_index(
        "ix_deck_archive_recipients_preserved_deck_id",
        "deck_archive_recipients",
        ["preserved_deck_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_deck_archive_recipients_preserved_deck_id",
        table_name="deck_archive_recipients",
    )
    op.drop_index(
        "ix_deck_archive_recipients_user_id",
        table_name="deck_archive_recipients",
    )
    op.drop_table("deck_archive_recipients")

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM cards WHERE archive_deck_id IS NOT NULL) THEN
                RAISE EXCEPTION 'Cannot downgrade while archive-owned cards exist';
            END IF;
        END;
        $$
    """)
    op.drop_constraint("ck_cards_owner_or_archive", "cards", type_="check")
    op.drop_constraint("ck_cards_archive_deck_id_positive", "cards", type_="check")
    op.alter_column(
        "cards", "user_id", existing_type=sa.BigInteger(), nullable=False,
    )
    op.drop_index("ix_cards_archive_deck_id", table_name="cards")
    op.drop_constraint(
        "fk_cards_archive_deck_id_decks", "cards", type_="foreignkey",
    )
    op.drop_column("cards", "archive_deck_id")
