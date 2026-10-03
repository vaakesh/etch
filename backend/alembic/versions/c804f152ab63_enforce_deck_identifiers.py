"""Require positive deck identifiers and UUIDv7.

Revision ID: c804f152ab63
Revises: b793e041fa52
"""
from alembic import op

revision = "c804f152ab63"
down_revision = "b793e041fa52"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint("ck_deck_id_positive", "decks", "id > 0")
    op.create_check_constraint("ck_deck_user_id_positive", "decks", "user_id > 0")
    op.create_check_constraint(
        "ck_deck_source_id_positive", "decks",
        "source_deck_id IS NULL OR source_deck_id > 0",
    )
    op.create_check_constraint(
        "ck_deck_uuid_v7", "decks",
        "substring(uuid::text from 15 for 1) = '7' "
        "AND substring(uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_deck_uuid_v7", "decks", type_="check")
    op.drop_constraint("ck_deck_source_id_positive", "decks", type_="check")
    op.drop_constraint("ck_deck_user_id_positive", "decks", type_="check")
    op.drop_constraint("ck_deck_id_positive", "decks", type_="check")
