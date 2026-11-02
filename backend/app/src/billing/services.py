"""School subscription billing (BUILD_PROMPT 9.2q to 9.2s; SPEC F19; D-087 to D-097, D-178).

The super admin saves price lists (each save a new version), issues one invoice
per school per term as a snapshot that never changes (AC19.5), voids invoices
and records manual payments. A school admin sees their own school's billing,
starts a payment and gets a receipt. The amount always comes from the invoice,
and the return from Paystack never marks anything paid (AT-37.1): only a signed
webhook plus Paystack's own answer does (processing.py). With billing off a
school sees no invoices and no way to pay (AC19.9).
"""

import hashlib
import hmac
import json
import logging
import uuid
from typing import Any

from fastapi import Response
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import Principal, found
from app.core.errors import ProblemError
from app.platform import pdf
from app.platform.payments.gateway import GatewayError, PaymentGateway
from app.src.audit.services import write_audit
from app.src.billing import processing
from app.src.billing.pricing import DEFAULT_PLANS, Plan, bill_for, plan_problems, price_check
from app.src.billing.render import receipt_html
from app.src.billing.schemas import (
    BillingSchoolRow,
    Checkout,
    Generate,
    Generated,
    InvoiceRow,
    ManualPayment,
    NewPricing,
    PaymentStatus,
    PlanForm,
    PricingPage,
    PricingVersionRow,
    Receipt,
    SchoolBilling,
    Skipped,
    StudentRange,
    SubscriptionChange,
    SubscriptionRow,
    TermSummary,
    VoidInvoice,
)
from app.src.billing.utils import field_of
from app.src.platform_admin import settings_model

logger = logging.getLogger(__name__)

PRIVATE = {"Cache-Control": "private, no-store"}
TERM_NAMES = "(array['First Term', 'Second Term', 'Third Term'])"
# Each side reads the term's label its own way: app_platform may not read terms (D-051).
SCHOOL_TERM = (
    f"(select {TERM_NAMES}[t.term_number] || ' ' || a.name from terms t"  # noqa: S608
    " join academic_sessions a on a.id = t.session_id where t.id = i.term_id)"
)
PLATFORM_TERM = "platform_term_label(i.term_id)"
INVOICE_SELECT = (
    "select i.id, i.school_id, i.term_id, {term} as term, i.kind, i.billable_students,"
    " i.pricing_version_id, i.tier_name, i.rate_kobo, i.amount_kobo, i.cliff_cap_applied,"
    " i.due_on, i.status, i.paid_at, i.void_reason, i.created_at,"
    " p.gateway_reference, p.receipt_number"
    " from invoices i left join payments p on p.invoice_id = i.id and p.status = 'succeeded'"
)


def invoice_row(r: Any) -> InvoiceRow:
    return InvoiceRow(
        id=str(r.id),
        school_id=str(r.school_id),
        term=r.term,
        kind=r.kind,
        billable_students=r.billable_students,
        plan=r.tier_name,
        rate_kobo=r.rate_kobo,
        amount_kobo=r.amount_kobo,
        cliff_cap_applied=r.cliff_cap_applied,
        due_on=r.due_on,
        status=r.status,
        paid_at=r.paid_at,
        void_reason=r.void_reason,
        reference=r.gateway_reference,
        receipt_number=r.receipt_number,
        created_at=r.created_at,
    )


# --- price lists ----------------------------------------------------------------------------------


def plan_of(row: Any) -> Plan:
    return Plan(row.name, row.min_students, row.max_students, row.price_kobo)


def plans_of(db: Session, version_id: uuid.UUID) -> tuple[Plan, ...]:
    rows = db.execute(
        text(
            "select name, min_students, max_students, price_kobo from pricing_tiers"
            " where version_id = :v order by position"
        ),
        {"v": version_id},
    )
    return tuple(plan_of(r) for r in rows)


def latest_version(db: Session) -> Any:
    return db.execute(
        text("select id, version from pricing_versions order by version desc limit 1")
    ).first()


def forms(plans: tuple[Plan, ...]) -> list[PlanForm]:
    return [
        PlanForm(
            name=p.name,
            min_students=p.min_students,
            max_students=p.max_students,
            price_kobo=p.price_kobo,
        )
        for p in plans
    ]


