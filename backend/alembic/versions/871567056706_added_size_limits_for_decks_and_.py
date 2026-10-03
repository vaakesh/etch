"""added size limits for decks and training sessions

Revision ID: 871567056706
Revises: 2079f8197d03
Create Date: 2026-09-04 18:07:01.063702

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '871567056706'
down_revision: Union[str, Sequence[str], None] = '2079f8197d03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_check_constraint(
        'ck_deck_words_count_le_max', 'decks', 'words_count <= 5000',
    )
    op.create_check_constraint(
        'ck_deck_cards_position_le_max', 'deck_cards', 'position <= 5000',
    )
    op.create_check_constraint(
        'ck_training_session_requested_count_ge_1',
        'training_sessions',
        'requested_count >= 1',
    )
    op.create_check_constraint(
        'ck_training_session_requested_count_le_max',
        'training_sessions',
        'requested_count <= 500',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'ck_training_session_requested_count_le_max',
        'training_sessions',
        type_='check',
    )
    op.drop_constraint(
        'ck_training_session_requested_count_ge_1',
        'training_sessions',
        type_='check',
    )
    op.drop_constraint(
        'ck_deck_cards_position_le_max', 'deck_cards', type_='check',
    )
    op.drop_constraint(
        'ck_deck_words_count_le_max', 'decks', type_='check',
    )
