"""Protect the archive account and prevent ownership transfers.

Revision ID: d4280b751c9e
Revises: a037d81ef942
"""

from alembic import op

revision = "d4280b751c9e"
down_revision = "a037d81ef942"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.execute("""
        CREATE FUNCTION prevent_owner_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.user_id IS DISTINCT FROM OLD.user_id THEN
                RAISE EXCEPTION 'Ownership cannot be transferred; create a copy instead'
                    USING ERRCODE = '23514', CONSTRAINT = 'owner_immutable';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    for table in ("cards", "decks"):
        op.execute(f"""
            CREATE TRIGGER {table}_owner_immutable
            BEFORE UPDATE OF user_id ON {table}
            FOR EACH ROW EXECUTE FUNCTION prevent_owner_change()
        """)


def downgrade() -> None:
    for table in ("decks", "cards"):
        op.execute(f"DROP TRIGGER {table}_owner_immutable ON {table}")
    op.execute("DROP FUNCTION prevent_owner_change()")
    op.execute("DROP TRIGGER protect_archive_user_truncate ON users")
    op.execute("DROP TRIGGER protect_archive_user_row ON users")
    op.execute("DROP FUNCTION protect_archive_user()")
