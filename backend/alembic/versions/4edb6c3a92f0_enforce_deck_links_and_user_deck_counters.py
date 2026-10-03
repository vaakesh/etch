"""Enforce deck link identifiers, archive source, and user deck counters.

Revision ID: 4edb6c3a92f0
Revises: c804f152ab63
"""
from alembic import op
import sqlalchemy as sa

revision = "4edb6c3a92f0"
down_revision = "c804f152ab63"
branch_labels = None
depends_on = None


DECK_CARD_UUID_V7 = (
    "substring(uuid::text from 15 for 1) = '7' "
    "AND substring(uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')"
)


def upgrade() -> None:
    op.create_check_constraint(
        "ck_deck_source_not_self", "decks",
        "source_deck_id IS NULL OR source_deck_id <> id",
    )
    op.create_check_constraint(
        "ck_deck_source_archive_owner", "decks",
        "source_deck_id IS NULL OR user_id = 1",
    )

    op.create_check_constraint("ck_deck_cards_id_positive", "deck_cards", "id > 0")
    op.create_check_constraint(
        "ck_deck_cards_deck_id_positive", "deck_cards", "deck_id > 0",
    )
    op.create_check_constraint(
        "ck_deck_cards_card_id_positive", "deck_cards", "card_id > 0",
    )
    op.create_check_constraint(
        "ck_deck_cards_uuid_v7", "deck_cards", DECK_CARD_UUID_V7,
    )
    op.create_check_constraint(
        "ck_deck_cards_dates_order", "deck_cards",
        "updated_at >= created_at",
    )

    op.create_check_constraint(
        "ck_user_decks_user_id_positive", "user_decks", "user_id > 0",
    )
    op.create_check_constraint(
        "ck_user_decks_deck_id_positive", "user_decks", "deck_id > 0",
    )
    for name in ("sessions_count", "correct_count", "wrong_count"):
        op.create_check_constraint(
            f"ck_user_decks_{name}_ge_0", "user_decks", f"{name} >= 0",
        )
        op.alter_column(
            "user_decks", name,
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default="0",
        )


def downgrade() -> None:
    for name in ("wrong_count", "correct_count", "sessions_count"):
        op.alter_column(
            "user_decks", name,
            existing_type=sa.Integer(),
            existing_nullable=False,
            server_default=None,
        )
        op.drop_constraint(
            f"ck_user_decks_{name}_ge_0", "user_decks", type_="check",
        )
    op.drop_constraint(
        "ck_user_decks_deck_id_positive", "user_decks", type_="check",
    )
    op.drop_constraint(
        "ck_user_decks_user_id_positive", "user_decks", type_="check",
    )

    op.drop_constraint("ck_deck_cards_dates_order", "deck_cards", type_="check")
    op.drop_constraint("ck_deck_cards_uuid_v7", "deck_cards", type_="check")
    op.drop_constraint("ck_deck_cards_card_id_positive", "deck_cards", type_="check")
    op.drop_constraint("ck_deck_cards_deck_id_positive", "deck_cards", type_="check")
    op.drop_constraint("ck_deck_cards_id_positive", "deck_cards", type_="check")

    op.drop_constraint("ck_deck_source_archive_owner", "decks", type_="check")
    op.drop_constraint("ck_deck_source_not_self", "decks", type_="check")
