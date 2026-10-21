"""Migration 21: counts and checks for the super admin's pages.

BUILD_PROMPT 9.2d; SPEC F24 rules 1 and 2, F25 rule 5; D-051.

app_platform cannot read pupils, result sheets or report documents (D-051),
yet the platform pages need a few facts about them. These functions run as
the owner (search path fixed, callable only by app_platform) and return
numbers or names, never records:

- platform_school_usage(school): active pupils, active staff (school admins,
  reviewers, teachers), parents, valid published reports, last audited
  activity.
- platform_unpublished_classes(school, level): the classes at that level with
  result sheets not yet published in the active term (F25 rule 5's
  confirmation names them).
- platform_username_taken(username): whether a staff, parent or super admin
  account already uses it (usernames are platform-wide, D-033; pupils'
  usernames are per school and do not count).
- platform_email_taken(email): whether any account uses that email (emails are
  platform-wide, D-033), so a principal is never refused by a database error.

No table changes.

Revision ID: c4d82f1e6a07
Revises: 7a3e51c90d2b
Create Date: 2026-10-22 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d82f1e6a07"
down_revision: str | Sequence[str] | None = "7a3e51c90d2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTIONS = (
    "platform_school_usage(uuid)",
    "platform_unpublished_classes(uuid, text)",
    "platform_username_taken(text)",
    "platform_email_taken(text)",
)

PLATFORM_RULES = """
create function platform_school_usage(school uuid)
returns table (
    students bigint, staff bigint, parents bigint, results_published bigint,
    last_activity timestamptz
)
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select
        (select count(*) from public.students s
          where s.school_id = platform_school_usage.school and s.status = 'active'),
        (select count(*) from public.school_memberships m
          where m.school_id = platform_school_usage.school and m.status = 'active'
            and m.role in ('school_admin', 'reviewer', 'teacher')),
        (select count(*) from public.school_memberships m
          where m.school_id = platform_school_usage.school and m.status = 'active'
            and m.role = 'parent'),
        (select count(*) from public.report_documents d
          where d.school_id = platform_school_usage.school and d.status = 'valid'),
        (select max(a.created_at) from public.audit_events a
          where a.school_id = platform_school_usage.school)
$$;

create function platform_unpublished_classes(school uuid, level text)
returns setof text
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select distinct c.name
      from public.classes c
      join public.class_arms a on a.class_id = c.id
      join public.result_sheets r on r.arm_id = a.id
      join public.terms t on t.id = r.term_id
     where c.school_id = platform_unpublished_classes.school
       and c.level = platform_unpublished_classes.level
       and t.is_active
       and r.status <> 'published'
     order by c.name
$$;

create function platform_username_taken(username text) returns boolean
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select exists (
        select 1 from public.users u
         where u.username = lower(btrim(platform_username_taken.username))
           and u.student_school_id is null
    )
$$;

create function platform_email_taken(email text) returns boolean
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select exists (
        select 1 from public.users u where u.email = lower(btrim(platform_email_taken.email))
    )
$$;
"""


def upgrade() -> None:
    """Upgrade schema."""
    # Hand-written (D-023): functions only.
    op.execute(PLATFORM_RULES)
    for function in FUNCTIONS:
        op.execute(f"revoke all on function {function} from public")
        op.execute(f"grant execute on function {function} to app_platform")


def downgrade() -> None:
    """Downgrade schema."""
    for function in FUNCTIONS:
        op.execute(f"drop function {function}")
