"""Enforce completed-session counters and study dates.

Revision ID: d915a263bc74
Revises: 4edb6c3a92f0
"""
from alembic import op

revision = "d915a263bc74"
down_revision = "4edb6c3a92f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_user_decks_answers_require_sessions", "user_decks",
        "sessions_count > 0 OR (correct_count = 0 AND wrong_count = 0)",
    )
    op.create_check_constraint(
        "ck_user_decks_study_matches_sessions", "user_decks",
        "(sessions_count = 0 AND last_studied_at IS NULL) OR "
        "(sessions_count > 0 AND last_studied_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_user_decks_study_dates_order", "user_decks",
        "last_studied_at IS NULL OR last_studied_at >= added_at",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_decks_study_dates_order", "user_decks", type_="check")
    op.drop_constraint("ck_user_decks_study_matches_sessions", "user_decks", type_="check")
    op.drop_constraint("ck_user_decks_answers_require_sessions", "user_decks", type_="check")
