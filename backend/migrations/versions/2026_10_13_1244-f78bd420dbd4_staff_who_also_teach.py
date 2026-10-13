"""Migration 10: staff who also teach (D-144; approved CHANGE, 2026-10-13).

School admins and reviewers can also hold teacher assignments and class
assistant places; on those sheets they act as teachers, and separation of
duties still stops them reviewing or approving what they submitted.

- check_member_role() (migration 7) now accepts a list of roles separated by
  "|" and an optional rule name. Existing uses with one role behave exactly
  as before (same rule names).
- The login rules on teacher_assignments and class_assistants accept
  teacher, school_admin or reviewer, named
  teacher_assignments_teacher_id_is_staff and
  class_assistants_assistant_id_is_staff.

Revision ID: f78bd420dbd4
Revises: 5fb9cabe6e74
Create Date: 2026-10-13 12:44:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f78bd420dbd4"
down_revision: str | Sequence[str] | None = "5fb9cabe6e74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAFF = "teacher|school_admin|reviewer"

ROLE_LIST_RULE = """
create or replace function check_member_role() returns trigger
language plpgsql
as $$
declare
    member uuid;
begin
    -- tg_argv[0]: the login column; tg_argv[1]: allowed roles, separated by |;
    -- tg_argv[2] (optional): the rule's name when several roles are allowed.
    member := (to_jsonb(new) ->> tg_argv[0])::uuid;
    if member is not null and not exists (
        select 1
          from school_memberships m
         where m.user_id = member
           and m.school_id = new.school_id
           and m.role = any (string_to_array(tg_argv[1], '|'))
    ) then
        raise exception 'This login cannot be used here (allowed: %).',
            replace(tg_argv[1], '|', ', ')
            using errcode = 'check_violation',
                  constraint = coalesce(
                      tg_argv[2], tg_table_name || '_' || tg_argv[0] || '_is_' || tg_argv[1]
                  );
    end if;
    return new;
end
$$;
"""

SINGLE_ROLE_RULE = """
create or replace function check_member_role() returns trigger
language plpgsql
as $$
declare
    member uuid;
begin
    -- tg_argv[0] names the login column, tg_argv[1] the role it must have.
    member := (to_jsonb(new) ->> tg_argv[0])::uuid;
    if member is not null and not exists (
        select 1
          from school_memberships m
         where m.user_id = member
           and m.school_id = new.school_id
           and m.role = tg_argv[1]
    ) then
        raise exception 'This login is not a % of this school.', tg_argv[1]
            using errcode = 'check_violation',
                  constraint = tg_table_name || '_' || tg_argv[0] || '_is_' || tg_argv[1];
    end if;
    return new;
end
$$;
"""


def upgrade() -> None:
    op.execute(ROLE_LIST_RULE)
    op.execute("drop trigger teacher_assignments_login_is_a_teacher on teacher_assignments")
    op.execute(
        f"""
create trigger teacher_assignments_login_is_staff
    before insert or update of teacher_id, school_id on teacher_assignments
    for each row execute function check_member_role(
        'teacher_id', '{STAFF}', 'teacher_assignments_teacher_id_is_staff'
    );
"""
    )
    op.execute("drop trigger class_assistants_login_is_a_teacher on class_assistants")
    op.execute(
        f"""
create trigger class_assistants_login_is_staff
    before insert or update of assistant_id, school_id on class_assistants
    for each row execute function check_member_role(
        'assistant_id', '{STAFF}', 'class_assistants_assistant_id_is_staff'
    );
"""
    )


def downgrade() -> None:
    op.execute("drop trigger class_assistants_login_is_staff on class_assistants")
    op.execute(
        """
create trigger class_assistants_login_is_a_teacher
    before insert or update of assistant_id, school_id on class_assistants
    for each row execute function check_member_role('assistant_id', 'teacher');
"""
    )
    op.execute("drop trigger teacher_assignments_login_is_staff on teacher_assignments")
    op.execute(
        """
create trigger teacher_assignments_login_is_a_teacher
    before insert or update of teacher_id, school_id on teacher_assignments
    for each row execute function check_member_role('teacher_id', 'teacher');
"""
    )
    op.execute(SINGLE_ROLE_RULE)
