"""Enforce positive training session IDs.

Revision ID: b359e607fa18
Revises: a248d596ef07
"""
from alembic import op

revision = "b359e607fa18"
down_revision = "a248d596ef07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_training_session_id_positive", "training_sessions", "id > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_training_session_id_positive", "training_sessions", type_="check",
    )
