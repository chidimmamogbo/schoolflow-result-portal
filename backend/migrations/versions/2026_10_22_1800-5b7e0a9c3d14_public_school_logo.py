"""Migration 23: the school logo for the public login page.

Approved CHANGE (Chidimma, 2026-10-22); SPEC F02 rule 2, AT-09.6; D-056.

auth_school_logo(code): owner-run, callable only by app_user, returns the
storage key, type and hash of an active school's logo, and only a file whose
purpose is "logo" (never a signature, stamp or attachment). No table changes.

Revision ID: 5b7e0a9c3d14
Revises: e19b6c3d7f52
Create Date: 2026-10-22 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b7e0a9c3d14"
down_revision: str | Sequence[str] | None = "e19b6c3d7f52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RULES = """
create function auth_school_logo(code text)
returns table (storage_key text, content_type text, sha256 bytea)
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select f.storage_key, f.content_type, f.sha256
      from public.schools s
      join public.files f on f.id = s.logo_file_id and f.school_id = s.id
     where s.code = upper(btrim(auth_school_logo.code))
       and s.status = 'active'
       and f.purpose = 'logo'
$$;

revoke all on function auth_school_logo(text) from public;
grant execute on function auth_school_logo(text) to app_user;
"""


def upgrade() -> None:
    """Upgrade schema."""
    # Hand-written (D-023): one function.
    op.execute(RULES)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("drop function auth_school_logo(text)")