def pricing_page(db: Session, version: int | None, plans: tuple[Plan, ...]) -> PricingPage:
    return PricingPage(
        version=version,
        plans=forms(plans),
        price_check=[StudentRange(from_students=a, to_students=b) for a, b in price_check(plans)],
        cliff_protection=settings_model.load(db).billing.cliff_protection,
    )


def get_pricing(db: Session) -> PricingPage:
    latest = latest_version(db)
    if latest is None:
        return pricing_page(db, None, DEFAULT_PLANS)
    return pricing_page(db, latest.version, plans_of(db, latest.id))


def store_version(db: Session, plans: tuple[Plan, ...]) -> Any:
    version_id = db.scalar(text("insert into pricing_versions default values returning id"))
    for position, plan in enumerate(plans, start=1):
        db.execute(
            text(
                "insert into pricing_tiers (version_id, position, name, min_students,"
                " max_students, price_kobo) values (:v, :p, :n, :low, :high, :price)"
            ),
            {
                "v": version_id,
                "p": position,
                "n": plan.name.strip(),
                "low": plan.min_students,
                "high": plan.max_students,
                "price": plan.price_kobo,
            },
        )
    return db.execute(
        text("select id, version from pricing_versions where id = :v"), {"v": version_id}
    ).one()


def save_pricing(body: NewPricing, db: Session) -> PricingPage:
    plans = tuple(Plan(p.name, p.min_students, p.max_students, p.price_kobo) for p in body.plans)
    problems = plan_problems(plans)
    if problems:
        raise ProblemError(
            422,
            "These plans can't be saved.",
            code="plans_invalid",
            errors=[{"field": "plans", "message": problem} for problem in problems],
        )
    saved = store_version(db, plans)
    write_audit(
        db,
        None,
        "super_admin",
        "pricing.save",
        target=("pricing_versions", saved.id),
        new={"version": saved.version, "plans": [p.model_dump() for p in body.plans]},
    )
    return pricing_page(db, saved.version, plans)


def pricing_versions(db: Session) -> list[PricingVersionRow]:
    rows = db.execute(
        text("select id, version, created_at from pricing_versions order by version desc")
    ).all()
    return [
        PricingVersionRow(
            version=r.version, created_at=r.created_at, plans=forms(plans_of(db, r.id))
        )
        for r in rows
    ]


def version_for_billing(db: Session) -> Any:
    """The current version; the first invoice saves the defaults as version 1."""
    return latest_version(db) or store_version(db, DEFAULT_PLANS)


# --- invoices -------------------------------------------------------------------------------------


def platform_invoice(db: Session, invoice_id: Any) -> Any:
    query = INVOICE_SELECT.format(term=PLATFORM_TERM) + " where i.id = :id"
    return db.execute(text(query), {"id": invoice_id}).first()


def issue(
    db: Session,
    school_id: uuid.UUID,
    term_id: uuid.UUID,
    kind: str,
    students: int,
    version_id: uuid.UUID,
    plan: str,
    rate: int,
    amount: int,
    capped: bool,
) -> InvoiceRow:
    due_days = settings_model.load(db).billing.invoice_due_days
    invoice_id = db.scalar(
        text(
            "insert into invoices (school_id, term_id, kind, billable_students,"
            " pricing_version_id, tier_name, rate_kobo, amount_kobo, cliff_cap_applied, due_on)"
            " values (:s, :t, :k, :n, :v, :plan, :rate, :amount, :capped,"
            " (now() at time zone 'Africa/Lagos')::date + cast(:due as integer)) returning id"
        ),
        {
            "s": school_id,
            "t": term_id,
            "k": kind,
            "n": students,
            "v": version_id,
            "plan": plan,
            "rate": rate,
            "amount": amount,
            "capped": capped,
            "due": due_days,
        },
    )
    processing.refresh_subscription(db, school_id)
    write_audit(
        db,
        school_id,
        "super_admin",
        "invoices.generate",
        target=("invoices", invoice_id),
        new={
            "kind": kind,
            "billable_students": students,
            "plan": plan,
            "rate_kobo": rate,
            "amount_kobo": amount,
            "cliff_cap_applied": capped,
        },
    )
    return invoice_row(platform_invoice(db, invoice_id))


