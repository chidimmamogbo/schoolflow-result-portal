"""Billing: pricing, subscriptions, invoices, payments and webhook events (BUILD_PROMPT 9.1
item 10; SPEC F19; AC19.1, AC19.3, AC19.5, AC19.7, AC19.8; D-087 to D-097, D-155).

Behaviour: only the super admin saves pricing; each save is a new version whose
tiers start at 1 and follow on with no gaps or overlaps, only the last
open-ended, and versions never change. One term invoice per school per term,
issued by the super admin, with consistent arithmetic in kobo (the cliff cap
only ever lowers the amount); an invoice only moves Unpaid to Paid (with a
succeeded payment of exactly its amount) or Void (with a reason), and its
snapshot never changes. A school admin starts a payment for an unpaid
invoice of their school and the database takes the amount from the invoice;
success needs proof, issues a numbered receipt and marks the invoice paid,
once. Webhook events are stored once per gateway event. Schools see only
their own billing; payment events are the platform's alone. All data is
fictional.
"""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from schoolflow_api.db import use_context
from tests.db_support import acting_as, refused, run_commit_checks, violates
from tests.factories import (
    add_membership,
    create_pricing_version,
    create_school,
    create_session,
    create_term,
    create_user,
    issue_invoice,
    record_payment_event,
    set_subscription,
    start_payment,
)

SCHOOL_TABLES = ("school_subscriptions", "invoices", "payments")
COUNT: dict[str, TextClause] = {
    table: text(f"select count(*) from {table}")  # noqa: S608
    for table in (*SCHOOL_TABLES, "payment_events", "pricing_versions", "pricing_tiers")
}
SUCCEED = text(
    "update payments set status = 'succeeded', verified_at = now(),"
    " gateway_reference = :gateway_reference where id = :id"
)


@dataclass(frozen=True)
class Billing:
    gmc: uuid.UUID
    bsa: uuid.UUID
    first_term: uuid.UUID
    second_term: uuid.UUID
    admin: uuid.UUID  # the super admin
    ngozi: uuid.UUID  # GMC principal
    tunde: uuid.UUID  # GMC teacher
    version: uuid.UUID  # pricing version 1, the defaults


@pytest.fixture
def billing(db_session: Session) -> Billing:
    s = db_session
    gmc = create_school(s, code="GMC", name="Greenfield Model College")
    bsa = create_school(s, code="BSA", name="Bright Stars Academy", school_type="nursery_primary")
    gmc_session = create_session(s, gmc)
    admin = create_user(
        s, username="platform.admin", full_name="Platform Admin", is_super_admin=True
    )
    ngozi = create_user(s, username="ngozi.okeke", full_name="Ngozi Okeke")
    add_membership(s, ngozi, gmc, "school_admin", is_primary=True)
    tunde = create_user(s, username="tunde.adebayo", full_name="Tunde Adebayo")
    add_membership(s, tunde, gmc, "teacher")
    use_context(s, user_id=admin)
    version = create_pricing_version(s)
    run_commit_checks(s)
    for school, enabled in ((gmc, True), (bsa, False)):
        set_subscription(
            s, school, billing_enabled=enabled, status="active" if enabled else "free_pilot"
        )
    return Billing(
        gmc,
        bsa,
        create_term(s, gmc, gmc_session, 1, is_active=True),
        create_term(s, gmc, gmc_session, 2),
        admin,
        ngozi,
        tunde,
        version,
    )


def as_admin(session: Session, b: Billing) -> None:
    use_context(session, user_id=b.admin)


def gmc_invoice(session: Session, b: Billing, **values: object) -> uuid.UUID:
    """GMC's First Term invoice: 580 students on Standard at N500, N290,000 (AC19.3)."""
    as_admin(session, b)
    return issue_invoice(session, b.gmc, b.first_term, b.version, **values)  # type: ignore[arg-type]


def ngozi_pays(
    session: Session, b: Billing, invoice: uuid.UUID, reference: str = "SF-PAY-0001"
) -> uuid.UUID:
    use_context(session, school_id=b.gmc, user_id=b.ngozi)
    return start_payment(session, b.gmc, invoice, reference)


