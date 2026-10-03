"""Require nonnegative deck counters and a positive version.

Revision ID: e682b930cd41
Revises: d571a829bc30
"""
from alembic import op

revision = "e682b930cd41"
down_revision = "d571a829bc30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_deck_words_count_ge_0", "decks", "words_count >= 0",
    )
    op.create_check_constraint(
        "ck_deck_saves_count_ge_0", "decks", "saves_count >= 0",
    )
    op.create_check_constraint(
        "ck_deck_version_ge_1", "decks", "version >= 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_deck_version_ge_1", "decks", type_="check")
    op.drop_constraint("ck_deck_saves_count_ge_0", "decks", type_="check")
    op.drop_constraint("ck_deck_words_count_ge_0", "decks", type_="check")
