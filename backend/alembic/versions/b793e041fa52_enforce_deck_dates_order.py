"""Require deck update timestamps not to precede creation.

Revision ID: b793e041fa52
Revises: a682d930ef41
"""
from alembic import op

revision = "b793e041fa52"
down_revision = "a682d930ef41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_deck_dates_order", "decks", "updated_at >= created_at",
    )


def downgrade() -> None:
    op.drop_constraint("ck_deck_dates_order", "decks", type_="check")