def adjustment_invoice(db: Session, school: Any, students: int) -> InvoiceRow | str:
    term = db.execute(text("select * from platform_billing_term(:s)"), {"s": school.id}).first()
    if term is None:
        return "No active term"
    base = db.execute(
        text(
            "select pricing_version_id, tier_name, rate_kobo from invoices"
            " where school_id = :s and term_id = :t and kind = 'term' and status <> 'void'"
        ),
        {"s": school.id, "t": term.term_id},
    ).first()
    if base is None:
        return "No term invoice to adjust"
    # The term's own version and rate: later price changes do not reach it (AC19.5).
    return issue(
        db, school.id, term.term_id, "adjustment", students, base.pricing_version_id,
        base.tier_name, base.rate_kobo, students * base.rate_kobo, False,
    )  # fmt: skip


def term_invoice(db: Session, school: Any) -> InvoiceRow | str:
    if school.status == "suspended":
        return "School is suspended"
    term = db.execute(text("select * from platform_billing_term(:s)"), {"s": school.id}).first()
    if term is None:
        return "No active term"
    if term.billable < 1:
        return "No billable students"
    if db.scalar(
        text(
            "select exists (select 1 from invoices where school_id = :s and term_id = :t"
            " and kind = 'term' and status <> 'void')"
        ),
        {"s": school.id, "t": term.term_id},
    ):
        return "Already invoiced for this term"
    version = version_for_billing(db)
    cliff = settings_model.load(db).billing.cliff_protection
    bill = bill_for(term.billable, plans_of(db, version.id), cliff_protection=cliff)
    return issue(
        db, school.id, term.term_id, "term", term.billable, version.id, bill.plan.name,
        bill.rate_kobo, bill.amount_kobo, bill.capped,
    )  # fmt: skip


BILLABLE = (
    "select s.id, s.name, s.status, sub.billing_enabled from schools s"
    " left join school_subscriptions sub on sub.school_id = s.id"
)


def generate_invoices(body: Generate, db: Session) -> Generated:
    if body.adjustment_students is not None and body.school_id is None:
        raise ProblemError(422, "Choose the school to adjust.", code="school_required")
    if body.school_id is None:
        schools = db.execute(text(BILLABLE + " where sub.billing_enabled order by s.name")).all()
    else:
        try:
            wanted = uuid.UUID(body.school_id)
        except ValueError:
            found(None)
            raise
        schools = [found(db.execute(text(BILLABLE + " where s.id = :s"), {"s": wanted}).first())]
    created: list[InvoiceRow] = []
    skipped: list[Skipped] = []
    for school in schools:
        if not school.billing_enabled:
            outcome: InvoiceRow | str = "Billing is off"
        elif body.adjustment_students is not None:
            outcome = adjustment_invoice(db, school, body.adjustment_students)
        else:
            outcome = term_invoice(db, school)
        if isinstance(outcome, str):
            skipped.append(Skipped(school_id=str(school.id), name=school.name, reason=outcome))
        else:
            created.append(outcome)
    return Generated(created=created, skipped=skipped)


def list_invoices(db: Session, school_id: uuid.UUID | None) -> list[InvoiceRow]:
    query = (
        INVOICE_SELECT.format(term=PLATFORM_TERM)
        + " where (cast(:s as uuid) is null or i.school_id = :s)"
        " order by i.created_at desc, i.id"
    )
    return [invoice_row(r) for r in db.execute(text(query), {"s": school_id})]


def get_invoice(invoice_id: uuid.UUID, db: Session) -> InvoiceRow:
    return invoice_row(found(platform_invoice(db, invoice_id)))


def void_invoice(invoice_id: uuid.UUID, body: VoidInvoice, db: Session) -> InvoiceRow:
    row = found(platform_invoice(db, invoice_id))
    if row.status != "unpaid":
        raise ProblemError(409, "Only an unpaid invoice can be voided.", code="invoice_not_unpaid")
    db.execute(
        text("update invoices set status = 'void', void_reason = :r where id = :id"),
        {"r": body.reason, "id": invoice_id},
    )
    processing.refresh_subscription(db, row.school_id)
    write_audit(
        db,
        row.school_id,
        "super_admin",
        "invoices.void",
        target=("invoices", invoice_id),
        reason=body.reason,
    )
    return invoice_row(platform_invoice(db, invoice_id))


