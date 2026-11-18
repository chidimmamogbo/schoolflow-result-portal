"""Migration 29: each school's own login page (CHANGE C, Chidimma 2026-11-17; D-182).

SPEC F02 rules 1, 2 and 11 to 14; AC24.4.

- schools gains its login page settings: login_layout ("half" or "behind"),
  login_picture ("pattern", "people" or "photo"), login_message (up to 80
  characters, one line) and login_photo_file_id (one of its own files). A
  photo picture needs a photo. School admins may change these four columns
  (still only in their own school, through check_school_admin_edit()).
- files accepts a new purpose, "login_photo", up to 2 MB after cleaning. The
  platform role may store login photos as well as logos.
- school_code_changes remembers each old school code and when it changed, so
  a login link with the old code forwards for 30 days. The owner-run trigger
  writes it; no app role can read or change it (row-level security, no grants).
- auth_school_public(code) now also returns the login page settings, answers
  for suspended schools too (their page looks normal; the paused message comes
  after login, AC24.3), and for a code changed in the last 30 days returns the
  school's current code so the page can forward.
- auth_school_logo(code) also answers for suspended schools;
  auth_school_login_photo(code) does the same for the login photo.
- auth_login_school(code): the id of the school with exactly this current
  code, so a login on /login/{code} can check the account belongs there.
- email_prepare(email, link_hash) also returns the school's code, so links in
  emails open the school's own pages (F02 rule 14). Its body is migration 26's,
  read from that file, with one more column.

Revision ID: c5e2a9d74f18
Revises: e91c3a7d5f02
Create Date: 2026-11-17 10:00:00.000000

"""

import importlib.util
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5e2a9d74f18"
down_revision: str | Sequence[str] | None = "e91c3a7d5f02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FORWARD_DAYS = 30


