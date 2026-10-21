"""Migration 24: a parent answers a school's link request (D-138, D-140).

BUILD_PROMPT 9.2e part 2b; SPEC F03 rule 8; AT-31.4, AT-31.5, AC03.7, AC03.8.

A link request belongs to the school that sent it, so row-level security
hides it from the parent. These owner-run functions (search path fixed,
callable only by app_user) let the signed-in parent, and only them, see and
answer the requests sent to their own verified email:

- my_parent_link_requests(): the open, unexpired requests for that email,
  with the school's name and code and the name the school typed.
- accept_parent_link_request(id): links the parent's account to the school
  (a parent membership, made as the parent, so the consent rule of migration
  3 is satisfied) and to the school's guardian record; returns the school.
- decline_parent_link_request(id): records the answer.

Only an active account with a verified email that is not staff or a pupil
can answer (staff who are also parents are a future upgrade, D-138 3A).
Every refusal looks like "no such request". No table changes.

Revision ID: 8c1f4d2b6e93
Revises: 5b7e0a9c3d14
Create Date: 2026-10-22 20:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c1f4d2b6e93"
down_revision: str | Sequence[str] | None = "5b7e0a9c3d14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTIONS = (
    "my_parent_link_requests()",
    "accept_parent_link_request(uuid)",
    "decline_parent_link_request(uuid)",
)

RULES = """
-- The signed-in account's verified email, if it may answer link requests.
create function app_parent_answer_email() returns text
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select u.email
      from public.users u
     where u.id = public.app_current_user_id()
       and u.is_active
       and u.email is not null
       and u.email_verified_at is not null
       and u.student_school_id is null
       and not u.is_super_admin
       and not exists (
           select 1 from public.school_memberships m
            where m.user_id = u.id and m.role <> 'parent'
       )
$$;

revoke all on function app_parent_answer_email() from public;

create function my_parent_link_requests()
returns table (
    id uuid, school_id uuid, school_name text, school_code text, guardian_name text,
    created_at timestamptz, expires_at timestamptz
)
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select r.id, s.id, s.name, s.code, g.full_name, r.created_at, r.expires_at
      from public.parent_link_requests r
      join public.schools s on s.id = r.school_id
      join public.guardians g on g.id = r.guardian_id
     where r.email = public.app_parent_answer_email()
       and r.accepted_at is null and r.declined_at is null and r.cancelled_at is null
       and r.expires_at > now()
       and s.status = 'active'
     order by r.created_at
$$;

create function accept_parent_link_request(request uuid) returns uuid
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    wanted record;
    me uuid := public.app_current_user_id();
begin
    select r.id, r.school_id, r.guardian_id into wanted
      from public.parent_link_requests r
     where r.id = accept_parent_link_request.request
       and r.email = public.app_parent_answer_email()
       and r.accepted_at is null and r.declined_at is null and r.cancelled_at is null
       and r.expires_at > now()
     for update;
    if not found then
        return null;
    end if;

    if not exists (
        select 1 from public.school_memberships m
         where m.user_id = me and m.school_id = wanted.school_id
    ) then
        insert into public.school_memberships (user_id, school_id, role, status)
        values (me, wanted.school_id, 'parent', 'active');
    end if;
    update public.guardians g
       set user_id = me
     where g.id = wanted.guardian_id and g.user_id is null;
    update public.parent_link_requests r
       set accepted_at = now()
     where r.id = wanted.id;
    return wanted.school_id;
end
$$;

create function decline_parent_link_request(request uuid) returns boolean
language sql
security definer
set search_path = pg_catalog, public
as $$
    with answered as (
        update public.parent_link_requests r
           set declined_at = now()
         where r.id = decline_parent_link_request.request
           and r.email = public.app_parent_answer_email()
           and r.accepted_at is null and r.declined_at is null and r.cancelled_at is null
           and r.expires_at > now()
        returning 1
    )
    select exists (select 1 from answered)
$$;
"""


def upgrade() -> None:
    """Upgrade schema."""
    # Hand-written (D-023): functions only.
    op.execute(RULES)
    for function in FUNCTIONS:
        op.execute(f"revoke all on function {function} from public")
        op.execute(f"grant execute on function {function} to app_user")


def downgrade() -> None:
    """Downgrade schema."""
    for function in FUNCTIONS:
        op.execute(f"drop function {function}")
    op.execute("drop function app_parent_answer_email()")
