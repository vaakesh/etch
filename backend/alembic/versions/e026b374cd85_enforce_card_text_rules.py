"""Enforce card text length and trimmed edges.

Revision ID: e026b374cd85
Revises: d915a263bc74
"""
from alembic import op

revision = "e026b374cd85"
down_revision = "d915a263bc74"
branch_labels = None
depends_on = None

# Explicit Python whitespace characters, matching CardText.strip_whitespace.
WHITESPACE = "\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000"


def upgrade() -> None:
    for field in ("front_text", "back_text"):
        op.create_check_constraint(
            f"ck_cards_{field}_length", "cards",
            f"char_length({field}) BETWEEN 1 AND 255",
        )
        op.create_check_constraint(
            f"ck_cards_{field}_trimmed", "cards",
            f"{field} = btrim({field}, U&'{WHITESPACE}')",
        )


def downgrade() -> None:
    for field in ("back_text", "front_text"):
        op.drop_constraint(f"ck_cards_{field}_trimmed", "cards", type_="check")
        op.drop_constraint(f"ck_cards_{field}_length", "cards", type_="check")
