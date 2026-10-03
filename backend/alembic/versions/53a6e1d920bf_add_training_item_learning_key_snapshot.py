"""Snapshot card learning keys in training session items.

Revision ID: 53a6e1d920bf
Revises: 7f0c1b8a42de
"""

import sqlalchemy as sa
from alembic import op

revision = "53a6e1d920bf"
down_revision = "7f0c1b8a42de"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "training_session_items",
        sa.Column("learning_key_snapshot", sa.UUID(), nullable=True),
    )
    op.execute("""
        UPDATE training_session_items AS item
        SET learning_key_snapshot = card.learning_key
        FROM cards AS card
        WHERE item.original_card_id = card.id
    """)
    op.create_check_constraint(
        "ck_training_session_item_learning_key_snapshot_v7",
        "training_session_items",
        "substring(learning_key_snapshot::text from 15 for 1) = '7' "
        "AND substring(learning_key_snapshot::text from 20 for 1) IN ('8', '9', 'a', 'b')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_training_session_item_learning_key_snapshot_v7",
        "training_session_items",
        type_="check",
    )
    op.drop_column("training_session_items", "learning_key_snapshot")