def invoice_status(session: Session, invoice: uuid.UUID) -> str:
    status: str = session.scalar(
        text("select status from invoices where id = :id"), {"id": invoice}
    )
    return status


# --- pricing (F19 rules 1 to 6) -------------------------------------------------------


def test_each_pricing_save_is_a_new_version(billing: Billing, db_session: Session) -> None:
    as_admin(db_session, billing)
    create_pricing_version(db_session)

    rows = [
        tuple(row)
        for row in db_session.execute(
            text("select version, created_by from pricing_versions order by version")
        )
    ]
    assert rows == [(1, billing.admin), (2, billing.admin)]


def test_only_the_super_admin_changes_pricing(billing: Billing, db_session: Session) -> None:
    # Non-negotiable: "Only the super admin changes pricing".
    use_context(db_session, school_id=billing.gmc, user_id=billing.ngozi)

    with violates(db_session, "pricing_versions_by_super_admin"):
        create_pricing_version(db_session)


def test_only_the_super_admin_adds_plans(billing: Billing, db_session: Session) -> None:
    use_context(db_session, school_id=billing.gmc, user_id=billing.ngozi)

    with violates(db_session, "pricing_tiers_by_super_admin"):
        db_session.execute(
            text(
                "insert into pricing_tiers (version_id, position, name, min_students,"
                " max_students, price_kobo) values (:id, 4, 'Gold', 2001, null, 20000)"
            ),
            {"id": billing.version},
        )


@pytest.mark.parametrize(
    "tiers",
    [
        (("Basic", 1, 499, 100_000), ("Standard", 501, None, 50_000)),  # a gap
        (("Basic", 1, 500, 100_000), ("Standard", 500, None, 50_000)),  # an overlap
        (("Basic", 2, 499, 100_000), ("Standard", 500, None, 50_000)),  # not from 1
        (("Basic", 1, None, 100_000), ("Standard", 500, None, 50_000)),  # open-ended too soon
        (("Basic", 1, 499, 100_000), ("Standard", 500, 1000, 50_000)),  # no open-ended plan
    ],
)
def test_plans_cover_every_count_once(
    billing: Billing, db_session: Session, tiers: tuple[tuple[str, int, int | None, int], ...]
) -> None:
    # AC19.1 and D-090.
    as_admin(db_session, billing)
    create_pricing_version(db_session, tiers)

    with violates(db_session, "pricing_versions_tiers_cover_all_counts"):
        run_commit_checks(db_session)


def test_a_saved_version_takes_no_new_plans(billing: Billing, db_session: Session) -> None:
    # Adding a plan to version 1 would change the prices its invoices used.
    as_admin(db_session, billing)
    db_session.execute(
        text(
            "insert into pricing_tiers (version_id, position, name, min_students, max_students,"
            " price_kobo) values (:id, 4, 'Gold', 2001, null, 20000)"
        ),
        {"id": billing.version},
    )

    with violates(db_session, "pricing_versions_tiers_cover_all_counts"):
        run_commit_checks(db_session)


@pytest.mark.parametrize(
    ("tiers", "rule"),
    [
        ((("Basic", 1, None, 0),), "ck_pricing_tiers_price_positive"),
        ((("Basic", 1, 499, 100), ("basic", 500, None, 50)), "ix_pricing_tiers_unique_name"),
    ],
)
def test_plans_have_a_price_and_a_name_once(
    billing: Billing,
    db_session: Session,
    tiers: tuple[tuple[str, int, int | None, int], ...],
    rule: str,
) -> None:
    as_admin(db_session, billing)

    with violates(db_session, rule):
        create_pricing_version(db_session, tiers)


@pytest.mark.parametrize(
    ("statement", "rule"),
    [
        ("update pricing_tiers set price_kobo = 1", "pricing_tiers_append_only"),
        ("delete from pricing_tiers", "pricing_tiers_append_only"),
        ("delete from pricing_versions", "pricing_versions_append_only"),
    ],
)
def test_a_pricing_version_never_changes(
    billing: Billing, db_session: Session, statement: str, rule: str
) -> None:
    # AC19.5 and D-090: issued invoices keep their version.
    with violates(db_session, rule):
        db_session.execute(text(statement))