def record_manual_payment(invoice_id: uuid.UUID, body: ManualPayment, db: Session) -> InvoiceRow:
    row = found(platform_invoice(db, invoice_id))
    if row.status != "unpaid":
        raise ProblemError(
            409, "Only an unpaid invoice can take a payment.", code="invoice_not_unpaid"
        )
    payment_id = db.scalar(
        text(
            "insert into payments (school_id, invoice_id, reference, gateway)"
            " values (:s, :i, :r, 'paystack') returning id"
        ),
        {"s": row.school_id, "i": invoice_id, "r": f"MANUAL-{uuid.uuid4().hex[:24]}"},
    )
    processing.finish_payment(db, payment_id, body.reference, "super_admin", note=body.note)
    return invoice_row(platform_invoice(db, invoice_id))


def resend_receipt(payment_id: uuid.UUID, db: Session) -> None:
    payment = found(
        db.execute(
            text(
                "select p.school_id, p.amount_kobo, p.receipt_number, i.term_id from payments p"
                " join invoices i on i.id = p.invoice_id"
                " where p.id = :id and p.status = 'succeeded'"
            ),
            {"id": payment_id},
        ).first()
    )
    term = db.scalar(text("select platform_term_label(:t)"), {"t": payment.term_id})
    processing.queue_receipt_email(
        db, payment.school_id, term, payment.amount_kobo, payment.receipt_number
    )
    write_audit(
        db,
        payment.school_id,
        "super_admin",
        "payments.resend_receipt",
        target=("payments", payment_id),
    )


# --- the super admin's overview -------------------------------------------------------------------


def billing_schools(db: Session) -> list[BillingSchoolRow]:
    rows = db.execute(
        text(
            "select s.id, s.name, s.code, sub.billing_enabled from schools s"
            " join school_subscriptions sub on sub.school_id = s.id order by s.name"
        )
    ).all()
    result: list[BillingSchoolRow] = []
    for r in rows:
        now = found(processing.current_status(db, r.id))
        usage = db.execute(
            text("select students from platform_school_usage(:s)"), {"s": r.id}
        ).one()
        query = (
            INVOICE_SELECT.format(term=PLATFORM_TERM)
            + " where i.school_id = :s and i.status <> 'void'"
            " order by i.created_at desc, i.id limit 1"
        )
        current = db.execute(text(query), {"s": r.id}).first()
        result.append(
            BillingSchoolRow(
                id=str(r.id),
                name=r.name,
                code=r.code,
                billing_enabled=r.billing_enabled,
                status=now[0],
                grace_period_days=now[1],
                students=usage.students,
                current_invoice=invoice_row(current) if current else None,
            )
        )
    return result


def billing_summary(db: Session) -> list[TermSummary]:
    return [
        TermSummary(
            term=r.label,
            invoices=r.invoices,
            invoiced_kobo=r.invoiced_kobo,
            paid_kobo=r.paid_kobo,
            outstanding_kobo=r.outstanding_kobo,
        )
        for r in db.execute(text("select * from platform_billing_summary()"))
    ]


def change_subscription(
    school_id: uuid.UUID, body: SubscriptionChange, db: Session
) -> SubscriptionRow:
    found(
        db.scalar(
            text("select school_id from school_subscriptions where school_id = :s"),
            {"s": school_id},
        )
    )
    if body.suspended and not body.reason:
        raise ProblemError(422, "Suspending a school needs a reason.", code="reason_required")
    if body.billing_enabled is not None:
        db.execute(
            text("update school_subscriptions set billing_enabled = :on where school_id = :s"),
            {"on": body.billing_enabled, "s": school_id},
        )
    if body.use_platform_grace or body.grace_period_days is not None:
        db.execute(
            text("update school_subscriptions set grace_period_days = :g where school_id = :s"),
            {"g": None if body.use_platform_grace else body.grace_period_days, "s": school_id},
        )
    if body.suspended is not None:
        db.execute(
            text("update schools set status = :status where id = :s"),
            {"status": "suspended" if body.suspended else "active", "s": school_id},
        )
    processing.refresh_subscription(db, school_id)
    now = found(processing.current_status(db, school_id))
    write_audit(
        db,
        school_id,
        "super_admin",
        "subscriptions.change",
        target=("schools", school_id),
        new={
            **body.model_dump(exclude_none=True, exclude={"reason"}),
            "status": now[0],
        },
        reason=body.reason,
    )
    return SubscriptionRow(
        school_id=str(school_id), billing_enabled=now[2], status=now[0], grace_period_days=now[1]
    )


