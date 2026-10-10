"""Index user decks by deck.

Revision ID: b7e2d9c41f53
Revises: a1c5e7b93d24
"""
from alembic import op

revision = "b7e2d9c41f53"
down_revision = "a1c5e7b93d24"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_user_decks_deck_id"


def upgrade() -> None:
    # The primary key starts with user_id, so lookups by deck_id alone and the
    # cascade from deleting a deck were full scans of user_decks.
    with op.get_context().autocommit_block():
        op.create_index(
            INDEX_NAME,
            "user_decks",
            ["deck_id"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            INDEX_NAME,
            table_name="user_decks",
            postgresql_concurrently=True,
            if_exists=True,
        )