def migration_26() -> Any:
    """Migration 26's module, for email_prepare's body (one copy of it, not two)."""
    path = Path(__file__).with_name("2026_10_25_1200-b7e4c1d93f20_the_sender_prepares_an_email.py")
    spec = importlib.util.spec_from_file_location("migration_26", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot read {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def email_prepare_with_code(old: str) -> str:
    new = old.replace(
        "    link_expires_at timestamptz\n)",
        "    link_expires_at timestamptz,\n    school_code text\n)",
    ).replace(
        "select s.name, s.email, kind, expires\n",
        "select s.name, s.email, kind, expires, s.code\n",
    )
    if new.count("school_code text") != 1 or new.count("expires, s.code") != 1:
        raise RuntimeError("email_prepare in migration 26 is not what this migration expects")
    return "drop function email_prepare(uuid, bytea);\n" + new


TABLES = """
alter table schools
    add column login_layout text not null default 'half',
    add column login_picture text not null default 'pattern',
    add column login_message text,
    add column login_photo_file_id uuid,
    add constraint ck_schools_login_layout_allowed
        check (login_layout in ('half', 'behind')),
    add constraint ck_schools_login_picture_allowed
        check (login_picture in ('pattern', 'people', 'photo')),
    add constraint ck_schools_login_message_valid
        check (login_message is null or (
            btrim(login_message) <> ''
            and char_length(login_message) <= 80
            and login_message !~ '[\\r\\n]')),
    add constraint ck_schools_login_photo_when_chosen
        check (login_picture <> 'photo' or login_photo_file_id is not null),
    add constraint fk_schools_login_photo_file_id_files
        foreign key (login_photo_file_id, id) references files (id, school_id);

alter table files drop constraint ck_files_purpose_allowed;
alter table files add constraint ck_files_purpose_allowed
    check (purpose in ('logo', 'signature', 'stamp', 'correction_attachment', 'login_photo'));
alter table files drop constraint ck_files_size_within_limit;
alter table files add constraint ck_files_size_within_limit
    check (size_bytes between 1 and case
        when purpose = 'correction_attachment' then 4194304
        when purpose = 'login_photo' then 2097152
        else 1048576 end);

drop policy files_app_platform_logos on files;
create policy files_app_platform_logos on files
    for all to app_platform
    using (purpose in ('logo', 'login_photo'))
    with check (purpose in ('logo', 'login_photo'));

create table school_code_changes (
    id uuid primary key default gen_random_uuid(),
    school_id uuid not null references schools (id),
    old_code text not null,
    new_code text not null,
    changed_at timestamptz not null default now()
);
create index ix_school_code_changes_old_code on school_code_changes (old_code, changed_at);
alter table school_code_changes enable row level security;
revoke all on school_code_changes from public;

grant update (login_layout, login_picture, login_message, login_photo_file_id)
    on schools to app_user;
"""

FUNCTIONS = f"""
create function remember_school_code() returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if new.code is distinct from old.code then
        insert into public.school_code_changes (school_id, old_code, new_code)
        values (new.id, old.code, new.code);
    end if;
    return new;
end
$$;
revoke all on function remember_school_code() from public;

create trigger schools_remember_code
    after update of code on schools
    for each row execute function remember_school_code();

drop function auth_school_public(text);
create function auth_school_public(code text)
returns table (
    school_code text,
    school_name text,
    school_colour text,
    login_layout text,
    login_picture text,
    login_message text,
    has_logo boolean,
    has_photo boolean
)
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    with wanted as (select upper(btrim(auth_school_public.code)) as code),
    found as (
        select s.id, 0 as rank, now() as at
          from public.schools s, wanted w
         where s.code = w.code
        union all
        select c.school_id, 1, c.changed_at
          from public.school_code_changes c, wanted w
         where c.old_code = w.code
           and c.changed_at > now() - interval '{FORWARD_DAYS} days'
    )
    select s.code, s.name, s.colour, s.login_layout, s.login_picture, s.login_message,
           s.logo_file_id is not null,
           s.login_photo_file_id is not null
      from found f
      join public.schools s on s.id = f.id
     where s.status in ('active', 'suspended')
     order by f.rank, f.at desc
     limit 1
$$;
revoke all on function auth_school_public(text) from public;
grant execute on function auth_school_public(text) to app_user;

create or replace function auth_school_logo(code text)
returns table (storage_key text, content_type text, sha256 bytea)
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select f.storage_key, f.content_type, f.sha256
      from public.schools s
      join public.files f on f.id = s.logo_file_id and f.school_id = s.id
     where s.code = upper(btrim(auth_school_logo.code))
       and s.status in ('active', 'suspended')
       and f.purpose = 'logo'
$$;

create function auth_school_login_photo(code text)
returns table (storage_key text, content_type text, sha256 bytea)
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select f.storage_key, f.content_type, f.sha256
      from public.schools s
      join public.files f on f.id = s.login_photo_file_id and f.school_id = s.id
     where s.code = upper(btrim(auth_school_login_photo.code))
       and s.status in ('active', 'suspended')
       and f.purpose = 'login_photo'
$$;
revoke all on function auth_school_login_photo(text) from public;
grant execute on function auth_school_login_photo(text) to app_user;

create function auth_login_school(code text) returns uuid
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select s.id from public.schools s where s.code = upper(btrim(auth_login_school.code))
$$;
revoke all on function auth_login_school(text) from public;
grant execute on function auth_login_school(text) to app_user;
"""  # noqa: S608 (fixed text; FORWARD_DAYS is a constant)

UNDO = """
drop function auth_login_school(text);
drop function auth_school_login_photo(text);
create or replace function auth_school_logo(code text)
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
drop function auth_school_public(text);
create function auth_school_public(code text)
returns table (school_code text, school_name text, school_colour text)
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select s.code, s.name, s.colour
      from public.schools s
     where s.code = upper(btrim(auth_school_public.code))
       and s.status = 'active'
$$;
revoke all on function auth_school_public(text) from public;
grant execute on function auth_school_public(text) to app_user;
drop trigger schools_remember_code on schools;
drop function remember_school_code();
revoke update (login_layout, login_picture, login_message, login_photo_file_id)
    on schools from app_user;
drop table school_code_changes;
drop policy files_app_platform_logos on files;
create policy files_app_platform_logos on files
    for all to app_platform
    using (purpose = 'logo')
    with check (purpose = 'logo');
alter table files drop constraint ck_files_size_within_limit;
alter table files add constraint ck_files_size_within_limit
    check (size_bytes between 1 and case when purpose = 'correction_attachment'
        then 4194304 else 1048576 end);
alter table files drop constraint ck_files_purpose_allowed;
alter table files add constraint ck_files_purpose_allowed
    check (purpose in ('logo', 'signature', 'stamp', 'correction_attachment'));
alter table schools
    drop constraint fk_schools_login_photo_file_id_files,
    drop column login_photo_file_id,
    drop column login_message,
    drop column login_picture,
    drop column login_layout;
"""


def upgrade() -> None:
    """Upgrade schema."""
    # Hand-written (D-023): columns, one table, grants, a trigger and functions.
    op.execute(TABLES)
    op.execute(FUNCTIONS)
    op.execute(email_prepare_with_code(migration_26().FUNCTION))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("drop function email_prepare(uuid, bytea);\n" + migration_26().FUNCTION)
    op.execute(UNDO)
