"""Enforce card identifiers and timestamp order.

Revision ID: a248d596ef07
Revises: f137c485de96
"""
from alembic import op

revision = "a248d596ef07"
down_revision = "f137c485de96"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint("ck_cards_id_positive", "cards", "id > 0")
    op.create_check_constraint("ck_cards_user_id_positive", "cards", "user_id > 0")
    op.create_check_constraint(
        "ck_cards_uuid_v7", "cards",
        "substring(uuid::text from 15 for 1) = '7' "
        "AND substring(uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')",
    )
    op.create_check_constraint("ck_cards_dates_order", "cards", "updated_at >= created_at")


def downgrade() -> None:
    op.drop_constraint("ck_cards_dates_order", "cards", type_="check")
    op.drop_constraint("ck_cards_uuid_v7", "cards", type_="check")
    op.drop_constraint("ck_cards_user_id_positive", "cards", type_="check")
    op.drop_constraint("ck_cards_id_positive", "cards", type_="check")
