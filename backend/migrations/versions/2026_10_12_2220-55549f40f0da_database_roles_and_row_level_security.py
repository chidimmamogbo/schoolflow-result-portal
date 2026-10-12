"""Migration 2: database roles and row-level security for migration 1's tables.

D-026, D-027, D-051, D-137. Hand-written SQL (Alembic cannot generate roles,
grants or policies).

- Three roles the app logs in as. None of them owns tables, is a superuser or
  can bypass row-level security (RLS); the migration refuses to run if one can.
  app_user: every school request. app_platform: super admin pages only.
  app_verifier: public QR verification only (no access yet). Logins and
  passwords are added per environment, outside git.
- Two helpers that RLS rules call: app_current_school_id() and
  app_current_user_id(). They read the settings db.use_context() sets in each
  transaction and turn "not set" (NULL or the empty string a reused connection
  returns) into NULL, so a request without a school sees no school rows.
- RLS on schools, school_features and school_levels: app_user reads only its
  own school; only app_platform (the super admin) changes them. School users
  can read platform_settings; only the platform changes them.
- Downgrade keeps the roles: roles belong to the whole database server and
  other databases on it may still use them.

Revision ID: 55549f40f0da
Revises: 32f732df750b
Create Date: 2026-10-12 22:20:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "55549f40f0da"
down_revision: str | Sequence[str] | None = "32f732df750b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLES = "app_user, app_platform, app_verifier"

CREATE_ROLES = """
do $$
declare
    role_name text;
begin
    foreach role_name in array array['app_user', 'app_platform', 'app_verifier'] loop
        if not exists (select from pg_roles where rolname = role_name) then
            execute format(
                'create role %I nologin nosuperuser nocreatedb nocreaterole'
                ' noreplication nobypassrls',
                role_name
            );
        end if;
    end loop;

    -- Safety catch (D-137): on Neon, a role made in the Console can bypass RLS.
    if exists (
        select from pg_roles
         where rolname in ('app_user', 'app_platform', 'app_verifier')
           and (rolsuper or rolbypassrls or rolcreaterole or rolcreatedb)
    ) then
        raise exception
            'An app role can bypass row-level security or create roles or databases.'
            ' Recreate it with SQL (see D-137) before running migrations.';
    end if;
end
$$;
"""

HELPERS = """
create function app_current_school_id() returns uuid
language sql stable
as $$ select nullif(current_setting('app.school_id', true), '')::uuid $$;

comment on function app_current_school_id() is
    'The school this transaction works for (D-027), or NULL when none is set.';

create function app_current_user_id() returns uuid
language sql stable
as $$ select nullif(current_setting('app.user_id', true), '')::uuid $$;

comment on function app_current_user_id() is
    'The signed-in user this transaction works for (D-137), or NULL when none is set.';
"""

POLICIES = """
alter table schools enable row level security;
create policy schools_app_user_read_own on schools
    for select to app_user using (id = app_current_school_id());
create policy schools_app_platform_all on schools
    for all to app_platform using (true) with check (true);

alter table school_features enable row level security;
create policy school_features_app_user_read_own on school_features
    for select to app_user using (school_id = app_current_school_id());
create policy school_features_app_platform_all on school_features
    for all to app_platform using (true) with check (true);

alter table school_levels enable row level security;
create policy school_levels_app_user_read_own on school_levels
    for select to app_user using (school_id = app_current_school_id());
create policy school_levels_app_platform_all on school_levels
    for all to app_platform using (true) with check (true);
"""

GRANTS = f"""
grant usage on schema public to {APP_ROLES};

grant select on schools, school_features, school_levels, platform_settings to app_user;
grant select, insert, update
    on schools, school_features, school_levels, platform_settings to app_platform;
"""


def upgrade() -> None:
    op.execute(CREATE_ROLES)
    op.execute(HELPERS)
    op.execute(POLICIES)
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute(
        f"revoke all on schools, school_features, school_levels, platform_settings from {APP_ROLES}"
    )
    for table, policies in {
        "schools": ("schools_app_user_read_own", "schools_app_platform_all"),
        "school_features": (
            "school_features_app_user_read_own",
            "school_features_app_platform_all",
        ),
        "school_levels": ("school_levels_app_user_read_own", "school_levels_app_platform_all"),
    }.items():
        for policy in policies:
            op.execute(f"drop policy {policy} on {table}")
        op.execute(f"alter table {table} disable row level security")
    op.execute("drop function app_current_user_id()")
    op.execute("drop function app_current_school_id()")
    op.execute(f"revoke usage on schema public from {APP_ROLES}")
