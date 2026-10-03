"""Enforce normalized, nonempty email addresses.

Revision ID: b814a296cf03
Revises: e9a31b672405
"""

from alembic import op


revision = "b814a296cf03"
down_revision = "e9a31b672405"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Validate existing data without silently rewriting user addresses.
    op.create_check_constraint("email_nonempty", "users", "char_length(email) >= 1")
    op.create_check_constraint("email_lowercase", "users", "email = lower(email)")
    op.create_check_constraint("email_no_whitespace", "users", "email !~ '[[:space:]]'")
    op.execute("ALTER TABLE users RENAME CONSTRAINT users_email_key TO uq_users_email")


def downgrade() -> None:
    op.execute("ALTER TABLE users RENAME CONSTRAINT uq_users_email TO users_email_key")
    op.drop_constraint("email_no_whitespace", "users", type_="check")
    op.drop_constraint("email_lowercase", "users", type_="check")
    op.drop_constraint("email_nonempty", "users", type_="check")
