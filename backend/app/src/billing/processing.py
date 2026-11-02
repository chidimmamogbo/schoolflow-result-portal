"""What happens after Paystack calls us (SPEC F19 rule 11; AC19.6, AC19.7; D-094, D-178).

The webhook route only checks the signature, stores the event once and answers
200. This module does the rest, as app_platform, one event per transaction,
right after the response and again in the daily run:

1. Only charge.success matters; anything else is marked ignored.
2. The reference must be one of our payments, still pending.
3. Paystack's Verify Transaction must say success, the invoice's exact amount,
   NGN and the same reference. The webhook only tells us to look; this is the
   proof. A mismatch fails the payment and leaves the invoice Unpaid.
4. If Paystack cannot be reached, the event stays Received and is tried again.
5. Success: the database numbers the receipt and marks the invoice Paid; the
   school's admins get a notice and a receipt email; it is all audited.

The same success path serves the super admin's manual payment (F19 rule 12).
"""

import logging
import uuid
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.platform.email import trigger
from app.platform.email.queue import queue_email
from app.platform.payments.gateway import GatewayError, PaymentGateway, PaystackGateway
from app.src.audit.services import write_audit
from app.src.billing.pricing import subscription_status
from app.src.billing.utils import field_of, money
from app.src.platform_admin import settings_model

logger = logging.getLogger(__name__)

CHARGE_SUCCESS = "charge.success"

Kick = Callable[[], None]
Batches = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class ProcessReport:
    processed: int
    ignored: int
    failed: int
    waiting: int


# --- subscriptions --------------------------------------------------------------------------------


def today(db: Session) -> Any:
    return db.scalar(text("select (now() at time zone 'Africa/Lagos')::date"))


def grace_days(db: Session, own: int | None) -> int:
    return settings_model.load(db).billing.grace_period_days if own is None else own


def current_status(db: Session, school_id: uuid.UUID) -> tuple[str, int, bool] | None:
    """The status worked out now, the grace in force and whether billing is on."""
    row = db.execute(
        text(
            "select sub.billing_enabled, sub.grace_period_days, s.status as school_status,"
            " (select min(i.due_on) from invoices i"
            "   where i.school_id = s.id and i.status = 'unpaid') as oldest_due"
            " from school_subscriptions sub join schools s on s.id = sub.school_id"
            " where s.id = :s"
        ),
        {"s": school_id},
    ).first()
    if row is None:
        return None
    grace = grace_days(db, row.grace_period_days)
    # Suspension lives on the school (the platform's Suspend action sets it there too).
    stored = "suspended" if row.school_status == "suspended" else "active"
    status = subscription_status(row.billing_enabled, stored, row.oldest_due, grace, today(db))
    return status, grace, row.billing_enabled


def refresh_subscription(db: Session, school_id: uuid.UUID) -> None:
    now = current_status(db, school_id)
    if now is not None:
        db.execute(
            text(
                "update school_subscriptions set status = :status"
                " where school_id = :s and status <> :status"
            ),
            {"status": now[0], "s": school_id},
        )


# --- a payment that succeeded ---------------------------------------------------------------------


def finish_payment(
    db: Session, payment_id: uuid.UUID, gateway_reference: str, role: str, note: str | None = None
) -> str:
    """Paid: receipt, invoice, status, notice, email and audit, in one transaction."""
    payment = db.execute(
        text(
            "update payments set status = 'succeeded', verified_at = now(),"
            " gateway_reference = :g where id = :id"
            " returning school_id, invoice_id, amount_kobo, receipt_number, reference"
        ),
        {"g": gateway_reference, "id": payment_id},
    ).one()
    school_id: uuid.UUID = payment.school_id
    term_id = db.scalar(
        text("select term_id from invoices where id = :i"), {"i": payment.invoice_id}
    )
    term = db.scalar(text("select platform_term_label(:t)"), {"t": term_id})
    refresh_subscription(db, school_id)
    amount = money(payment.amount_kobo)
    db.scalar(
        text("select platform_post_billing_notice(:s, :t, :b)"),
        {
            "s": school_id,
            "t": f"{term} invoice paid",
            "b": f"Payment of {amount} received for {term}. Receipt {payment.receipt_number}.",
        },
    )
    queue_receipt_email(db, school_id, term, payment.amount_kobo, payment.receipt_number)
    write_audit(
        db,
        school_id,
        role,
        "invoices.paid",
        target=("invoices", payment.invoice_id),
        new={
            "payment_reference": payment.reference,
            "gateway_reference": gateway_reference,
            "amount_kobo": payment.amount_kobo,
            "receipt_number": payment.receipt_number,
        },
        reason=note,
    )
    return str(payment.receipt_number)


