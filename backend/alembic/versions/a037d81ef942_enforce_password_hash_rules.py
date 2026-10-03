"""Require nonempty password hashes without whitespace.

Revision ID: a037d81ef942
Revises: c6513e902ab4
"""

from alembic import op

revision = "a037d81ef942"
down_revision = "c6513e902ab4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "hashed_password_nonempty", "users", "char_length(hashed_password) >= 1",
    )
    op.create_check_constraint(
        "hashed_password_no_whitespace", "users", "hashed_password !~ '[[:space:]]'",
    )


def downgrade() -> None:
    op.drop_constraint("hashed_password_no_whitespace", "users", type_="check")
    op.drop_constraint("hashed_password_nonempty", "users", type_="check")
