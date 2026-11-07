"""Index answered training session items by learning key.

Revision ID: e4b81f6c3a57
Revises: 9b3e5c7a2d41
"""

import sqlalchemy as sa

from alembic import op

revision = "e4b81f6c3a57"
down_revision = "9b3e5c7a2d41"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_training_session_items_learning_key_answered"


def upgrade() -> None:
    # rate_answer and the FSRS memory rebuild read the answer history of one
    # word; without this index each lookup was a full scan of the items.
    # answered_at, id match the replay order of that history.
    with op.get_context().autocommit_block():
        op.create_index(
            INDEX_NAME,
            "training_session_items",
            ["learning_key_snapshot", "answered_at", "id"],
            postgresql_where=sa.text("is_answered"),
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            INDEX_NAME,
            table_name="training_session_items",
            postgresql_concurrently=True,
            if_exists=True,
        )
