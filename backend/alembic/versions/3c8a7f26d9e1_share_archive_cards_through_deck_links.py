"""Share archive card copies through deck links.

Revision ID: 3c8a7f26d9e1
Revises: 2b7d4e91a6c0
"""

import sqlalchemy as sa
from alembic import op

revision = "3c8a7f26d9e1"
down_revision = "2b7d4e91a6c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # An existing archive card must not lose its only link to its archive.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM cards AS card
                WHERE card.archive_deck_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM deck_cards AS link
                      WHERE link.card_id = card.id
                        AND link.deck_id = card.archive_deck_id
                  )
            ) THEN
                RAISE EXCEPTION 'Archive cards without deck links cannot be migrated';
            END IF;
        END;
        $$
    """)

    op.drop_constraint("ck_cards_owner_or_archive", "cards", type_="check")
    op.drop_constraint("ck_cards_archive_deck_id_positive", "cards", type_="check")
    op.drop_index("ix_cards_archive_deck_id", table_name="cards")
    op.drop_constraint(
        "fk_cards_archive_deck_id_decks", "cards", type_="foreignkey",
    )
    op.drop_column("cards", "archive_deck_id")


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM cards WHERE user_id IS NULL) THEN
                RAISE EXCEPTION 'Cannot downgrade shared archive cards';
            END IF;
        END;
        $$
    """)

    op.add_column(
        "cards", sa.Column("archive_deck_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_cards_archive_deck_id_decks", "cards", "decks",
        ["archive_deck_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_cards_archive_deck_id", "cards", ["archive_deck_id"])
    op.create_check_constraint(
        "ck_cards_archive_deck_id_positive", "cards", "archive_deck_id > 0",
    )
    op.create_check_constraint(
        "ck_cards_owner_or_archive", "cards",
        "(user_id IS NOT NULL AND archive_deck_id IS NULL) OR "
        "(user_id IS NULL AND archive_deck_id IS NOT NULL)",
    )
