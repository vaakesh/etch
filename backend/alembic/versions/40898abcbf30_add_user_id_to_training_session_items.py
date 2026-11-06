"""Copy the session owner into training session items.

The FSRS history of a word is read for one user. Words of public decks share a
learning key across many users, so the history index has to start with user_id.

Revision ID: 40898abcbf30
Revises: e4b81f6c3a57
"""

import sqlalchemy as sa

from alembic import op

revision = "40898abcbf30"
down_revision = "e4b81f6c3a57"
branch_labels = None
depends_on = None

OLD_INDEX_NAME = "ix_training_session_items_learning_key_answered"
NEW_INDEX_NAME = "ix_training_session_items_user_learning_key_answered"


def upgrade() -> None:
    op.add_column(
        "training_session_items",
        sa.Column("user_id", sa.BigInteger(), nullable=True),
    )
    op.execute(
        """
        UPDATE training_session_items AS items
        SET user_id = sessions.user_id
        FROM training_sessions AS sessions
        WHERE sessions.id = items.training_session_id
        """
    )
    op.alter_column("training_session_items", "user_id", nullable=False)
    op.create_check_constraint(
        "ck_training_session_item_user_id_positive",
        "training_session_items",
        "user_id > 0",
    )
    # Составной ключ гарантирует, что user_id item совпадает с владельцем сессии
    op.create_unique_constraint(
        "uq_training_session_id_user",
        "training_sessions",
        ["id", "user_id"],
    )
    op.create_foreign_key(
        "fk_training_session_items_session_user",
        "training_session_items",
        "training_sessions",
        ["training_session_id", "user_id"],
        ["id", "user_id"],
        ondelete="CASCADE",
    )

    with op.get_context().autocommit_block():
        op.create_index(
            NEW_INDEX_NAME,
            "training_session_items",
            ["user_id", "learning_key_snapshot", "answered_at", "id"],
            postgresql_where=sa.text("is_answered"),
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.drop_index(
            OLD_INDEX_NAME,
            table_name="training_session_items",
            postgresql_concurrently=True,
            if_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            OLD_INDEX_NAME,
            "training_session_items",
            ["learning_key_snapshot", "answered_at", "id"],
            postgresql_where=sa.text("is_answered"),
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.drop_index(
            NEW_INDEX_NAME,
            table_name="training_session_items",
            postgresql_concurrently=True,
            if_exists=True,
        )

    op.drop_constraint(
        "fk_training_session_items_session_user",
        "training_session_items",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_training_session_id_user",
        "training_sessions",
        type_="unique",
    )
    op.drop_constraint(
        "ck_training_session_item_user_id_positive",
        "training_session_items",
        type_="check",
    )
    op.drop_column("training_session_items", "user_id")
