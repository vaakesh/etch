"""Add FSRS memory states per user, learning key and prompt side.

Revision ID: 7d2f4a9c1b8e
Revises: c6e18a9d42f0
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "7d2f4a9c1b8e"
down_revision = "c6e18a9d42f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "card_memory_states",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("learning_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prompt_side", sa.String(length=5), nullable=False),
        sa.Column(
            "state",
            sa.Enum(
                "learning",
                "review",
                "relearning",
                name="card_memory_state",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("step", sa.Integer(), nullable=True),
        sa.Column("stability", sa.Double(), nullable=True),
        sa.Column("difficulty", sa.Double(), nullable=True),
        sa.Column("due", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_review", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "learning_key", "prompt_side"),
        sa.CheckConstraint("user_id > 0", name="ck_card_memory_user_id_positive"),
        sa.CheckConstraint(
            "substring(learning_key::text from 15 for 1) = '7' "
            "AND substring(learning_key::text from 20 for 1) IN ('8', '9', 'a', 'b')",
            name="ck_card_memory_learning_key_v7",
        ),
        sa.CheckConstraint(
            "prompt_side IN ('front', 'back')",
            name="ck_card_memory_prompt_side_valid",
        ),
        sa.CheckConstraint(
            "(state = 'review') = (step IS NULL)",
            name="ck_card_memory_step_matches_state",
        ),
        sa.CheckConstraint("step >= 0", name="ck_card_memory_step_non_negative"),
        sa.CheckConstraint(
            "(stability IS NULL) = (difficulty IS NULL) "
            "AND (stability IS NULL) = (last_review IS NULL)",
            name="ck_card_memory_memory_fields_together",
        ),
        sa.CheckConstraint("stability >= 0.001", name="ck_card_memory_stability_min"),
        sa.CheckConstraint(
            "difficulty BETWEEN 1 AND 10",
            name="ck_card_memory_difficulty_range",
        ),
        sa.CheckConstraint(
            "due >= last_review",
            name="ck_card_memory_due_after_last_review",
        ),
    )


def downgrade() -> None:
    op.drop_table("card_memory_states")