def queue_receipt_email(
    db: Session, school_id: uuid.UUID, term: str, amount_kobo: int, receipt_number: str
) -> None:
    emails_on = db.scalar(
        text(
            "select enabled from school_features"
            " where school_id = :s and feature = 'email_notifications'"
        ),
        {"s": school_id},
    )
    if not emails_on:
        return
    school_name = db.scalar(text("select name from schools where id = :s"), {"s": school_id})
    admins = db.execute(
        text(
            "select u.full_name, u.email from school_memberships m"
            " join users u on u.id = m.user_id"
            " where m.school_id = :s and m.role = 'school_admin' and m.status = 'active'"
            " and u.is_active and u.email is not null order by u.email"
        ),
        {"s": school_id},
    )
    for admin in admins:
        queue_email(
            db,
            school_id,
            "payment_receipt",
            admin.email,
            {
                "full_name": admin.full_name,
                "school_name": school_name,
                "term_name": term,
                "amount": money(amount_kobo),
                "receipt_number": receipt_number,
                "billing_path": "/school/billing",
            },
        )


# --- one webhook event ----------------------------------------------------------------------------


def settle_event(db: Session, event_id: uuid.UUID, status: str, error: str | None) -> None:
    db.execute(
        text(
            "update payment_events set status = :status, error = :error, processed_at ="
            " case when :status = 'received' then null else now() end where id = :id"
        ),
        {"status": status, "error": error, "id": event_id},
    )


def fail_payment(db: Session, payment: Any, reason: str) -> None:
    db.execute(
        text("update payments set status = 'failed', failure_reason = :r where id = :id"),
        {"r": reason, "id": payment.id},
    )
    write_audit(
        db,
        payment.school_id,
        "system",
        "payments.rejected",
        target=("payments", payment.id),
        reason=reason,
    )
    # The reference and the reason hold no secret, address or card detail.
    logger.warning(
        "payment rejected", extra={"fields": {"reference": payment.reference, "reason": reason}}
    )


def mismatch(verified: Any, payment: Any) -> str | None:
    """What Paystack's own answer gets wrong for this payment, if anything."""
    if verified.status != "success":
        return f"Paystack says {verified.status}"
    if verified.reference != payment.reference:
        return "Reference does not match"
    if verified.amount_kobo != payment.amount_kobo:
        return "Amount does not match the invoice"
    if verified.currency != "NGN":
        return "Currency is not NGN"
    return None