# --- subscriptions and invoices (F19 rules 7 to 9 and 12) ----------------------------


def test_one_subscription_per_school(billing: Billing, db_session: Session) -> None:
    with violates(db_session, "uq_school_subscriptions_school_id"):
        set_subscription(db_session, billing.gmc)
    with violates(db_session, "ck_school_subscriptions_status_allowed"):
        db_session.execute(
            text("update school_subscriptions set status = 'paused' where school_id = :id"),
            {"id": billing.gmc},
        )


@pytest.mark.parametrize(
    ("students", "tier", "rate", "amount", "cliff"),
    [
        (580, "Standard", 50_000, 29_000_000, False),  # N290,000
        (642, "Standard", 50_000, 30_030_000, True),  # N300,300, capped
        (499, "Basic", 100_000, 25_000_000, True),  # N250,000, capped
    ],
)
def test_invoices_keep_the_arithmetic_right(
    billing: Billing,
    db_session: Session,
    students: int,
    tier: str,
    rate: int,
    amount: int,
    cliff: bool,
) -> None:
    # AC19.3 (cliff protection on), in kobo.
    invoice = gmc_invoice(
        db_session,
        billing,
        students=students,
        tier=tier,
        rate_kobo=rate,
        amount_kobo=amount,
        cliff_cap_applied=cliff,
    )

    assert invoice_status(db_session, invoice) == "unpaid"


@pytest.mark.parametrize(
    ("amount", "cliff"),
    [(28_000_000, False), (29_000_000, True), (29_000_001, False)],
)
def test_an_invoice_amount_matches_its_snapshot(
    billing: Billing, db_session: Session, amount: int, cliff: bool
) -> None:
    # Less than students times rate only when the cap applied; never more.
    with violates(db_session, "ck_invoices_amount_matches"):
        gmc_invoice(db_session, billing, amount_kobo=amount, cliff_cap_applied=cliff)


@pytest.mark.parametrize(("tier", "rate"), [("Standard", 45_000), ("Gold", 50_000)])
def test_an_invoice_rate_comes_from_the_price_list(
    billing: Billing, db_session: Session, tier: str, rate: int
) -> None:
    with violates(db_session, "invoices_rate_from_pricing"):
        gmc_invoice(db_session, billing, tier=tier, rate_kobo=rate)


def test_only_the_super_admin_voids(billing: Billing, db_session: Session) -> None:
    invoice = gmc_invoice(db_session, billing)
    use_context(db_session, school_id=billing.gmc, user_id=billing.ngozi)

    with violates(db_session, "invoices_voided_by_super_admin"):
        db_session.execute(
            text("update invoices set status = 'void', void_reason = 'No' where id = :id"),
            {"id": invoice},
        )


def test_one_term_invoice_per_school_per_term(billing: Billing, db_session: Session) -> None:
    gmc_invoice(db_session, billing)

    with violates(db_session, "ix_invoices_one_per_term"):
        gmc_invoice(db_session, billing)
    gmc_invoice(db_session, billing, kind="adjustment", students=12)


def test_only_the_super_admin_issues_invoices(billing: Billing, db_session: Session) -> None:
    use_context(db_session, school_id=billing.gmc, user_id=billing.ngozi)

    with violates(db_session, "invoices_issued_by_super_admin"):
        issue_invoice(db_session, billing.gmc, billing.first_term, billing.version)


@pytest.mark.parametrize(
    "change", ["amount_kobo = 1", "billable_students = 1", "due_on = date '2027-02-01'"]
)
def test_an_issued_invoice_never_changes(
    billing: Billing, db_session: Session, change: str
) -> None:
    # AC19.5.
    invoice = gmc_invoice(db_session, billing)

    with violates(db_session, "invoices_kept"):
        db_session.execute(text(f"update invoices set {change} where id = :id"), {"id": invoice})  # noqa: S608


