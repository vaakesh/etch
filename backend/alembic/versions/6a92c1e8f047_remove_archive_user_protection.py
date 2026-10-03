"""Remove special database restrictions for the archive account.

Revision ID: 6a92c1e8f047
Revises: e682b930cd41
"""

from alembic import op

revision = "6a92c1e8f047"
down_revision = "e682b930cd41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_deck_source_archive_owner", "decks", type_="check")
    op.execute("DROP TRIGGER protect_archive_user_truncate ON users")
    op.execute("DROP TRIGGER protect_archive_user_row ON users")
    op.execute("DROP FUNCTION protect_archive_user()")


def downgrade() -> None:
    op.create_check_constraint(
        "ck_deck_source_archive_owner",
        "decks",
        "source_deck_id IS NULL OR user_id = 1",
    )
    op.execute("""
        CREATE FUNCTION protect_archive_user() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'TRUNCATE' THEN
                RAISE EXCEPTION 'Cannot truncate users: archive user is protected'
                    USING ERRCODE = '23514', CONSTRAINT = 'archive_user_protected';
            END IF;
            IF OLD.id = 1 THEN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'Cannot delete archive user'
                        USING ERRCODE = '23514', CONSTRAINT = 'archive_user_protected';
                ELSIF NEW.id IS DISTINCT FROM OLD.id THEN
                    RAISE EXCEPTION 'Cannot change archive user ID'
                        USING ERRCODE = '23514', CONSTRAINT = 'archive_user_protected';
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER protect_archive_user_row
        BEFORE DELETE OR UPDATE OF id ON users
        FOR EACH ROW EXECUTE FUNCTION protect_archive_user()
    """)
    op.execute("""
        CREATE TRIGGER protect_archive_user_truncate
        BEFORE TRUNCATE ON users
        FOR EACH STATEMENT EXECUTE FUNCTION protect_archive_user()
    """)
