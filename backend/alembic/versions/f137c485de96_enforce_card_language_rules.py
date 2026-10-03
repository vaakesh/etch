"""Enforce normalized card language codes.

Revision ID: f137c485de96
Revises: e026b374cd85
"""
from alembic import op

revision = "f137c485de96"
down_revision = "e026b374cd85"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for field in ("front_lang", "back_lang"):
        op.create_check_constraint(
            f"ck_cards_{field}_format", "cards",
            f"{field} ~ '^[a-z]{{2,3}}$' AND char_length({field}) BETWEEN 2 AND 3",
        )


def downgrade() -> None:
    for field in ("back_lang", "front_lang"):
        op.drop_constraint(f"ck_cards_{field}_format", "cards", type_="check")