def process_event(db: Session, event_id: uuid.UUID, gateway: PaymentGateway) -> str:
    """One event; returns its new status."""
    event = db.execute(
        text(
            "select id, event_type, payload from payment_events"
            " where id = :id and status = 'received' for update skip locked"
        ),
        {"id": event_id},
    ).first()
    if event is None:
        return "ignored"
    if event.event_type != CHARGE_SUCCESS:
        settle_event(db, event.id, "ignored", None)
        return "ignored"
    reference = field_of(field_of(event.payload, "data"), "reference")
    payment = db.execute(
        text(
            "select p.id, p.school_id, p.reference, p.amount_kobo, p.status,"
            " i.status as invoice_status from payments p"
            " join invoices i on i.id = p.invoice_id"
            " where p.reference = :r for update of p"
        ),
        {"r": str(reference)},
    ).first()
    if payment is None:
        settle_event(db, event.id, "failed", "Unknown reference")
        logger.warning(
            "webhook for an unknown reference", extra={"fields": {"event": str(event.id)}}
        )
        return "failed"
    if payment.status != "pending":
        settle_event(db, event.id, "ignored", f"Payment already {payment.status}")
        return "ignored"
    try:
        verified = gateway.verify(payment.reference)
    except GatewayError as error:
        if error.temporary:
            settle_event(db, event.id, "received", str(error))
            return "received"
        fail_payment(db, payment, str(error))
        settle_event(db, event.id, "failed", str(error))
        return "failed"
    wrong = mismatch(verified, payment)
    if wrong is None and payment.invoice_status != "unpaid":
        # Money arrived for a closed invoice: someone must look at it and refund it.
        wrong = f"Invoice is already {payment.invoice_status}; refund by hand"
    if wrong is not None:
        fail_payment(db, payment, wrong)
        settle_event(db, event.id, "failed", wrong)
        return "failed"
    finish_payment(db, payment.id, verified.gateway_id, "system")
    settle_event(db, event.id, "processed", None)
    return "processed"


def process_pending(batches: Batches, gateway: PaymentGateway) -> ProcessReport:
    """Every Received event, each in its own transaction, so one bad event stops no other."""
    with batches() as db:
        waiting = list(
            db.scalars(
                text("select id from payment_events where status = 'received' order by received_at")
            )
        )
    counts = {"processed": 0, "ignored": 0, "failed": 0, "received": 0}
    for event_id in waiting:
        try:
            with batches() as db:
                counts[process_event(db, event_id, gateway)] += 1
        except Exception as error:  # logged; it stays Received for the next run
            counts["received"] += 1
            logger.warning(
                "webhook event not processed", extra={"fields": {"error": type(error).__name__}}
            )
    return ProcessReport(
        processed=counts["processed"],
        ignored=counts["ignored"],
        failed=counts["failed"],
        waiting=counts["received"],
    )


def refresh_all_subscriptions(batches: Batches) -> int:
    """The daily refresh of D-092: Due becomes Overdue when the grace runs out."""
    with batches() as db:
        schools = list(db.scalars(text("select school_id from school_subscriptions")))
        before = {
            r.school_id: r.status
            for r in db.execute(text("select school_id, status from school_subscriptions"))
        }
        for school_id in schools:
            refresh_subscription(db, school_id)
        after = {
            r.school_id: r.status
            for r in db.execute(text("select school_id, status from school_subscriptions"))
        }
    return sum(1 for school_id in schools if before[school_id] != after[school_id])


# --- running it for real --------------------------------------------------------------------------


@contextmanager
def committed(engine: Engine) -> Generator[Session]:
    with Session(engine) as session:
        yield session
        session.commit()


def real_batches() -> Batches | None:
    """The platform login's transactions; None until DATABASE_URL_PLATFORM is set."""
    from app.src.platform_admin.dependencies import get_platform_engine

    if get_settings().database_url_platform is None:
        return None
    engine = get_platform_engine()

    def batch() -> AbstractContextManager[Session]:
        return committed(engine)

    return batch


def real_gateway() -> PaymentGateway | None:
    key = get_settings().paystack_secret_key
    if key is None or not key.get_secret_value():
        return None
    return PaystackGateway(key.get_secret_value())


def process_soon() -> None:
    """The background run after a webhook. It must never break the app."""
    try:
        batches, gateway = real_batches(), real_gateway()
        if batches is None or gateway is None:
            return
        if process_pending(batches, gateway).processed:
            trigger.send_soon()  # the receipt emails it queued
    except Exception as error:  # logged; the daily run tries again
        logger.warning("payment run failed", extra={"fields": {"error": type(error).__name__}})


def get_payment_kick() -> Kick:
    """What the webhook starts after a new event (tests replace it)."""
    return process_soon
