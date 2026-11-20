"""Migration 30: two-factor login for the super admin (CHANGE D, Chidimma 2026-11-20; D-043, D-183).

SPEC F02 rule 11; F24.

- users gains totp_secret (the authenticator secret, encrypted by the app
  with TOTP_ENCRYPTION_KEY before it is stored), totp_confirmed_at and
  totp_last_step (the last 30-second step used, so a code works once).
  No app role can read or change these columns directly.
- recovery_codes: one row per one-time recovery code (HMAC hash only).
  Row-level security on, no policies, no grants.
- user_sessions gains second_factor_pending: a session made by a correct
  password that still waits for the code. It lasts 5 minutes and the app
  refuses it everywhere except the two-factor routes.
- Owner-run functions, callable only by app_user, each for the signed-in
  super admin only (app_current_user_id()):
  auth_totp_state(), auth_totp_start(secret), auth_totp_use_step(step),
  auth_totp_confirm(code_hashes), auth_recovery_replace(code_hashes),
  auth_recovery_use(code_hash), auth_recovery_left(),
  auth_second_factor_passed(session, new_hash, lifetime).

Revision ID: d7a3f1c58e24
Revises: c5e2a9d74f18
Create Date: 2026-11-20 10:00:00.000000

"""

# ruff: noqa: S608 -- every SQL text here is fixed; READABLE and the names are constants.
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7a3f1c58e24"
down_revision: str | Sequence[str] | None = "c5e2a9d74f18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The users columns the app's roles could read before this migration (all of them).
READABLE = (
    "id, full_name, username, email, password_hash, must_change_password,"
    " temp_password_expires_at, is_active, email_verified_at, is_super_admin,"
    " student_school_id, created_at, updated_at"
)

TABLES = f"""
alter table users
    add column totp_secret bytea,
    add column totp_confirmed_at timestamptz,
    add column totp_last_step bigint,
    add constraint ck_users_totp_only_super_admin
        check (totp_secret is null or is_super_admin),
    add constraint ck_users_totp_confirmed_needs_secret
        check (totp_confirmed_at is null or totp_secret is not null);

create table recovery_codes (
    id uuid not null default gen_random_uuid(),
    user_id uuid not null,
    code_hash bytea not null,
    created_at timestamptz not null default now(),
    used_at timestamptz,
    constraint pk_recovery_codes primary key (id),
    constraint fk_recovery_codes_user_id_users
        foreign key (user_id) references users (id) on delete cascade,
    constraint uq_recovery_codes_code_hash unique (code_hash),
    constraint ck_recovery_codes_hash_length check (octet_length(code_hash) = 32)
);
create index ix_recovery_codes_user_id on recovery_codes (user_id);
alter table recovery_codes enable row level security;
revoke all on recovery_codes from public;

-- Migration 3's "grant select, update (columns)" gave SELECT on the whole table
-- (the column list belongs to UPDATE only), so every new column would be readable.
-- Read rights become exactly today's columns; the two-factor columns stay closed.
revoke select on users from app_user, app_platform;
grant select ({READABLE}) on users to app_user, app_platform;

alter table user_sessions
    add column second_factor_pending boolean not null default false;
grant insert (second_factor_pending) on user_sessions to app_user;
"""

