"""Require positive user IDs, UUIDv7 and ordered timestamps.

Revision ID: c6513e902ab4
Revises: f2309c6e815a
"""

from alembic import op

revision = "c6513e902ab4"
down_revision = "f2309c6e815a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint("users_id_positive", "users", "id > 0")
    op.create_check_constraint(
        "users_settings_user_id_positive", "users_settings", "user_id > 0",
    )
    op.create_check_constraint(
        "users_uuid_v7", "users",
        "substring(uuid::text from 15 for 1) = '7' "
        "AND substring(uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')",
    )
    op.create_check_constraint("users_dates_order", "users", "updated_at >= created_at")
    op.create_check_constraint(
        "users_settings_dates_order", "users_settings", "updated_at >= created_at",
    )


def downgrade() -> None:
    op.drop_constraint("users_settings_dates_order", "users_settings", type_="check")
    op.drop_constraint("users_dates_order", "users", type_="check")
    op.drop_constraint("users_uuid_v7", "users", type_="check")
    op.drop_constraint("users_settings_user_id_positive", "users_settings", type_="check")
    op.drop_constraint("users_id_positive", "users", type_="check")
