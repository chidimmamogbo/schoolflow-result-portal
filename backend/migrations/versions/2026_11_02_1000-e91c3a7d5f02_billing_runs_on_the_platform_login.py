"""Migration 28: what billing needs from the platform login (D-051, D-091, D-092, D-096, D-178).

BUILD_PROMPT 9.2q to 9.2s; SPEC F19; AC19.5.

app_platform cannot read pupils or terms, nor post notices (D-051), yet billing
needs a few facts and one action. These functions run as the owner (search
path fixed, callable only by app_platform) and return numbers or names:

- platform_billing_term(school): the school's active term, its label and how
  many active pupils are enrolled for it (D-091).
- platform_term_label(term): "First Term 2026/2027".
- platform_billing_summary(): invoiced, paid and outstanding per term, void
  invoices left out.
- platform_post_billing_notice(school, title, body): a system notice to the
  school's active school admins; returns its id.

Two small changes to what migration 18 set:

- school_subscriptions.grace_period_days: a school's own grace period; empty
  means the platform setting (F19 rule 7).
- check_payment(): a super admin may also start a payment, the manual payment
  of F19 rule 12, and app_platform may insert the same columns a school admin
  may. Everything else about the rule is unchanged: the amount still comes
  from the invoice and the invoice must be unpaid.

Revision ID: e91c3a7d5f02
Revises: d2a8f61e4b57
Create Date: 2026-11-02 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e91c3a7d5f02"
down_revision: str | Sequence[str] | None = "d2a8f61e4b57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SIGNATURES = (
    "platform_billing_term(uuid)",
    "platform_term_label(uuid)",
    "platform_billing_summary()",
    "platform_post_billing_notice(uuid, text, text)",
)

LABEL = "(array['First Term', 'Second Term', 'Third Term'])[t.term_number] || ' ' || a.name"

FUNCTIONS = f"""
create function platform_billing_term(school uuid)
returns table (term_id uuid, label text, billable integer)
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select t.id,
           {LABEL},
           (select count(distinct e.student_id)::integer
              from public.enrolments e
              join public.students p on p.id = e.student_id
             where e.session_id = t.session_id
               and e.school_id = t.school_id
               and e.left_on is null
               and p.status = 'active')
      from public.terms t
      join public.academic_sessions a on a.id = t.session_id
     where t.school_id = platform_billing_term.school
       and t.is_active
$$;

create function platform_term_label(term uuid) returns text
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select {LABEL}
      from public.terms t
      join public.academic_sessions a on a.id = t.session_id
     where t.id = platform_term_label.term
$$;

create function platform_billing_summary()
returns table (label text, invoices integer, invoiced_kobo bigint, paid_kobo bigint,
               outstanding_kobo bigint)
language sql stable
security definer
set search_path = pg_catalog, public
as $$
    select {LABEL},
           count(*)::integer,
           sum(i.amount_kobo)::bigint,
           (coalesce(sum(i.amount_kobo) filter (where i.status = 'paid'), 0))::bigint,
           (coalesce(sum(i.amount_kobo) filter (where i.status = 'unpaid'), 0))::bigint
      from public.invoices i
      join public.terms t on t.id = i.term_id
      join public.academic_sessions a on a.id = t.session_id
     where i.status <> 'void'
     group by t.term_number, a.name
     order by a.name desc, t.term_number desc
$$;

create function platform_post_billing_notice(school uuid, title text, body text) returns uuid
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    posted uuid;
begin
    insert into public.notices (school_id, title, body, kind)
    values (platform_post_billing_notice.school, platform_post_billing_notice.title,
            platform_post_billing_notice.body, 'system')
    returning id into posted;
    insert into public.notice_audiences (school_id, notice_id, role)
    values (platform_post_billing_notice.school, posted, 'school_admin');
    insert into public.notice_recipients (school_id, notice_id, user_id)
    select m.school_id, posted, m.user_id
      from public.school_memberships m
      join public.users u on u.id = m.user_id
     where m.school_id = platform_post_billing_notice.school
       and m.role = 'school_admin'
       and m.status = 'active'
       and u.is_active;
    return posted;
