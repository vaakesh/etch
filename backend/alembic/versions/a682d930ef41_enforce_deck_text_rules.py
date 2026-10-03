"""Align deck title and description storage with the API contract.

Revision ID: a682d930ef41
Revises: d4280b751c9e
"""
from alembic import op
import sqlalchemy as sa

revision = "a682d930ef41"
down_revision = "d4280b751c9e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Validate before narrowing VARCHAR: never silently truncate existing titles.
    op.create_check_constraint('ck_deck_title_length', "decks", 'char_length(title) BETWEEN 3 AND 50')
    op.create_check_constraint('ck_deck_title_trimmed', "decks", "title = btrim(title, U&'\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')")
    op.create_check_constraint('ck_deck_title_single_line', "decks", "title = translate(title, U&'\\0009\\000A\\000B\\000C\\000D\\0085\\2028\\2029', '')")
    op.create_check_constraint('ck_deck_description_length', "decks", 'description IS NULL OR char_length(description) BETWEEN 1 AND 3000')
    op.create_check_constraint('ck_deck_description_trimmed', "decks", "description IS NULL OR description = btrim(description, U&'\\0009\\000A\\000B\\000C\\000D\\001C\\001D\\001E\\001F\\0020\\0085\\00A0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200A\\2028\\2029\\202F\\205F\\3000')")
    op.alter_column("decks", "title", existing_type=sa.String(150), type_=sa.String(50), existing_nullable=False)


def downgrade() -> None:
    op.alter_column("decks", "title", existing_type=sa.String(50), type_=sa.String(150), existing_nullable=False)
    op.drop_constraint('ck_deck_description_trimmed', "decks", type_="check")
    op.drop_constraint('ck_deck_description_length', "decks", type_="check")
    op.drop_constraint('ck_deck_title_single_line', "decks", type_="check")
    op.drop_constraint('ck_deck_title_trimmed', "decks", type_="check")
    op.drop_constraint('ck_deck_title_length', "decks", type_="check")
