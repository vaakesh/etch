"""Store the user's IANA timezone in settings.

The FSRS review summary counts words due until the end of the user's day.

Revision ID: 0d6d9ea8d635
Revises: 40898abcbf30
"""

import sqlalchemy as sa

from alembic import op

revision = "0d6d9ea8d635"
down_revision = "40898abcbf30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users_settings",
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default="UTC",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "timezone_not_empty",
        "users_settings",
        "char_length(timezone) >= 1",
    )


def downgrade() -> None:
    op.drop_constraint("timezone_not_empty", "users_settings", type_="check")
    op.drop_column("users_settings", "timezone")
