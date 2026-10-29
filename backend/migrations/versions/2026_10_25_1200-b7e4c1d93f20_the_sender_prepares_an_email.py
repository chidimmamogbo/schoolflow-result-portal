"""Migration 26: the email sender prepares each email at send time (D-081, D-153, D-176).

BUILD_PROMPT 9.2 (email sender); SPEC F18; D-078 to D-083.

The background sender logs in as app_sender, which reads the outbox and
updates only its sending columns. To write an email it also needs a few facts
it may not read itself, and for some emails a fresh secret link must be
stored (only its hash, made by the sender a moment before sending, D-081).
One owner-run function does exactly that and nothing else:

- email_prepare(email, link_hash): for a Queued email, returns the school's
  name and email (the sender name and Reply-To, D-079; empty for platform
  emails), what the address belongs to for a link request, and the new
  link's expiry. For an activation or reset email it cancels the account's
  live link of that kind and stores the new hash (72 hours, or 1 hour for a
  reset, D-039, D-041). For a link request to an address that has no account,
  it stores the hash on the request. An email that is no longer Queued gives
  nothing. Callable only by app_sender.

No table changes.

Revision ID: b7e4c1d93f20
Revises: a4d9e2c71b05
Create Date: 2026-10-25 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e4c1d93f20"
down_revision: str | Sequence[str] | None = "a4d9e2c71b05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTION = """
create function email_prepare(email uuid, link_hash bytea)
returns table (
    school_name text,
    reply_to text,
    address_kind text,
    link_expires_at timestamptz
)
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    outgoing public.email_outbox%rowtype;
    account uuid;
    link_purpose text;
    expires timestamptz;
    kind text;
begin
    select * into outgoing from public.email_outbox o where o.id = email and o.status = 'queued';
    if not found then
        return;
    end if;

    if outgoing.template in ('activation', 'password_reset') then
        account := (outgoing.template_data ->> 'user_id')::uuid;
        link_purpose := case outgoing.template when 'activation' then 'activation' else 'reset' end;
        expires := now() + case link_purpose when 'activation' then interval '72 hours'
                                             else interval '1 hour' end;
        update public.account_tokens t
           set cancelled_at = now()
         where t.user_id = account
           and t.purpose = link_purpose
           and t.used_at is null
           and t.cancelled_at is null;
        insert into public.account_tokens (user_id, purpose, token_hash, expires_at)
        values (account, link_purpose, link_hash, expires);
    elsif outgoing.template = 'parent_link_request' then
        select case
                 when u.id is null then 'nobody'
                 when u.student_school_id is not null
                      or exists (select 1 from public.school_memberships m
                                  where m.user_id = u.id and m.role <> 'parent')
                   then 'staff_or_pupil'
                 else 'parent'
               end
          into kind
          from (select 1) one
          left join public.users u on u.email = outgoing.to_address;
        if kind = 'nobody' then
            update public.parent_link_requests r
               set token_hash = link_hash
             where r.id = (outgoing.template_data ->> 'link_request_id')::uuid
               and r.accepted_at is null and r.declined_at is null and r.cancelled_at is null
               and r.expires_at > now()
            returning r.expires_at into expires;
        end if;
    end if;

    return query
    select s.name, s.email, kind, expires
      from (select 1) one
      left join public.schools s on s.id = outgoing.school_id;
end
$$;

revoke all on function email_prepare(uuid, bytea) from public;
grant execute on function email_prepare(uuid, bytea) to app_sender;
"""


def upgrade() -> None:
    """Upgrade schema."""
    # Hand-written (D-023): one function, no tables.
    op.execute(FUNCTION)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("drop function email_prepare(uuid, bytea)")