FUNCTIONS = """
create function auth_is_super_admin() returns boolean
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select coalesce((select u.is_super_admin and u.is_active
                       from public.users u where u.id = public.app_current_user_id()), false)
$$;
revoke all on function auth_is_super_admin() from public;

create function auth_totp_state()
returns table (secret bytea, confirmed boolean)
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select u.totp_secret, u.totp_confirmed_at is not null
      from public.users u
     where u.id = public.app_current_user_id() and public.auth_is_super_admin()
$$;

-- A new secret only while two-factor is not yet confirmed (set-up, or after a reset).
create function auth_totp_start(secret bytea) returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if not public.auth_is_super_admin() then
        return false;
    end if;
    update public.users u
       set totp_secret = auth_totp_start.secret, totp_last_step = null
     where u.id = public.app_current_user_id() and u.totp_confirmed_at is null;
    return found;
end
$$;

-- A code's 30-second step counts once: a later step only (no replay).
create function auth_totp_use_step(step bigint) returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if not public.auth_is_super_admin() then
        return false;
    end if;
    update public.users u
       set totp_last_step = auth_totp_use_step.step
     where u.id = public.app_current_user_id()
       and u.totp_secret is not null
       and (u.totp_last_step is null or u.totp_last_step < auth_totp_use_step.step);
    return found;
end
$$;

create function auth_recovery_replace(code_hashes bytea[]) returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if not public.auth_is_super_admin() or cardinality(code_hashes) <> 10 then
        return false;
    end if;
    delete from public.recovery_codes r where r.user_id = public.app_current_user_id();
    insert into public.recovery_codes (user_id, code_hash)
    select public.app_current_user_id(), h from unnest(code_hashes) h;
    return true;
end
$$;

create function auth_totp_confirm(code_hashes bytea[]) returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if not public.auth_is_super_admin() then
        return false;
    end if;
    update public.users u
       set totp_confirmed_at = now()
     where u.id = public.app_current_user_id()
       and u.totp_secret is not null and u.totp_confirmed_at is null;
    if not found then
        return false;
    end if;
    return public.auth_recovery_replace(code_hashes);
end
$$;

create function auth_recovery_use(code_hash bytea) returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if not public.auth_is_super_admin() then
        return false;
    end if;
    update public.recovery_codes r
       set used_at = now()
     where r.user_id = public.app_current_user_id()
       and r.code_hash = auth_recovery_use.code_hash
       and r.used_at is null;
    return found;
end
$$;

create function auth_recovery_left() returns integer
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select count(*)::integer from public.recovery_codes r
     where r.user_id = public.app_current_user_id() and r.used_at is null
       and public.auth_is_super_admin()
$$;

-- The waiting session becomes a full one, under a new token (D-037).
create function auth_second_factor_passed(session uuid, new_hash bytea, lifetime integer)
returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if not public.auth_is_super_admin() then
        return false;
    end if;
    update public.user_sessions s
       set second_factor_pending = false,
           token_hash = auth_second_factor_passed.new_hash,
           expires_at = now() + make_interval(secs => auth_second_factor_passed.lifetime),
           last_seen_at = now()
     where s.id = auth_second_factor_passed.session
       and s.user_id = public.app_current_user_id()
       and s.second_factor_pending
       and s.revoked_at is null
       and s.expires_at > now();
    return found;
end
$$;
"""

NAMES = (
    "auth_is_super_admin()",
    "auth_totp_state()",
    "auth_totp_start(bytea)",
    "auth_totp_use_step(bigint)",
    "auth_recovery_replace(bytea[])",
    "auth_totp_confirm(bytea[])",
    "auth_recovery_use(bytea)",
    "auth_recovery_left()",
    "auth_second_factor_passed(uuid, bytea, integer)",
)

GRANTS = "\n".join(
    f"revoke all on function {name} from public;\ngrant execute on function {name} to app_user;"
    for name in NAMES
)

UNDO = (
    "\n".join(f"drop function {name};" for name in reversed(NAMES))
    + f"""
revoke insert (second_factor_pending) on user_sessions from app_user;
revoke select ({READABLE}) on users from app_user, app_platform;
grant select on users to app_user, app_platform;
alter table user_sessions drop column second_factor_pending;
drop table recovery_codes;
alter table users
    drop constraint ck_users_totp_confirmed_needs_secret,
    drop constraint ck_users_totp_only_super_admin,
    drop column totp_last_step,
    drop column totp_confirmed_at,
    drop column totp_secret;
"""
)


def upgrade() -> None:
    """Upgrade schema."""
    # Hand-written (D-023): columns, one table, grants and owner-run functions.
    op.execute(TABLES)
    op.execute(FUNCTIONS)
    op.execute(GRANTS)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(UNDO)
