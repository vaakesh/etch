"""Preserve the studied deck title in training sessions.

Revision ID: 8c91e2f7b4a0
Revises: 53a6e1d920bf
"""

import sqlalchemy as sa
from alembic import op

revision = "8c91e2f7b4a0"
down_revision = "53a6e1d920bf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "training_sessions",
        sa.Column("deck_title_snapshot", sa.String(50), nullable=True),
    )
    op.execute("""
        UPDATE training_sessions AS training_session
        SET deck_title_snapshot = deck.title
        FROM decks AS deck
        WHERE training_session.deck_id = deck.id
    """)
    op.create_check_constraint(
        "ck_training_session_deck_title_snapshot_present",
        "training_sessions",
        "deck_id IS NULL OR deck_title_snapshot IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_training_session_deck_title_snapshot_length",
        "training_sessions",
        "char_length(deck_title_snapshot) BETWEEN 3 AND 50",
    )
    op.create_check_constraint(
        "ck_training_session_deck_title_snapshot_trimmed",
        "training_sessions",
        "deck_title_snapshot = btrim(deck_title_snapshot, U&'\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')",
    )
    op.create_check_constraint(
        "ck_training_session_deck_title_snapshot_single_line",
        "training_sessions",
        "deck_title_snapshot = translate(deck_title_snapshot, U&'\\0009\\000A\\000B\\000C\\000D\\0085\\2028\\2029', '')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_training_session_deck_title_snapshot_single_line",
        "training_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_training_session_deck_title_snapshot_trimmed",
        "training_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_training_session_deck_title_snapshot_length",
        "training_sessions",
        type_="check",
    )
    op.drop_constraint(
        "ck_training_session_deck_title_snapshot_present",
        "training_sessions",
        type_="check",
    )
    op.drop_column("training_sessions", "deck_title_snapshot")