def test_voiding_needs_a_reason_and_is_final(billing: Billing, db_session: Session) -> None:
    invoice = gmc_invoice(db_session, billing)
    void = text("update invoices set status = 'void', void_reason = :reason where id = :id")

    with violates(db_session, "invoices_void_needs_reason"):
        db_session.execute(void, {"reason": None, "id": invoice})
    db_session.execute(void, {"reason": "Issued for the wrong term", "id": invoice})
    with violates(db_session, "invoices_status_change_allowed"):
        db_session.execute(
            text("update invoices set status = 'unpaid' where id = :id"), {"id": invoice}
        )


def test_an_invoice_is_paid_only_by_a_payment(billing: Billing, db_session: Session) -> None:
    # Non-negotiable: never marked paid without a verified payment.
    invoice = gmc_invoice(db_session, billing)

    with violates(db_session, "invoices_paid_with_a_payment"):
        db_session.execute(
            text("update invoices set status = 'paid' where id = :id"), {"id": invoice}
        )


# --- payments (F19 rule 11, D-093 to D-096) ------------------------------------------


def test_a_payment_takes_its_amount_from_the_invoice(billing: Billing, db_session: Session) -> None:
    # Non-negotiable: amounts come from the server invoice, never the browser.
    invoice = gmc_invoice(db_session, billing)
    payment = ngozi_pays(db_session, billing, invoice)

    row = db_session.execute(
        text("select amount_kobo, currency, status, created_by from payments where id = :id"),
        {"id": payment},
    ).one()
    assert tuple(row) == (29_000_000, "NGN", "pending", billing.ngozi)


def test_only_a_school_admin_starts_a_payment(billing: Billing, db_session: Session) -> None:
    invoice = gmc_invoice(db_session, billing)
    use_context(db_session, school_id=billing.gmc, user_id=billing.tunde)

    with violates(db_session, "payments_started_by_school_admin"):
        start_payment(db_session, billing.gmc, invoice, "SF-PAY-0001")


def test_a_void_invoice_takes_no_payment(billing: Billing, db_session: Session) -> None:
    invoice = gmc_invoice(db_session, billing)
    db_session.execute(
        text("update invoices set status = 'void', void_reason = 'Duplicate' where id = :id"),
        {"id": invoice},
    )

    with violates(db_session, "payments_for_an_unpaid_invoice"):
        ngozi_pays(db_session, billing, invoice)


def test_success_marks_the_invoice_paid_with_a_receipt(
    billing: Billing, db_session: Session
) -> None:
    # D-094 and D-095: one transaction marks the invoice paid and numbers the receipt.
    invoice = gmc_invoice(db_session, billing)
    payment = ngozi_pays(db_session, billing, invoice)
    use_context(db_session)  # the webhook worker: nobody signed in

    db_session.execute(SUCCEED, {"gateway_reference": "T123456789", "id": payment})

    receipt = db_session.scalar(
        text("select receipt_number from payments where id = :id"), {"id": payment}
    )
    assert invoice_status(db_session, invoice) == "paid"
    assert receipt.startswith("SF-RCPT-")


def test_an_invoice_is_paid_once(billing: Billing, db_session: Session) -> None:
    # AC19.7: a second success for the same invoice is refused.
    invoice = gmc_invoice(db_session, billing)
    first, second = (ngozi_pays(db_session, billing, invoice, f"SF-PAY-000{n}") for n in (1, 2))
    db_session.execute(SUCCEED, {"gateway_reference": "T1", "id": first})

    with violates(db_session, "payments_invoice_still_unpaid"):
        db_session.execute(SUCCEED, {"gateway_reference": "T2", "id": second})


def test_success_needs_proof(billing: Billing, db_session: Session) -> None:
    invoice = gmc_invoice(db_session, billing)
    payment = ngozi_pays(db_session, billing, invoice)

    with violates(db_session, "ck_payments_succeeded_with_proof"):
        db_session.execute(SUCCEED, {"gateway_reference": None, "id": payment})