# --- the school's side ----------------------------------------------------------------------------


def school_invoice_select() -> str:
    return INVOICE_SELECT.format(term=SCHOOL_TERM)


def billing_on(session: Session) -> bool:
    """AC19.9: with billing off, invoices and payment prompts are not there at all."""
    return bool(session.scalar(text("select billing_enabled from school_subscriptions")))


def billing_card(who: Principal, session: Session) -> SchoolBilling:
    school_id = found(who.school_id)
    now = processing.current_status(session, school_id)
    if now is None or not now[2]:
        return SchoolBilling(billing_enabled=False, status=now[0] if now else "free_pilot")
    current = session.execute(
        text(
            school_invoice_select()
            + " where i.status <> 'void' order by (i.status = 'unpaid') desc,"
            " i.created_at desc, i.id limit 1"
        )
    ).first()
    due = session.execute(
        text("select coalesce(sum(amount_kobo), 0) as total, min(due_on) as due_on"
             " from invoices where status = 'unpaid'")
    ).one()  # fmt: skip
    billable = int(
        session.scalar(
            text(
                "select count(distinct e.student_id) from enrolments e"
                " join students p on p.id = e.student_id"
                " join terms t on t.session_id = e.session_id"
                " where t.is_active and e.left_on is null and p.status = 'active'"
            )
        )
        or 0
    )
    renewal = session.scalar(text("select next_term_begins from terms where is_active"))
    latest = latest_version(session)
    plans = plans_of(session, latest.id) if latest else DEFAULT_PLANS
    cliff = settings_model.load(session).billing.cliff_protection
    bill = bill_for(billable, plans, cliff_protection=cliff) if billable else None
    return SchoolBilling(
        billing_enabled=True,
        status=now[0],
        plan=current.tier_name if current else (bill.plan.name if bill else None),
        billable_students=current.billable_students if current else billable,
        price_per_student_kobo=current.rate_kobo if current else (bill.rate_kobo if bill else None),
        amount_due_kobo=due.total,
        due_on=due.due_on,
        next_renewal_on=renewal,
        projected_next_term_kobo=bill.amount_kobo if bill else None,
        current_invoice=invoice_row(current) if current else None,
    )


def school_invoices(who: Principal, session: Session) -> list[InvoiceRow]:
    found(who.school_id)
    if not billing_on(session):
        return []
    query = school_invoice_select() + " order by i.created_at desc, i.id"
    return [invoice_row(r) for r in session.execute(text(query))]


def school_invoice(invoice_id: uuid.UUID, who: Principal, session: Session) -> Any:
    found(who.school_id)
    if not billing_on(session):
        found(None)
    query = school_invoice_select() + " where i.id = :id"
    return found(session.execute(text(query), {"id": invoice_id}).first())


