"""Enforce username format and case-insensitive uniqueness.

Revision ID: e9a31b672405
Revises: 871567056706
"""

from alembic import op
import sqlalchemy as sa


revision = "e9a31b672405"
down_revision = "871567056706"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fail on incompatible existing data; do not rename users automatically.
    op.alter_column(
        "users", "username",
        existing_type=sa.String(50), type_=sa.String(18),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "username_min_length", "users", "char_length(username) >= 3",
    )
    op.create_check_constraint(
        "username_allowed_characters", "users", "username !~ '[^A-Za-z0-9_-]'",
    )
    op.create_index(
        "uq_users_username_lower", "users", [sa.text("lower(username)")],
        unique=True,
    )
    op.drop_constraint("users_username_key", "users", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("users_username_key", "users", ["username"])
    op.drop_index("uq_users_username_lower", table_name="users")
    op.drop_constraint("username_allowed_characters", "users", type_="check")
    op.drop_constraint("username_min_length", "users", type_="check")
    op.alter_column(
        "users", "username",
        existing_type=sa.String(18), type_=sa.String(50),
        existing_nullable=False,
    )
