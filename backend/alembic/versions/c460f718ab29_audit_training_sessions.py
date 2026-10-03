"""Preserve training history and enforce session and snapshot rules.

Revision ID: c460f718ab29
Revises: b359e607fa18
"""
from alembic import op
import sqlalchemy as sa

revision = "c460f718ab29"
down_revision = "b359e607fa18"
branch_labels = None
depends_on = None

# Frozen SQL: migrations must not import application model definitions.
CHECKS = [
    ('training_sessions', 'ck_training_session_activity_dates_order', 'activity_last_seen_at >= started_at'),
    ('training_sessions', 'ck_training_session_answer_counts', 'correct_count >= 0 AND wrong_count >= 0 AND correct_count::bigint + wrong_count::bigint = answered_count'),
    ('training_sessions', 'ck_training_session_answered_count_range', 'answered_count BETWEEN 0 AND requested_count'),
    ('training_sessions', 'ck_training_session_completed_count', "status <> 'completed' OR answered_count = requested_count"),
    ('training_sessions', 'ck_training_session_dates_order', 'finished_at >= started_at'),
    ('training_sessions', 'ck_training_session_deck_id_positive', 'deck_id > 0'),
    ('training_sessions', 'ck_training_session_finish_state', "(status = 'in_progress') = (finished_at IS NULL)"),
    ('training_sessions', 'ck_training_session_finished_activity_empty', "status = 'in_progress' OR (activity_tracker_uuid IS NULL AND activity_last_seen_at IS NULL)"),
    ('training_sessions', 'ck_training_session_tracker_uuid_v7', "substring(activity_tracker_uuid::text from 15 for 1) = '7' AND substring(activity_tracker_uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')"),
    ('training_sessions', 'ck_training_session_user_id_positive', 'user_id > 0'),
    ('training_sessions', 'ck_training_session_uuid_v7', "substring(uuid::text from 15 for 1) = '7' AND substring(uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')"),
    ('training_session_items', 'ck_training_session_item_answer_date_state', 'is_answered = (answered_at IS NOT NULL)'),
    ('training_session_items', 'ck_training_session_item_answer_lang_format', "answer_lang ~ '^[a-z]{2,3}$' AND char_length(answer_lang) BETWEEN 2 AND 3"),
    ('training_session_items', 'ck_training_session_item_answer_text_length', 'char_length(answer_text) BETWEEN 1 AND 255'),
    ('training_session_items', 'ck_training_session_item_answer_text_state', '(is_answered OR user_typed_text IS NULL) AND (is_correct IS NOT TRUE OR user_typed_text IS NOT NULL)'),
    ('training_session_items', 'ck_training_session_item_answer_text_trimmed', "answer_text = btrim(answer_text, U&'\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')"),
    ('training_session_items', 'ck_training_session_item_card_id_positive', 'original_card_id > 0'),
    ('training_session_items', 'ck_training_session_item_id_positive', 'id > 0'),
    ('training_session_items', 'ck_training_session_item_prompt_lang_format', "prompt_lang ~ '^[a-z]{2,3}$' AND char_length(prompt_lang) BETWEEN 2 AND 3"),
    ('training_session_items', 'ck_training_session_item_prompt_text_length', 'char_length(prompt_text) BETWEEN 1 AND 255'),
    ('training_session_items', 'ck_training_session_item_prompt_text_trimmed', "prompt_text = btrim(prompt_text, U&'\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')"),
    ('training_session_items', 'ck_training_session_item_sequence_le_max', 'sequence_number <= 500'),
    ('training_session_items', 'ck_training_session_item_session_id_positive', 'training_session_id > 0'),
    ('training_session_items', 'ck_training_session_item_user_typed_text_length', 'char_length(user_typed_text) BETWEEN 1 AND 255'),
    ('training_session_items', 'ck_training_session_item_user_typed_text_trimmed', "user_typed_text = btrim(user_typed_text, U&'\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')"),
    ('training_session_items', 'ck_training_session_item_uuid_v7', "substring(uuid::text from 15 for 1) = '7' AND substring(uuid::text from 20 for 1) IN ('8', '9', 'a', 'b')"),
]


def upgrade() -> None:
    op.alter_column("training_sessions", "actual_count", new_column_name="answered_count")
    op.alter_column("training_sessions", "deck_id", existing_type=sa.BigInteger(), nullable=True)
    op.drop_constraint("training_sessions_deck_id_fkey", "training_sessions", type_="foreignkey")
    op.create_foreign_key("training_sessions_deck_id_fkey", "training_sessions", "decks", ["deck_id"], ["id"], ondelete="SET NULL")
    op.add_column("training_session_items", sa.Column("original_card_id", sa.BigInteger(), nullable=True))
    op.execute("""
        UPDATE training_session_items AS item SET original_card_id = card.id
        FROM cards AS card WHERE card.uuid = item.original_card_uuid
    """)
    op.create_foreign_key("training_session_items_original_card_id_fkey", "training_session_items", "cards", ["original_card_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_training_session_items_original_card_id", "training_session_items", ["original_card_id"])
    op.create_unique_constraint("uq_training_session_item_original_card", "training_session_items", ["training_session_id", "original_card_id"])
    for table, name, sql in CHECKS:
        op.create_check_constraint(name, table, sql)
    for field in ("prompt_text", "answer_text", "user_typed_text"):
        op.alter_column("training_session_items", field, existing_type=sa.Text(), type_=sa.String(255))
    op.drop_index("ix_training_session_items_original_card_uuid", table_name="training_session_items")
    op.drop_column("training_session_items", "original_card_uuid")


def downgrade() -> None:
    # The old schema cannot represent missing decks/cards. Fail rather than
    # deleting history or fabricating an identity to satisfy NOT NULL.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM training_sessions WHERE deck_id IS NULL)
                OR EXISTS (SELECT 1 FROM training_session_items WHERE original_card_id IS NULL)
            THEN
                RAISE EXCEPTION 'Cannot downgrade: training history has deleted decks or cards';
            END IF;
        END $$;
    """)
    op.add_column("training_session_items", sa.Column("original_card_uuid", sa.UUID(), nullable=True))
    op.execute("""
        UPDATE training_session_items AS item SET original_card_uuid = card.uuid
        FROM cards AS card WHERE card.id = item.original_card_id
    """)
    op.alter_column("training_session_items", "original_card_uuid", nullable=False)
    op.create_index("ix_training_session_items_original_card_uuid", "training_session_items", ["original_card_uuid"])
    for field in ("prompt_text", "answer_text", "user_typed_text"):
        op.alter_column("training_session_items", field, existing_type=sa.String(255), type_=sa.Text())
    for table, name, _ in reversed(CHECKS):
        op.drop_constraint(name, table, type_="check")
    op.drop_constraint("uq_training_session_item_original_card", "training_session_items", type_="unique")
    op.drop_constraint("training_session_items_original_card_id_fkey", "training_session_items", type_="foreignkey")
    op.drop_index("ix_training_session_items_original_card_id", table_name="training_session_items")
    op.drop_column("training_session_items", "original_card_id")
    op.drop_constraint("training_sessions_deck_id_fkey", "training_sessions", type_="foreignkey")
    op.create_foreign_key("training_sessions_deck_id_fkey", "training_sessions", "decks", ["deck_id"], ["id"], ondelete="CASCADE")
    op.alter_column("training_sessions", "deck_id", existing_type=sa.BigInteger(), nullable=False)
    op.alter_column("training_sessions", "answered_count", new_column_name="actual_count")