end
$$;
"""  # noqa: S608 (fixed text; LABEL is a constant)

CHECK_PAYMENT = """
create or replace function check_payment() returns trigger
language plpgsql
as $$
declare
    invoice record;
begin
    if tg_op = 'DELETE' then
        raise exception 'Payment records are kept.'
            using errcode = 'check_violation',
                  constraint = 'payments_kept';
    end if;

    select i.status, i.amount_kobo
      into invoice
      from invoices i
     where i.id = new.invoice_id
       and i.school_id = new.school_id;

    if tg_op = 'INSERT' then
        if not exists (
            select 1
              from school_memberships m
             where m.user_id = app_current_user_id()
               and m.school_id = new.school_id
               and m.role = 'school_admin'
        )MANUAL_PAYMENT then
            raise exception 'Only a school admin of the school pays its invoices.'
                using errcode = 'check_violation',
                      constraint = 'payments_started_by_school_admin';
        end if;
        if invoice.status is distinct from 'unpaid' then
            raise exception 'Only an unpaid invoice takes a payment.'
                using errcode = 'check_violation',
                      constraint = 'payments_for_an_unpaid_invoice';
        end if;
        -- D-093: the amount comes from the invoice, never from the request.
        new.amount_kobo := invoice.amount_kobo;
        new.currency := 'NGN';
        new.status := 'pending';
        new.gateway_reference := null;
        new.verified_at := null;
        new.failure_reason := null;
        new.receipt_number := null;
        new.created_by := app_current_user_id();
        return new;
    end if;

    if row(new.school_id, new.invoice_id, new.reference, new.gateway, new.amount_kobo,
           new.currency, new.created_by, new.created_at, new.receipt_number)
       is distinct from
       row(old.school_id, old.invoice_id, old.reference, old.gateway, old.amount_kobo,
           old.currency, old.created_by, old.created_at, old.receipt_number)
    then
        raise exception 'Payment records are kept.'
            using errcode = 'check_violation',
                  constraint = 'payments_kept';
    end if;

    if old.status <> 'pending' then
        raise exception 'A % payment stays as it is.', old.status
            using errcode = 'check_violation',
                  constraint = 'payments_status_change_allowed';
    end if;

    if new.status = 'succeeded' then
        if invoice.status is distinct from 'unpaid' then
            raise exception 'The invoice is already paid or void.'
                using errcode = 'check_violation',
                      constraint = 'payments_invoice_still_unpaid';
        end if;
        -- D-095: a numbered receipt goes with every success.
        new.receipt_number := 'SF-RCPT-' || lpad(nextval('payment_receipt_numbers')::text, 6, '0');
    end if;
    return new;
end
$$;
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "school_subscriptions", sa.Column("grace_period_days", sa.Integer(), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_school_subscriptions_grace_period_valid"),
        "school_subscriptions",
        "grace_period_days IS NULL OR grace_period_days BETWEEN 0 AND 90",
    )
    # Hand-written (D-023).
    op.execute("grant update (grace_period_days) on school_subscriptions to app_platform")
    op.execute(FUNCTIONS)
    for signature in SIGNATURES:
        op.execute(f"revoke all on function {signature} from public")
        op.execute(f"grant execute on function {signature} to app_platform")
    op.execute(
        CHECK_PAYMENT.replace("MANUAL_PAYMENT", " and not app_current_user_is_super_admin()")
    )
    op.execute(
        "grant insert (school_id, invoice_id, reference, gateway) on payments to app_platform"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "revoke insert (school_id, invoice_id, reference, gateway) on payments from app_platform"
    )
    op.execute(CHECK_PAYMENT.replace("MANUAL_PAYMENT", ""))
    for signature in SIGNATURES:
        op.execute(f"drop function {signature}")
    op.drop_constraint(
        op.f("ck_school_subscriptions_grace_period_valid"), "school_subscriptions", type_="check"
    )
    op.drop_column("school_subscriptions", "grace_period_days")
