"""collapse user_role enum to a single OFFICER value

The Python UserRole model was hand-edited to a single OFFICER role
earlier, but the actual Postgres enum type was never migrated — it
still had the original 4 values (FIELD_OFFICER/IMMIGRATION_OFFICER/
SUPERVISOR/IT_ADMIN), so every existing user row except one still had
its old role value stored. That value no longer matches any member of
the Python UserRole enum, so logging in as those accounts raised a hard
LookupError at the ORM layer. This migration actually does what the
Python-side change already claimed: every existing user becomes
OFFICER, and the enum type itself only allows OFFICER going forward.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-18
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(32) USING role::text")
    op.execute("UPDATE users SET role = 'OFFICER'")
    op.execute("DROP TYPE user_role")
    op.execute("CREATE TYPE user_role AS ENUM ('OFFICER')")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::user_role")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'OFFICER'")


def downgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(32) USING role::text")
    op.execute("DROP TYPE user_role")
    op.execute(
        "CREATE TYPE user_role AS ENUM "
        "('FIELD_OFFICER', 'IMMIGRATION_OFFICER', 'SUPERVISOR', 'IT_ADMIN')"
    )
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::user_role")
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'FIELD_OFFICER'")
