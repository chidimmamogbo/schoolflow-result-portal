"""Migration 27: a new parent joins from a school's link request (D-138, D-177).

BUILD_PROMPT 9.2 (email sender, new-parent route); SPEC F03 rule 8;
CHANGE 2026-10-29 (the public /auth/join route).

A link request to an email with no SchoolFlow account carries a link whose
hash the sender stored on the request (migration 26). Nobody is signed in when
the parent opens it, so row-level security hides the request from the app.
One owner-run function (search path fixed, callable only by app_user) does
exactly the join and nothing else:

- join_parent_link(link_hash, password_hash): for an open, unexpired request
  of an active school whose guardian has no login yet, matching the hash,
  creates the parent account (the request's email, already verified: only
  its owner could read the link; the password hash made by the app; the
  guardian's name; a username made from that name, numbered when taken), the
  parent membership, the guardian's login link, and accepts the request.
  Returns (account, 'joined'). If the email has gained an account since,
  returns (null, 'email_has_account') and changes nothing: that person logs
  in and accepts. Anything else returns (null, 'invalid').

No table changes.

Revision ID: d2a8f61e4b57
Revises: b7e4c1d93f20
Create Date: 2026-10-29 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2a8f61e4b57"
down_revision: str | Sequence[str] | None = "b7e4c1d93f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTION = """
create function join_parent_link(link_hash bytea, password_hash text)
returns table (account uuid, outcome text)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    wanted record;
    base text;
    chosen text;
    n integer := 1;
    created uuid := gen_random_uuid();
begin
    select r.id, r.school_id, r.guardian_id, r.email, g.full_name into wanted
      from public.parent_link_requests r
      join public.schools s on s.id = r.school_id
      join public.guardians g on g.id = r.guardian_id and g.school_id = r.school_id
     where r.token_hash = join_parent_link.link_hash
       and r.accepted_at is null and r.declined_at is null and r.cancelled_at is null
       and r.expires_at > now()
       and s.status = 'active'
       and g.user_id is null
     for update of r;
    if not found then
        return query select null::uuid, 'invalid'::text;
        return;
    end if;

    if exists (select 1 from public.users u where u.email = wanted.email) then
        return query select null::uuid, 'email_has_account'::text;
        return;
    end if;

    -- "Chiamaka Eze-Obi" becomes chiamaka.eze.obi; a name with no plain letters
    -- becomes parent. Staff and parent usernames are unique platform-wide.
    base := left(btrim(regexp_replace(lower(wanted.full_name), '[^a-z0-9]+', '.', 'g'), '.'), 24);
    base := rtrim(base, '.');
    if char_length(base) < 3 then
        base := 'parent';
    end if;
    chosen := base;
    while exists (
        select 1 from public.users u where u.student_school_id is null and u.username = chosen
    ) loop
        n := n + 1;
        chosen := base || '.' || n;
    end loop;

    insert into public.users (id, full_name, username, email, password_hash, email_verified_at)
    values (created, btrim(wanted.full_name), chosen, wanted.email,
            join_parent_link.password_hash, now());
    insert into public.school_memberships (user_id, school_id, role, status)
    values (created, wanted.school_id, 'parent', 'active');
    update public.guardians g set user_id = created where g.id = wanted.guardian_id;
    update public.parent_link_requests r set accepted_at = now() where r.id = wanted.id;
    return query select created, 'joined'::text;
end
$$;

revoke all on function join_parent_link(bytea, text) from public;
grant execute on function join_parent_link(bytea, text) to app_user;
"""


def upgrade() -> None:
    """Upgrade schema."""
    # Hand-written (D-023): one function, no tables.
    op.execute(FUNCTION)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("drop function join_parent_link(bytea, text)")
