"""Enforce user session identifiers, dates and replacement state.

Revision ID: d571a829bc30
Revises: c460f718ab29
"""
from alembic import op

revision = "d571a829bc30"
down_revision = "c460f718ab29"
branch_labels = None
depends_on = None

CHECKS = (
    ("ck_user_sessions_id_positive", "id > 0"),
    ("ck_user_sessions_user_id_positive", "user_id > 0"),
    (
        "ck_user_sessions_uuid_v7",
        "substring(uuid::text from 15 for 1) = '7' "
        "AND substring(uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')",
    ),
    ("ck_user_sessions_dates_order", "updated_at >= created_at"),
    ("ck_user_sessions_expiry_after_creation", "expires_at > created_at"),
    ("ck_user_sessions_revocation_after_creation", "revoked_at >= created_at"),
    ("ck_user_sessions_replacement_id_positive", "replaced_by_session_id > 0"),
    ("ck_user_sessions_replacement_not_self", "replaced_by_session_id <> id"),
    (
        "ck_user_sessions_replacement_requires_revocation",
        "replaced_by_session_id IS NULL OR revoked_at IS NOT NULL",
    ),
)


def upgrade() -> None:
    # Hash uniqueness already exists as ix_user_sessions_refresh_token_hash.
    # Do not rewrite existing sessions to satisfy the new rules.
    for name, condition in CHECKS:
        op.create_check_constraint(name, "user_sessions", condition)


def downgrade() -> None:
    for name, _ in reversed(CHECKS):
        op.drop_constraint(name, "user_sessions", type_="check")
