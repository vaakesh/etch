"""Add stable learning keys to cards.

Revision ID: 7f0c1b8a42de
Revises: 6a92c1e8f047
"""

import sqlalchemy as sa
from alembic import op

revision = "7f0c1b8a42de"
down_revision = "6a92c1e8f047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cards",
        sa.Column(
            "learning_key",
            sa.UUID(),
            server_default=sa.text("uuidv7()"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_cards_learning_key_v7",
        "cards",
        "substring(learning_key::text from 15 for 1) = '7' "
        "AND substring(learning_key::text from 20 for 1) IN ('8', '9', 'a', 'b')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_cards_learning_key_v7", "cards", type_="check")
    op.drop_column("cards", "learning_key")
