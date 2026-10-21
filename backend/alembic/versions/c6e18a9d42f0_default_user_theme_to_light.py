"""Default new user settings to the light theme.

Revision ID: c6e18a9d42f0
Revises: b7e2d9c41f53
"""

from alembic import op


revision = "c6e18a9d42f0"
down_revision = "b7e2d9c41f53"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users_settings", "theme", server_default="light")


def downgrade() -> None:
    op.alter_column("users_settings", "theme", server_default="system")
