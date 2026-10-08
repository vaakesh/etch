"""Index user session replacement references.

Revision ID: a1c5e7b93d24
Revises: 94f1c7d3a8b2
"""
import sqlalchemy as sa

from alembic import op

revision = "a1c5e7b93d24"
down_revision = "94f1c7d3a8b2"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_user_sessions_replaced_by_session_id"


def upgrade() -> None:
    # Deleting a session makes PostgreSQL look up the rows that reference it
    # through replaced_by_session_id; without this index that is a full scan
    # per deleted row.
    with op.get_context().autocommit_block():
        op.create_index(
            INDEX_NAME,
            "user_sessions",
            ["replaced_by_session_id"],
            postgresql_where=sa.text("replaced_by_session_id IS NOT NULL"),
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            INDEX_NAME,
            table_name="user_sessions",
            postgresql_concurrently=True,
            if_exists=True,
        )