@pytest.mark.parametrize(
    "statement",
    [
        "update payments set amount_kobo = 1 where id = :id",
        "update payments set currency = 'USD' where id = :id",
        "delete from payments where id = :id",
    ],
)
def test_a_payment_record_never_changes(
    billing: Billing, db_session: Session, statement: str
) -> None:
    payment = ngozi_pays(db_session, billing, gmc_invoice(db_session, billing))

    with violates(db_session, "payments_kept"):
        db_session.execute(text(statement), {"id": payment})


def test_a_finished_payment_stays_finished(billing: Billing, db_session: Session) -> None:
    payment = ngozi_pays(db_session, billing, gmc_invoice(db_session, billing))
    db_session.execute(
        text("update payments set status = 'failed' where id = :id"), {"id": payment}
    )

    with violates(db_session, "payments_status_change_allowed"):
        db_session.execute(SUCCEED, {"gateway_reference": "T1", "id": payment})


def test_a_webhook_event_is_stored_once(billing: Billing, db_session: Session) -> None:
    # AC19.7 and D-094: the same event twice is refused.
    record_payment_event(db_session, "evt_fictional_1")

    with violates(db_session, "uq_payment_events_provider_event_id"):
        record_payment_event(db_session, "evt_fictional_1")


def test_a_webhook_event_keeps_what_it_said(billing: Billing, db_session: Session) -> None:
    record_payment_event(db_session, "evt_fictional_1")

    db_session.execute(text("update payment_events set status = 'processed', processed_at = now()"))
    with violates(db_session, "payment_events_kept"):
        db_session.execute(text("update payment_events set event_type = 'charge.failed'"))


# --- row-level security and grants ---------------------------------------------------


def bill_gmc(session: Session, b: Billing) -> None:
    ngozi_pays(session, b, gmc_invoice(session, b))
    record_payment_event(session, "evt_fictional_1")


@pytest.mark.parametrize("table", SCHOOL_TABLES)
def test_a_school_sees_only_its_own_billing(
    billing: Billing, db_session: Session, table: str
) -> None:
    # AC19.8: BSA cannot see GMC's invoice.
    bill_gmc(db_session, billing)

    with acting_as(db_session, "app_user", school_id=billing.gmc):
        own = db_session.scalar(COUNT[table])
    with acting_as(db_session, "app_user", school_id=billing.bsa):
        other = db_session.scalar(COUNT[table])

    assert own >= 1
    assert other == (1 if table == "school_subscriptions" else 0)


@pytest.mark.parametrize(
    "statement",
    [
        "select count(*) from payment_events",
        "update invoices set status = 'paid'",
        "update payments set status = 'succeeded'",
        "update payments set amount_kobo = 1",
        "insert into pricing_versions default values",
        "update school_subscriptions set status = 'active'",
    ],
)
def test_schools_cannot_change_their_billing(
    billing: Billing, db_session: Session, statement: str
) -> None:
    # Prices, invoices and payment results come only from the platform.
    bill_gmc(db_session, billing)

    with (
        acting_as(db_session, "app_user", school_id=billing.gmc, user_id=billing.ngozi),
        refused(db_session),
    ):
        db_session.execute(text(statement))


def test_school_users_can_read_the_pricing_table(billing: Billing, db_session: Session) -> None:
    # The billing card's projected next-term cost reads the current prices.
    with acting_as(db_session, "app_user", school_id=billing.gmc):
        assert db_session.scalar(COUNT["pricing_tiers"]) == 3


def test_the_platform_runs_billing(billing: Billing, db_session: Session) -> None:
    bill_gmc(db_session, billing)

    with acting_as(db_session, "app_platform", user_id=billing.admin):
        counts = [db_session.scalar(COUNT[table]) for table in (*SCHOOL_TABLES, "payment_events")]
        issue_invoice(db_session, billing.gmc, billing.second_term, billing.version)

    assert all(count >= 1 for count in counts)


@pytest.mark.parametrize("role", ["app_verifier", "app_sender"])
@pytest.mark.parametrize("table", (*SCHOOL_TABLES, "payment_events"))
def test_other_roles_cannot_read_billing(
    billing: Billing, db_session: Session, role: str, table: str
) -> None:
    bill_gmc(db_session, billing)

    with acting_as(db_session, role), refused(db_session):
        db_session.execute(COUNT[table])
