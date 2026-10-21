"""Migration 22: school admins edit their school's details and level settings.

BUILD_PROMPT 9.2e; SPEC F04 (branding), F08 rule 0 (assessment mode per
level), F12 rule 0 (head's title); D-050, D-137.

Until now app_user could only read schools and school_levels. Here it may
update exactly these columns, in its own school only:

- schools: email, phone, address, city, state, country, colour and the logo.
  Never the name, code, status or school type (the super admin's).
- school_levels: assessment_mode and head_title. Never `enabled`: only the
  super admin switches levels (F25 rule 3).

check_school_admin_edit() makes sure the signed-in person is a school admin
of that school when app_user makes the change (the platform role and the
owner are not affected). No table changes.

Revision ID: e19b6c3d7f52
Revises: c4d82f1e6a07
Create Date: 2026-10-22 14:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e19b6c3d7f52"
down_revision: str | Sequence[str] | None = "c4d82f1e6a07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RULES = """
create function check_school_admin_edit() returns trigger
language plpgsql
as $$
declare
    school uuid;
begin
    if tg_table_name = 'schools' then
        school := new.id;
    else
        school := new.school_id;
    end if;
    if current_user = 'app_user' and not exists (
        select 1
          from school_memberships m
         where m.user_id = app_current_user_id()
           and m.school_id = school
           and m.role = 'school_admin'
           and m.status = 'active'
    ) then
        raise exception 'Only school admins change the school''s settings.'
            using errcode = 'check_violation',
                  constraint = 'school_settings_by_school_admin';
    end if;
    return new;
end
$$;

create trigger schools_edited_by_school_admin
    before update on schools
    for each row execute function check_school_admin_edit();
create trigger school_levels_edited_by_school_admin
    before update on school_levels
    for each row execute function check_school_admin_edit();

create policy schools_app_user_update_own on schools
    for update to app_user
    using (id = app_current_school_id())
    with check (id = app_current_school_id());
grant update (email, phone, address, city, state, country, colour, logo_file_id)
    on schools to app_user;

create policy school_levels_app_user_update_own on school_levels
    for update to app_user
    using (school_id = app_current_school_id())
    with check (school_id = app_current_school_id());
grant update (assessment_mode, head_title) on school_levels to app_user;
"""

UNDO = """
revoke update (assessment_mode, head_title) on school_levels from app_user;
drop policy school_levels_app_user_update_own on school_levels;
revoke update (email, phone, address, city, state, country, colour, logo_file_id)
    on schools from app_user;
drop policy schools_app_user_update_own on schools;
drop trigger school_levels_edited_by_school_admin on school_levels;
drop trigger schools_edited_by_school_admin on schools;
drop function check_school_admin_edit();
"""


def upgrade() -> None:
    """Upgrade schema."""
    # Hand-written (D-023): grants, policies and a trigger only.
    op.execute(RULES)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(UNDO)
