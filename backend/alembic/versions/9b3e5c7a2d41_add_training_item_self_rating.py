"""Add an optional FSRS self rating to training session items.

Revision ID: 9b3e5c7a2d41
Revises: 7d2f4a9c1b8e
"""

from alembic import op
import sqlalchemy as sa

revision = "9b3e5c7a2d41"
down_revision = "7d2f4a9c1b8e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "training_session_items",
        sa.Column("self_rating", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_training_session_item_self_rating_range",
        "training_session_items",
        "self_rating BETWEEN 1 AND 4",
    )
    op.create_check_constraint(
        "ck_training_session_item_self_rating_answered",
        "training_session_items",
        "self_rating IS NULL OR is_answered",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_training_session_item_self_rating_answered",
        "training_session_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_training_session_item_self_rating_range",
        "training_session_items",
        type_="check",
    )
    op.drop_column("training_session_items", "self_rating")
