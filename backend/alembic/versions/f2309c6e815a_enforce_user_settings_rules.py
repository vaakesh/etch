"""Enforce locale format and supported themes.

Revision ID: f2309c6e815a
Revises: b814a296cf03
"""

from alembic import op


revision = "f2309c6e815a"
down_revision = "b814a296cf03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "locale_format", "users_settings",
        "locale ~ '^[a-z]{2,3}-[A-Z]{2}$' AND char_length(locale) BETWEEN 5 AND 6",
    )
    op.create_check_constraint(
        "theme_allowed_values", "users_settings",
        "theme IN ('light', 'dark', 'system')",
    )


def downgrade() -> None:
    op.drop_constraint("theme_allowed_values", "users_settings", type_="check")
    op.drop_constraint("locale_format", "users_settings", type_="check")