def start_payment(
    invoice_id: uuid.UUID,
    who: Principal,
    session: Session,
    gateway: PaymentGateway,
    base_url: str,
) -> Checkout:
    invoice = school_invoice(invoice_id, who, session)
    if invoice.status != "unpaid":
        raise ProblemError(
            409, "This invoice is not waiting for payment.", code="invoice_not_unpaid"
        )
    reference = f"SF-{uuid.uuid4().hex[:24]}"
    # The database copies the amount from the invoice (D-093).
    payment = session.execute(
        text(
            "insert into payments (school_id, invoice_id, reference, gateway)"
            " values (:s, :i, :r, 'paystack') returning id, amount_kobo"
        ),
        {"s": who.school_id, "i": invoice_id, "r": reference},
    ).one()
    email = session.scalar(
        text(
            "select coalesce(u.email, s.email) from users u, schools s"
            " where u.id = :u and s.id = :s"
        ),
        {"u": who.user_id, "s": who.school_id},
    )
    try:
        url = gateway.initialize(
            email=email,
            amount_kobo=payment.amount_kobo,
            reference=reference,
            callback_url=f"{base_url.rstrip('/')}/school/billing/callback",
        )
    except GatewayError as error:
        # The route's transaction rolls back, so no payment is left behind.
        raise ProblemError(
            503,
            "We couldn't reach the payment service.",
            "Please try again in a few minutes.",
            code="payment_unavailable",
        ) from error
    write_audit(
        session,
        who.school_id,
        who.role.value,
        "invoices.pay_started",
        target=("payments", payment.id),
        new={"reference": reference, "amount_kobo": payment.amount_kobo},
    )
    return Checkout(checkout_url=url, reference=reference)


def payment_status(reference: str, who: Principal, session: Session) -> PaymentStatus:
    """What the callback page polls. It only reads: the return never marks an invoice paid."""
    found(who.school_id)
    if not billing_on(session):
        found(None)
    row = found(
        session.execute(
            text(
                "select p.reference, p.status, p.invoice_id, p.receipt_number,"
                " i.status as invoice_status from payments p"
                " join invoices i on i.id = p.invoice_id where p.reference = :r"
            ),
            {"r": reference},
        ).first()
    )
    return PaymentStatus(
        reference=row.reference,
        status=row.status,
        invoice_id=str(row.invoice_id),
        invoice_status=row.invoice_status,
        receipt_number=row.receipt_number,
    )


def receipt_of(invoice_id: uuid.UUID, who: Principal, session: Session) -> Receipt:
    invoice = school_invoice(invoice_id, who, session)
    number = found(invoice.receipt_number)
    school_name = session.scalar(
        text("select name from schools where id = :s"), {"s": who.school_id}
    )
    return Receipt(
        receipt_number=number,
        school_name=school_name,
        term=invoice.term,
        plan=invoice.tier_name,
        billable_students=invoice.billable_students,
        amount_kobo=invoice.amount_kobo,
        reference=invoice.gateway_reference,
        paid_at=invoice.paid_at,
    )


def receipt_pdf(invoice_id: uuid.UUID, who: Principal, session: Session) -> Response:
    """Made again from the payment record on each download (D-058, D-095)."""
    receipt = receipt_of(invoice_id, who, session)
    body = pdf.pdf_of(receipt_html(receipt), receipt.receipt_number, 1)
    return Response(
        body,
        media_type="application/pdf",
        headers={
            **PRIVATE,
            "Content-Disposition": f'attachment; filename="{receipt.receipt_number}.pdf"',
        },
    )


# --- the webhook ----------------------------------------------------------------------------------


def signature_matches(body: bytes, signature: str | None, secret: SecretStr | None) -> bool:
    """HMAC SHA512 of the raw body with the secret key, compared in constant time."""
    if signature is None or secret is None or not secret.get_secret_value():
        return False
    expected = hmac.new(secret.get_secret_value().encode(), body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected.encode(), signature.encode())


def store_event(db: Session, body: bytes) -> bool:
    """Keep a signed event once (AC19.7); True when it is new."""
    try:
        event: Any = json.loads(body)
    except ValueError:
        event = None
    if field_of(event, "event") is None:
        logger.warning("signed webhook with an unreadable body")
        return False
    gateway_id = field_of(field_of(event, "data"), "id")
    event_type = str(field_of(event, "event") or "unknown")
    # Paystack's events carry no id of their own: the type and transaction make one.
    identity = (
        f"{event_type}:{gateway_id}" if gateway_id is not None else hashlib.sha256(body).hexdigest()
    )
    stored = db.scalar(
        text(
            "insert into payment_events (provider, event_id, event_type, payload)"
            " values ('paystack', :id, :type, cast(:payload as jsonb))"
            " on conflict (provider, event_id) do nothing returning id"
        ),
        {"id": identity, "type": event_type, "payload": json.dumps(event)},
    )
    return stored is not None
