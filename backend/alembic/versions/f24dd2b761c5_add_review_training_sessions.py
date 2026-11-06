"""Add FSRS review sessions and indexes for due words.

A review session is not tied to a deck: it collects due words from every deck
the user can study. Due words are found by user, prompt side and due, then
mapped to cards by learning key.

Revision ID: f24dd2b761c5
Revises: 0d6d9ea8d635
"""

import sqlalchemy as sa

from alembic import op

revision = "f24dd2b761c5"
down_revision = "0d6d9ea8d635"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "training_sessions",
        sa.Column(
            "kind",
            sa.Enum(
                "deck",
                "review",
                name="training_session_kind",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="deck",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_training_session_review_without_deck",
        "training_sessions",
        "kind = 'deck' OR (deck_id IS NULL AND deck_title_snapshot IS NULL)",
    )

    with op.get_context().autocommit_block():
        op.create_index(
            "uq_training_sessions_active_review",
            "training_sessions",
            ["user_id"],
            unique=True,
            postgresql_where=sa.text("kind = 'review' AND status = 'in_progress'"),
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.create_index(
            "ix_card_memory_states_user_side_due",
            "card_memory_states",
            ["user_id", "prompt_side", "due"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.create_index(
            "ix_cards_learning_key",
            "cards",
            ["learning_key"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for index_name, table_name in (
            ("ix_cards_learning_key", "cards"),
            ("ix_card_memory_states_user_side_due", "card_memory_states"),
            ("uq_training_sessions_active_review", "training_sessions"),
        ):
            op.drop_index(
                index_name,
                table_name=table_name,
                postgresql_concurrently=True,
                if_exists=True,
            )

    op.drop_constraint(
        "ck_training_session_review_without_deck",
        "training_sessions",
        type_="check",
    )
    op.drop_column("training_sessions", "kind")
