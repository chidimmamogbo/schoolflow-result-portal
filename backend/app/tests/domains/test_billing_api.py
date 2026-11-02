"""School subscription billing (BUILD_PROMPT 9.2q to 9.2s; SPEC F19; AT-35 to AT-38; D-087, D-097).

Behaviour: only the super admin saves price lists (each a new version), issues
invoices (a snapshot that never changes), voids them and records manual
payments. A school admin sees only their own school's billing and starts a
payment whose amount comes from the invoice; the return from Paystack never
marks anything paid. Only a webhook with a valid signature, followed by
Paystack's own Verify answer with the right status, amount, currency and
reference, marks an invoice Paid, with one numbered receipt, a notice to the
school admins and a receipt email. A forged webhook changes nothing and stores
nothing; a repeated one changes nothing more. If Paystack cannot be reached the
event waits and is tried again. With billing off a school sees no invoices or
payment prompts. All data is fictional; no test reaches Paystack.
"""

import hashlib
import hmac
import json
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import load_settings
from app.platform import pdf
from app.platform.email.provider import RecordingProvider
from app.platform.email.sender import send_due
from app.platform.payments.gateway import (
    GatewayError,
    PaystackGateway,
    RecordingGateway,
    Verified,
)
from app.src.billing import processing
from app.src.billing.render import receipt_html
from app.src.billing.router import get_base_url, get_payment_gateway, get_webhook_secret
from app.src.billing.schemas import Receipt
from app.src.billing.utils import money, nice_date
from app.src.cron.router import get_cron_secret, get_payment_runner, payment_run
from app.tests.auth_support import (
    PlatformAsRole,
    build_platform_app,
    client_for,
    csrf,
    logged_in,
    make_login,
    use_fast_hashing,
)
from app.tests.factories import (
    create_arm,
    create_class,
    create_school,
    create_session,
    create_student,
    create_term,
    enrol,
)

SECRET = "sk_test_fictional_key_for_signing_only"  # noqa: S105 (fictional)
CRON = "a-long-random-cron-secret-for-tests"
BASE = "https://schoolflow.example"
EVENT_ID = 4099260516


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


def add_school(
    db: Session, code: str, name: str, *, pupils: int = 3, billing: bool = True, term: bool = True
) -> uuid.UUID:
    school = create_school(db, code=code, name=name)
    db.execute(
        text(
            "insert into school_subscriptions (school_id, billing_enabled, status)"
            " values (:s, :on, :status)"
        ),
        {"s": school, "on": billing, "status": "active" if billing else "free_pilot"},
    )
    session_id = create_session(db, school)
    if term:
        create_term(db, school, session_id, 1, is_active=True)
    arm = create_arm(db, school, create_class(db, school, "junior_secondary", "JSS 1"))
    for n in range(pupils):
        pupil = create_student(db, school, f"{code}/2026/{n:03d}", "Okafor", f"Pupil{n}")
        enrol(db, school, pupil, session_id, arm)
    return school


@dataclass
class Billing:
    app: FastAPI
    db: Session
    gateway: RecordingGateway
    owner: TestClient
    ngozi: TestClient
    gmc: uuid.UUID
    kicks: list[str]


def as_platform(db: Session) -> Any:
    @contextmanager
    def batch() -> Generator[Any]:
        try:
            yield PlatformAsRole(db)
        finally:
            db.execute(text("reset role"))

    return batch


@pytest.fixture
def billing(db_session: Session) -> Billing:
    gmc = add_school(db_session, "GMC", "Greenfield Model College")
    make_login(db_session, username="platform.owner", full_name="Ada Platform", is_super_admin=True)
    make_login(
        db_session, username="ngozi.okeke", full_name="Ngozi Okeke", email="ngozi@gmc.example",
        school_id=gmc, role="school_admin", is_primary=True,
    )  # fmt: skip
    app = build_platform_app(db_session)
    gateway = RecordingGateway()
    kicks: list[str] = []
    app.dependency_overrides[get_payment_gateway] = lambda: gateway
    app.dependency_overrides[get_webhook_secret] = lambda: SecretStr(SECRET)
    app.dependency_overrides[get_base_url] = lambda: BASE + "/"
    app.dependency_overrides[processing.get_payment_kick] = lambda: lambda: kicks.append("run")
    return Billing(
        app, db_session, gateway, logged_in(app, "platform.owner"),
        logged_in(app, "ngozi.okeke"), gmc, kicks,
    )  # fmt: skip


def send(client: TestClient, method: str, url: str, body: Any = None) -> tuple[int, Any]:
    response = client.request(method, f"/api/v1{url}", json=body, headers=csrf(client))
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def generate(b: Billing, school: uuid.UUID | None = None, **more: Any) -> dict[str, Any]:
    body = {"school_id": str(school or b.gmc), **more}
    status, answer = send(b.owner, "POST", "/platform/invoices/generate", body)
    assert status == 200, answer
    return answer


def invoice_of(b: Billing) -> dict[str, Any]:
    [invoice] = generate(b)["created"]
    return invoice


def paying(b: Billing) -> tuple[dict[str, Any], str]:
    invoice = invoice_of(b)
    status, checkout = send(b.ngozi, "POST", f"/school/invoices/{invoice['id']}/pay")
    assert status == 200, checkout
    return invoice, checkout["reference"]


def paid_at_paystack(ours: str, amount: int, **changes: Any) -> Verified:
    answer: dict[str, Any] = {
        "status": "success",
        "amount_kobo": amount,
        "currency": "NGN",
        "reference": ours,
        "gateway_id": str(EVENT_ID),
    }
    return Verified(**(answer | changes))


def signed(body: bytes, secret: str = SECRET) -> dict[str, str]:
    return {"x-paystack-signature": hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()}


def webhook_body(reference: str, event: str = "charge.success", **data: Any) -> bytes:
    payload = {
        "event": event,
        "data": {"id": EVENT_ID, "status": "success", "reference": reference, "amount": 1} | data,
    }
    return json.dumps(payload).encode()


def post_webhook(b: Billing, body: bytes, headers: dict[str, str] | None = None) -> Any:
    response = client_for(b.app).post("/api/v1/webhooks/payments", content=body, headers=headers)
    b.db.execute(text("reset role"))
    return response


def process(b: Billing) -> processing.ProcessReport:
    return processing.process_pending(as_platform(b.db), b.gateway)


def pay_by_webhook(b: Billing) -> tuple[dict[str, Any], str]:
    invoice, reference = paying(b)
    b.gateway.answers[reference] = paid_at_paystack(reference, invoice["amount_kobo"])
    body = webhook_body(reference)
    assert post_webhook(b, body, signed(body)).status_code == 200
    process(b)
    return invoice, reference


def state(b: Billing, invoice: dict[str, Any]) -> tuple[str, list[str], int]:
    """The invoice's status, its payments' statuses and how many receipts it has."""
    status = b.db.scalar(text("select status from invoices where id = :i"), {"i": invoice["id"]})
    payments = list(
        b.db.scalars(
            text("select status from payments where invoice_id = :i order by status"),
            {"i": invoice["id"]},
        )
    )
    receipts = b.db.scalar(
        text("select count(receipt_number) from payments where invoice_id = :i"),
        {"i": invoice["id"]},
    )
    return status, payments, receipts


def audit_actions(b: Billing, school: uuid.UUID | None = None) -> set[str]:
    rows = b.db.scalars(
        text("select action from audit_events where school_id is not distinct from :s"),
        {"s": school},
    )
    return set(rows)


# --- price lists ----------------------------------------------------------------------------------
THREE_PLANS: list[dict[str, Any]] = [
    {"name": "Basic", "min_students": 1, "max_students": 499, "price_kobo": 120_000},
    {"name": "Standard", "min_students": 500, "max_students": 1000, "price_kobo": 50_000},
    {"name": "Premium", "min_students": 1001, "max_students": None, "price_kobo": 30_000},
]


def test_the_editor_starts_with_the_defaults_and_the_price_check(billing: Billing) -> None:
    """AC19.4, AT-35.1."""
    status, page = send(billing.owner, "GET", "/platform/pricing")
    assert status == 200
    assert page["version"] is None and page["cliff_protection"] is True
    assert [p["name"] for p in page["plans"]] == ["Basic", "Standard", "Premium"]
    assert page["price_check"] == [
        {"from_students": 251, "to_students": 499},
        {"from_students": 601, "to_students": 1000},
    ]


def test_each_save_is_a_new_audited_version(billing: Billing) -> None:
    """AT-35.1, F19 rule 6."""
    for expected, price in ((1, 120_000), (2, 110_000)):
        plans = [{**THREE_PLANS[0], "price_kobo": price}, *THREE_PLANS[1:]]
        status, page = send(billing.owner, "POST", "/platform/pricing", {"plans": plans})
        assert status == 201, page
        assert page["version"] == expected
    assert send(billing.owner, "GET", "/platform/pricing")[1]["plans"][0]["price_kobo"] == 110_000
    _, versions = send(billing.owner, "GET", "/platform/pricing/versions")
    assert [(v["version"], v["plans"][0]["price_kobo"]) for v in versions] == [
        (2, 110_000),
        (1, 120_000),
    ]
    assert "pricing.save" in audit_actions(billing)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"max_students": 520}, "Standard overlaps or leaves a gap after Basic."),
        ({"max_students": 480}, "Standard overlaps or leaves a gap after Basic."),
    ],
)
def test_overlaps_and_gaps_are_refused(
    billing: Billing, change: dict[str, Any], message: str
) -> None:
    """AC19.1, AT-35.2."""
    plans = [{**THREE_PLANS[0], **change}, *THREE_PLANS[1:]]
    status, body = send(billing.owner, "POST", "/platform/pricing", {"plans": plans})
    assert (status, body["code"]) == (422, "plans_invalid")
    assert {"field": "plans", "message": message} in body["errors"]
    assert billing.db.scalar(text("select count(*) from pricing_versions")) == 0


@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        ("GET", "/platform/pricing", None),
        ("POST", "/platform/pricing", {"plans": THREE_PLANS}),
        ("GET", "/platform/pricing/versions", None),
        ("POST", "/platform/invoices/generate", {}),
        ("GET", "/platform/invoices", None),
        ("GET", "/platform/billing/schools", None),
        ("GET", "/platform/billing/summary", None),
        ("POST", f"/platform/invoices/{uuid.uuid4()}/void", {"reason": "No"}),
        (
            "POST",
            f"/platform/invoices/{uuid.uuid4()}/manual-payment",
            {"reference": "x", "note": "y"},
        ),
        ("PATCH", f"/platform/schools/{uuid.uuid4()}/subscription", {"billing_enabled": False}),
        ("POST", f"/platform/payments/{uuid.uuid4()}/resend-receipt", None),
    ],
)
def test_only_the_super_admin_reaches_the_platform_side(
    billing: Billing, method: str, url: str, body: Any
) -> None:
    """AT-35.3."""
    assert send(billing.ngozi, method, url, body)[0] == 403
    assert billing.db.scalar(text("select count(*) from pricing_versions")) == 0


# --- invoices -------------------------------------------------------------------------------------


def test_an_invoice_is_a_snapshot_of_the_term(billing: Billing) -> None:
    """F19 rule 8, D-091: Basic at ₦1,000 for 3 pupils, due in 14 days."""
    invoice = invoice_of(billing)
    assert invoice["term"] == "First Term 2026/2027"
    assert (invoice["kind"], invoice["billable_students"], invoice["plan"]) == ("term", 3, "Basic")
    assert (invoice["rate_kobo"], invoice["amount_kobo"]) == (100_000, 300_000)
    assert (invoice["status"], invoice["cliff_cap_applied"]) == ("unpaid", False)
    days = billing.db.scalar(
        text(
            "select due_on - (now() at time zone 'Africa/Lagos')::date from invoices where id = :i"
        ),
        {"i": invoice["id"]},
    )
    assert days == 14
    assert billing.db.scalar(text("select version from pricing_versions")) == 1
    assert "invoices.generate" in audit_actions(billing, billing.gmc)
    assert billing.db.scalar(text("select status from school_subscriptions")) == "due"


def test_only_active_enrolled_pupils_count(billing: Billing) -> None:
    """D-091."""
    ids = list(billing.db.scalars(text("select id from students order by admission_number")))
    billing.db.execute(
        text("update students set status = 'withdrawn' where id = :i"), {"i": ids[0]}
    )
    billing.db.execute(
        text("update enrolments set left_on = current_date where student_id = :i"), {"i": ids[1]}
    )
    assert invoice_of(billing)["billable_students"] == 1


def test_one_term_invoice_per_school_per_term(billing: Billing) -> None:
    """F19 rule 8."""
    invoice_of(billing)
    answer = generate(billing)
    assert answer["created"] == []
    assert [s["reason"] for s in answer["skipped"]] == ["Already invoiced for this term"]


def test_generating_for_every_school_skips_the_ones_that_cannot_be_billed(billing: Billing) -> None:
    db = billing.db
    add_school(db, "BSA", "Bright Star Academy", billing=False)
    add_school(db, "RCS", "Riverside College", term=False)
    add_school(db, "NEW", "New Dawn School", pupils=0)
    gone = add_school(db, "OLD", "Old Mill School")
    db.execute(text("update schools set status = 'suspended' where id = :s"), {"s": gone})
    status, answer = send(billing.owner, "POST", "/platform/invoices/generate", {})
    assert status == 200, answer
    assert [i["school_id"] for i in answer["created"]] == [str(billing.gmc)]
    assert {s["name"]: s["reason"] for s in answer["skipped"]} == {
        "Riverside College": "No active term",
        "New Dawn School": "No billable students",
        "Old Mill School": "School is suspended",
    }


def test_a_school_with_billing_off_is_not_billed_even_when_named(billing: Billing) -> None:
    bsa = add_school(billing.db, "BSA", "Bright Star Academy", billing=False)
    assert [s["reason"] for s in generate(billing, bsa)["skipped"]] == ["Billing is off"]


def test_an_unknown_school_is_not_found(billing: Billing) -> None:
    status, _ = send(
        billing.owner, "POST", "/platform/invoices/generate", {"school_id": str(uuid.uuid4())}
    )
    assert status == 404
    assert (
        send(billing.owner, "POST", "/platform/invoices/generate", {"school_id": "nope"})[0] == 404
    )


def test_a_price_change_never_reaches_an_issued_invoice(billing: Billing) -> None:
    """AC19.5, AT-36.3."""
    invoice = invoice_of(billing)
    send(billing.owner, "POST", "/platform/pricing", {"plans": THREE_PLANS})
    assert send(billing.owner, "GET", f"/platform/invoices/{invoice['id']}")[1] == invoice


@pytest.mark.parametrize(
    ("cliff", "amount", "capped"), [(True, 40_000, True), (False, 300_000, False)]
)
def test_cliff_protection_follows_the_platform_setting(
    billing: Billing, cliff: bool, amount: int, capped: bool
) -> None:
    """AC19.2, AC19.3; 3 pupils at ₦1,000, while 4 at ₦100 would cost ₦400."""
    plans = [
        {"name": "Small", "min_students": 1, "max_students": 3, "price_kobo": 100_000},
        {"name": "Large", "min_students": 4, "max_students": None, "price_kobo": 10_000},
    ]
    send(billing.owner, "POST", "/platform/pricing", {"plans": plans})
    status, _ = send(
        billing.owner, "PATCH", "/platform/settings", {"billing": {"cliff_protection": cliff}}
    )
    assert status == 200
    invoice = invoice_of(billing)
    assert (invoice["amount_kobo"], invoice["cliff_cap_applied"]) == (amount, capped)


def test_an_adjustment_invoice_keeps_the_terms_rate(billing: Billing) -> None:
    """F19 rule 8, for pupils added later."""
    assert [s["reason"] for s in generate(billing, adjustment_students=2)["skipped"]] == [
        "No term invoice to adjust"
    ]
    invoice_of(billing)
    send(billing.owner, "POST", "/platform/pricing", {"plans": THREE_PLANS})
    [adjustment] = generate(billing, adjustment_students=2)["created"]
    assert (adjustment["kind"], adjustment["billable_students"]) == ("adjustment", 2)
    assert (adjustment["rate_kobo"], adjustment["amount_kobo"]) == (100_000, 200_000)
    status, body = send(
        billing.owner, "POST", "/platform/invoices/generate", {"adjustment_students": 2}
    )
    assert (status, body["code"]) == (422, "school_required")


def test_voiding_needs_a_reason_and_frees_the_term(billing: Billing) -> None:
    """F19 rule 12, D-157."""
    invoice = invoice_of(billing)
    url = f"/platform/invoices/{invoice['id']}/void"
    assert send(billing.owner, "POST", url, {"reason": ""})[0] == 422
    status, voided = send(billing.owner, "POST", url, {"reason": "Wrong count"})
    assert (status, voided["status"], voided["void_reason"]) == (200, "void", "Wrong count")
    assert "invoices.void" in audit_actions(billing, billing.gmc)
    assert billing.db.scalar(text("select status from school_subscriptions")) == "active"
    assert (
        (send(billing.owner, "POST", url, {"reason": "Again"})[1])["code"] == "invoice_not_unpaid"
    )
    assert len(generate(billing)["created"]) == 1


def test_a_void_invoice_takes_no_payment(billing: Billing) -> None:
    invoice = invoice_of(billing)
    send(billing.owner, "POST", f"/platform/invoices/{invoice['id']}/void", {"reason": "Wrong"})
    status, body = send(billing.ngozi, "POST", f"/school/invoices/{invoice['id']}/pay")
    assert (status, body["code"]) == (409, "invoice_not_unpaid")
    assert not billing.gateway.started


def test_a_manual_payment_pays_the_invoice_with_a_receipt_and_a_note(billing: Billing) -> None:
    """F19 rule 12, D-096."""
    invoice = invoice_of(billing)
    url = f"/platform/invoices/{invoice['id']}/manual-payment"
    status, paid = send(
        billing.owner, "POST", url, {"reference": "BANK-TELLER-77", "note": "Teller"}
    )
    assert (status, paid["status"], paid["reference"]) == (200, "paid", "BANK-TELLER-77")
    assert paid["receipt_number"].startswith("SF-RCPT-")
    assert state(billing, invoice) == ("paid", ["succeeded"], 1)
    reason = billing.db.scalar(
        text("select reason from audit_events where action = 'invoices.paid'")
    )
    assert reason == "Teller"
    assert billing.db.scalar(text("select status from school_subscriptions")) == "active"
    status, body = send(billing.owner, "POST", url, {"reference": "AGAIN", "note": "Twice"})
    assert (status, body["code"]) == (409, "invoice_not_unpaid")
    assert (
        send(billing.owner, "POST", f"/platform/invoices/{invoice['id']}/void", {"reason": "No"})
    )[0] == 409


def test_the_overview_and_the_summary(billing: Billing) -> None:
    """D-092, BUILD_PROMPT 9.2q."""
    bsa = add_school(billing.db, "BSA", "Bright Star Academy", pupils=2)
    pay_by_webhook(billing)
    [unpaid] = generate(billing, bsa)["created"]
    rcs = add_school(billing.db, "RCS", "Riverside College", pupils=1)
    [gone] = generate(billing, rcs)["created"]
    send(billing.owner, "POST", f"/platform/invoices/{gone['id']}/void", {"reason": "Wrong"})
    _, schools = send(billing.owner, "GET", "/platform/billing/schools")
    rows = {s["code"]: s for s in schools}
    assert rows["GMC"]["status"] == "active" and rows["GMC"]["current_invoice"]["status"] == "paid"
    assert rows["BSA"]["status"] == "due"
    assert rows["BSA"]["current_invoice"]["id"] == unpaid["id"]
    assert rows["BSA"]["students"] == 2 and rows["BSA"]["grace_period_days"] == 14
    assert rows["RCS"]["current_invoice"] is None
    _, summary = send(billing.owner, "GET", "/platform/billing/summary")
    assert summary == [
        {
            "term": "First Term 2026/2027",
            "invoices": 2,
            "invoiced_kobo": 500_000,
            "paid_kobo": 300_000,
            "outstanding_kobo": 200_000,
        }
    ]


def test_the_subscription_can_be_changed(billing: Billing) -> None:
    """F19 rule 7."""
    url = f"/platform/schools/{billing.gmc}/subscription"
    invoice_of(billing)
    status, row = send(billing.owner, "PATCH", url, {"grace_period_days": 3})
    assert (status, row["grace_period_days"], row["status"]) == (200, 3, "due")
    assert (
        send(billing.owner, "PATCH", url, {"use_platform_grace": True})[1]["grace_period_days"]
        == 14
    )
    assert (
        send(billing.owner, "PATCH", url, {"billing_enabled": False})[1]["status"] == "free_pilot"
    )
    assert send(billing.owner, "PATCH", url, {"billing_enabled": True})[1]["status"] == "due"
    status, body = send(billing.owner, "PATCH", url, {"suspended": True})
    assert (status, body["code"]) == (422, "reason_required")
    assert (
        send(billing.owner, "PATCH", url, {"suspended": True, "reason": "Unpaid"})[1]["status"]
        == "suspended"
    )
    assert (
        billing.db.scalar(text("select status from schools where id = :s"), {"s": billing.gmc})
        == "suspended"
    )
    assert send(billing.owner, "PATCH", url, {"suspended": False})[1]["status"] == "due"
    assert "subscriptions.change" in audit_actions(billing, billing.gmc)
    assert (
        send(
            billing.owner,
            "PATCH",
            f"/platform/schools/{uuid.uuid4()}/subscription",
            {"suspended": False},
        )[0]
        == 404
    )
    assert send(billing.owner, "PATCH", url, {"grace_period_days": 91})[0] == 422


def test_a_school_past_its_grace_is_overdue_and_the_daily_run_saves_it(billing: Billing) -> None:
    """D-092."""
    invoice = invoice_of(billing)
    db = billing.db
    db.execute(text("alter table invoices disable trigger invoices_rules"))
    db.execute(
        text("update invoices set due_on = current_date - 30 where id = :i"), {"i": invoice["id"]}
    )
    db.execute(text("alter table invoices enable trigger invoices_rules"))
    _, card = send(billing.ngozi, "GET", "/school/billing")
    assert card["status"] == "overdue"
    assert db.scalar(text("select status from school_subscriptions")) == "due"
    report = payment_run(as_platform(db), billing.gateway)
    assert report.subscriptions_refreshed == 1
    assert db.scalar(text("select status from school_subscriptions")) == "overdue"
    assert payment_run(as_platform(db), None).subscriptions_refreshed == 0


# --- the school's side ----------------------------------------------------------------------------


def test_the_school_admin_sees_the_billing_card(billing: Billing) -> None:
    """F19 rule 10, AT-36.4."""
    invoice = invoice_of(billing)
    status, card = send(billing.ngozi, "GET", "/school/billing")
    assert status == 200
    assert card["billing_enabled"] is True and card["status"] == "due"
    assert (card["plan"], card["billable_students"], card["price_per_student_kobo"]) == (
        "Basic",
        3,
        100_000,
    )
    assert (card["amount_due_kobo"], card["due_on"]) == (300_000, invoice["due_on"])
    assert card["next_renewal_on"] == "2027-01-05"
    assert card["projected_next_term_kobo"] == 300_000
    assert send(billing.ngozi, "GET", "/school/invoices")[1] == [invoice]
    assert send(billing.ngozi, "GET", f"/school/invoices/{invoice['id']}")[1] == invoice


def test_a_school_with_no_invoice_yet_sees_what_it_would_pay(billing: Billing) -> None:
    _, card = send(billing.ngozi, "GET", "/school/billing")
    assert (card["status"], card["amount_due_kobo"], card["plan"]) == ("active", 0, "Basic")
    assert card["projected_next_term_kobo"] == 300_000 and card["current_invoice"] is None


def test_billing_off_shows_no_invoices_or_prompts(billing: Billing) -> None:
    """AC19.9, AT-36.5."""
    invoice, reference = paying(billing)
    billing.gateway.started.clear()
    send(
        billing.owner,
        "PATCH",
        f"/platform/schools/{billing.gmc}/subscription",
        {"billing_enabled": False},
    )
    assert send(billing.ngozi, "GET", "/school/billing")[1] == {
        "billing_enabled": False,
        "status": "free_pilot",
        "plan": None,
        "billable_students": None,
        "price_per_student_kobo": None,
        "amount_due_kobo": None,
        "due_on": None,
        "next_renewal_on": None,
        "projected_next_term_kobo": None,
        "current_invoice": None,
    }
    assert send(billing.ngozi, "GET", "/school/invoices")[1] == []
    assert send(billing.ngozi, "GET", f"/school/invoices/{invoice['id']}")[0] == 404
    assert send(billing.ngozi, "POST", f"/school/invoices/{invoice['id']}/pay")[0] == 404
    assert send(billing.ngozi, "GET", f"/school/payments/verify?reference={reference}")[0] == 404
    assert not billing.gateway.started


def test_another_schools_billing_is_not_found(billing: Billing) -> None:
    """AC19.8, AT-36.4."""
    bsa = add_school(billing.db, "BSA", "Bright Star Academy")
    make_login(
        billing.db, username="amaka.bello", email="amaka@bsa.example", school_id=bsa,
        role="school_admin", is_primary=True,
    )  # fmt: skip
    invoice, reference = paying(billing)
    amaka = logged_in(billing.app, "amaka.bello")
    for method, url in (
        ("GET", f"/school/invoices/{invoice['id']}"),
        ("GET", f"/school/invoices/{invoice['id']}/receipt"),
        ("POST", f"/school/invoices/{invoice['id']}/pay"),
        ("GET", f"/school/payments/verify?reference={reference}"),
    ):
        assert send(amaka, method, url)[0] == 404, url
    assert send(amaka, "GET", "/school/invoices")[1] == []


@pytest.mark.parametrize("role", ["teacher", "reviewer", "parent"])
def test_only_school_admins_see_billing(billing: Billing, role: str) -> None:
    make_login(billing.db, username="someone.else", school_id=billing.gmc, role=role)
    client = logged_in(billing.app, "someone.else")
    invoice = invoice_of(billing)
    assert send(client, "GET", "/school/billing")[0] == 403
    assert send(client, "GET", "/school/invoices")[0] == 403
    assert send(client, "POST", f"/school/invoices/{invoice['id']}/pay")[0] == 403


def test_the_super_admin_has_no_school_side(billing: Billing) -> None:
    assert send(billing.owner, "GET", "/school/billing")[0] == 404
    assert send(billing.owner, "GET", "/school/invoices")[0] == 404


def test_paying_takes_the_amount_from_the_invoice(billing: Billing) -> None:
    """AT-37.2: whatever the browser sends is never read."""
    invoice = invoice_of(billing)
    status, checkout = send(
        billing.ngozi, "POST", f"/school/invoices/{invoice['id']}/pay", {"amount_kobo": 100}
    )
    assert status == 200, checkout
    [started] = billing.gateway.started
    assert started["amount_kobo"] == 300_000
    assert started["email"] == "ngozi@gmc.example"
    assert started["callback_url"] == f"{BASE}/school/billing/callback"
    assert started["reference"] == checkout["reference"]
    assert checkout["checkout_url"] == f"https://checkout.example/{checkout['reference']}"
    assert state(billing, invoice) == ("unpaid", ["pending"], 0)
    assert "invoices.pay_started" in audit_actions(billing, billing.gmc)


def test_a_school_admin_with_no_email_pays_under_the_schools_email(billing: Billing) -> None:
    billing.db.execute(text("update users set email = null where username = 'ngozi.okeke'"))
    invoice = invoice_of(billing)
    assert send(billing.ngozi, "POST", f"/school/invoices/{invoice['id']}/pay")[0] == 200
    assert billing.gateway.started[0]["email"] == "office@gmc.example"


def test_when_paystack_is_down_no_payment_is_left_behind(billing: Billing) -> None:
    invoice = invoice_of(billing)
    billing.gateway.fail_initialize = GatewayError("Paystack answered 500", temporary=True)
    status, body = send(billing.ngozi, "POST", f"/school/invoices/{invoice['id']}/pay")
    assert (status, body["code"]) == (503, "payment_unavailable")
    assert "500" not in json.dumps(body)
    assert state(billing, invoice) == ("unpaid", [], 0)


def test_the_return_from_paystack_never_marks_anything_paid(billing: Billing) -> None:
    """AT-37.1, D-093: the callback page only reads."""
    invoice, reference = paying(billing)
    billing.gateway.answers[reference] = paid_at_paystack(reference, invoice["amount_kobo"])
    status, answer = send(billing.ngozi, "GET", f"/school/payments/verify?reference={reference}")
    assert status == 200
    assert answer == {
        "reference": reference,
        "status": "pending",
        "invoice_id": invoice["id"],
        "invoice_status": "unpaid",
        "receipt_number": None,
    }
    assert state(billing, invoice) == ("unpaid", ["pending"], 0)
    assert billing.gateway.verified == []


# --- the webhook ----------------------------------------------------------------------------------


def test_a_signed_webhook_and_paystacks_answer_pay_the_invoice(billing: Billing) -> None:
    """AT-37.1, F19 rule 11."""
    invoice, reference = paying(billing)
    billing.gateway.answers[reference] = paid_at_paystack(reference, invoice["amount_kobo"])
    body = webhook_body(reference)

    response = post_webhook(billing, body, signed(body))
    assert (response.status_code, response.json()) == (200, {"received": True})
    assert billing.kicks == ["run"]
    # The answer comes first; the work happens in the background run.
    assert state(billing, invoice) == ("unpaid", ["pending"], 0)
    assert billing.gateway.verified == []

    report = process(billing)
    assert (report.processed, report.failed, report.waiting) == (1, 0, 0)
    assert billing.gateway.verified == [reference]
    assert state(billing, invoice) == ("paid", ["succeeded"], 1)
    event = billing.db.execute(text("select status, processed_at, error from payment_events")).one()
    assert (event.status, event.error) == ("processed", None)
    assert event.processed_at is not None
    audit = billing.db.execute(
        text("select actor_role, new_values from audit_events where action = 'invoices.paid'")
    ).one()
    assert audit.actor_role == "system"
    assert audit.new_values["amount_kobo"] == 300_000
    assert billing.db.scalar(text("select status from school_subscriptions")) == "active"

    _, answer = send(billing.ngozi, "GET", f"/school/payments/verify?reference={reference}")
    assert answer["status"] == "succeeded" and answer["invoice_status"] == "paid"
    assert answer["receipt_number"].startswith("SF-RCPT-")
    _, paid = send(billing.ngozi, "GET", f"/school/invoices/{invoice['id']}")
    assert paid["status"] == "paid" and paid["reference"] == str(EVENT_ID)
    assert paid["paid_at"] is not None


def test_only_the_school_admins_get_the_notice_and_the_receipt_email(billing: Billing) -> None:
    """AT-37.1; emails never carry scores (they hold no report data at all)."""
    db = billing.db
    db.execute(text("update users set email = 'ngozi@gmc.example' where username = 'ngozi.okeke'"))
    make_login(
        db,
        username="ada.second",
        email="ada@gmc.example",
        school_id=billing.gmc,
        role="school_admin",
    )
    make_login(
        db,
        username="tunde.teacher",
        email="tunde@gmc.example",
        school_id=billing.gmc,
        role="teacher",
    )
    bsa = add_school(db, "BSA", "Bright Star Academy")
    make_login(
        db,
        username="other.admin",
        email="other@bsa.example",
        school_id=bsa,
        role="school_admin",
        is_primary=True,
    )
    pay_by_webhook(billing)

    notice = db.execute(
        text("select id, kind, title, body, school_id, author_id from notices")
    ).one()
    assert (notice.kind, notice.school_id, notice.author_id) == ("system", billing.gmc, None)
    assert notice.title == "First Term 2026/2027 invoice paid"
    assert "₦3,000" in notice.body and "SF-RCPT-" in notice.body
    told = set(
        db.scalars(
            text(
                "select u.username from notice_recipients r join users u on u.id = r.user_id"
                " where r.notice_id = :n"
            ),
            {"n": notice.id},
        )
    )
    assert told == {"ngozi.okeke", "ada.second"}
    assert send(billing.ngozi, "GET", "/notices/unread-count")[1]["unread"] == 1

    provider = RecordingProvider()
    db.execute(text("set local role app_sender"))
    send_due(db, provider, base_url=BASE, from_domain="notify.meritiaa.com", daily_limit=95)
    db.execute(text("reset role"))
    assert {e.to for e in provider.sent} == {"ngozi@gmc.example", "ada@gmc.example"}
    email = provider.sent[0]
    assert email.subject.startswith("Receipt SF-RCPT-")
    assert "₦3,000" in email.text and f"{BASE}/school/billing" in email.text


def test_the_receipt_email_respects_the_schools_email_switch(billing: Billing) -> None:
    billing.db.execute(
        text("update school_features set enabled = false where feature = 'email_notifications'")
    )
    pay_by_webhook(billing)
    assert billing.db.scalar(text("select count(*) from email_outbox")) == 0
    assert billing.db.scalar(text("select count(*) from notices")) == 1


@pytest.mark.parametrize("kind", ["wrong_signature", "wrong_key", "no_signature", "other_body"])
def test_a_forged_webhook_changes_and_stores_nothing(billing: Billing, kind: str) -> None:
    """AC19.6, AT-38.1."""
    invoice, reference = paying(billing)
    billing.gateway.answers[reference] = paid_at_paystack(reference, invoice["amount_kobo"])
    body = webhook_body(reference)
    headers = {
        "wrong_signature": {"x-paystack-signature": "0" * 128},
        "wrong_key": signed(body, "sk_test_someone_elses_key"),
        "no_signature": {},
        "other_body": signed(webhook_body("SF-another-reference")),
    }[kind]
    response = post_webhook(billing, body, headers)
    assert (response.status_code, response.json()["code"]) == (401, "signature_invalid")
    assert billing.kicks == [] and billing.gateway.verified == []
    assert billing.db.scalar(text("select count(*) from payment_events")) == 0
    assert process(billing).processed == 0
    assert state(billing, invoice) == ("unpaid", ["pending"], 0)


def test_with_no_secret_key_every_webhook_is_refused(billing: Billing) -> None:
    billing.app.dependency_overrides[get_webhook_secret] = lambda: None
    body = webhook_body("SF-anything")
    assert post_webhook(billing, body, signed(body, "")).status_code == 401
    assert post_webhook(billing, body, {"x-paystack-signature": ""}).status_code == 401
    # An empty key would let anyone sign: it counts as no key.
    billing.app.dependency_overrides[get_webhook_secret] = lambda: SecretStr("")
    assert post_webhook(billing, body, signed(body, "")).status_code == 401
    assert billing.db.scalar(text("select count(*) from payment_events")) == 0


def test_the_same_webhook_twice_makes_one_payment_and_one_receipt(billing: Billing) -> None:
    """AC19.7, AT-37.3."""
    invoice, reference = pay_by_webhook(billing)
    body = webhook_body(reference)
    assert post_webhook(billing, body, signed(body)).status_code == 200
    assert billing.kicks == ["run"]  # the repeat starts no run
    assert process(billing).processed == 0
    assert state(billing, invoice) == ("paid", ["succeeded"], 1)
    assert billing.gateway.verified == [reference]
    assert billing.db.scalar(text("select count(*) from payment_events")) == 1
    assert billing.db.scalar(text("select count(*) from notices")) == 1


def test_an_event_already_handled_is_not_handled_again(billing: Billing) -> None:
    """Two runs at once: the second finds the event done and leaves it alone."""
    invoice, reference = pay_by_webhook(billing)
    event = billing.db.scalar(text("select id from payment_events"))
    with as_platform(billing.db)() as db:
        assert processing.process_event(db, event, billing.gateway) == "ignored"
    assert billing.gateway.verified == [reference]
    assert billing.db.scalar(text("select status from payment_events")) == "processed"
    assert state(billing, invoice) == ("paid", ["succeeded"], 1)


def test_a_second_event_for_a_finished_payment_is_ignored(billing: Billing) -> None:
    invoice, reference = pay_by_webhook(billing)
    body = webhook_body(reference, id=EVENT_ID + 1)
    post_webhook(billing, body, signed(body))
    assert process(billing).ignored == 1
    assert state(billing, invoice) == ("paid", ["succeeded"], 1)
    assert billing.gateway.verified == [reference]


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"status": "failed"}, "Paystack says failed"),
        ({"status": "abandoned"}, "Paystack says abandoned"),
        ({"amount_kobo": 100}, "Amount does not match the invoice"),
        ({"amount_kobo": 300_001}, "Amount does not match the invoice"),
        ({"currency": "USD"}, "Currency is not NGN"),
        ({"reference": "SF-another-reference"}, "Reference does not match"),
    ],
)
def test_paystacks_own_answer_must_match(
    billing: Billing, changes: dict[str, Any], reason: str
) -> None:
    """AT-38.1, F19 rule 11: a valid signature alone is not enough."""
    invoice, reference = paying(billing)
    billing.gateway.answers[reference] = paid_at_paystack(reference, 300_000, **changes)
    body = webhook_body(reference)
    post_webhook(billing, body, signed(body))
    assert process(billing).failed == 1
    assert state(billing, invoice) == ("unpaid", ["failed"], 0)
    row = billing.db.execute(text("select failure_reason from payments")).one()
    assert row.failure_reason == reason
    assert billing.db.scalar(text("select error from payment_events")) == reason
    assert billing.db.scalar(text("select count(*) from notices")) == 0
    assert billing.db.scalar(text("select count(*) from email_outbox")) == 0
    assert "payments.rejected" in audit_actions(billing, billing.gmc)


def test_the_webhooks_own_amount_is_never_believed(billing: Billing) -> None:
    """Only Paystack's Verify answer counts, not what the event's body claims."""
    invoice, reference = paying(billing)
    billing.gateway.answers[reference] = paid_at_paystack(reference, 100)
    body = webhook_body(reference, amount=300_000)
    post_webhook(billing, body, signed(body))
    process(billing)
    assert state(billing, invoice) == ("unpaid", ["failed"], 0)


def test_an_unknown_reference_is_logged_and_changes_nothing(billing: Billing) -> None:
    """AT-38.1."""
    invoice, _ = paying(billing)
    body = webhook_body("SF-not-ours")
    post_webhook(billing, body, signed(body))
    assert process(billing).failed == 1
    assert billing.gateway.verified == []
    assert billing.db.scalar(text("select error from payment_events")) == "Unknown reference"
    assert state(billing, invoice) == ("unpaid", ["pending"], 0)


def test_other_events_are_kept_and_ignored(billing: Billing) -> None:
    invoice, reference = paying(billing)
    body = webhook_body(reference, event="charge.dispute.create")
    post_webhook(billing, body, signed(body))
    assert process(billing).ignored == 1
    assert billing.gateway.verified == []
    assert state(billing, invoice) == ("unpaid", ["pending"], 0)


@pytest.mark.parametrize("body", [b"not json", b"[1, 2]", b'"text"', b"{}"])
def test_a_signed_body_we_cannot_read_is_answered_and_not_stored(
    billing: Billing, body: bytes
) -> None:
    assert post_webhook(billing, body, signed(body)).status_code == 200
    assert billing.db.scalar(text("select count(*) from payment_events")) == 0
    assert billing.kicks == []


def test_when_paystack_cannot_answer_the_event_waits(billing: Billing) -> None:
    """D-094: the daily run tries again; nothing is lost or marked paid."""
    invoice, reference = paying(billing)
    billing.gateway.answers[reference] = GatewayError("Paystack answered 500", temporary=True)
    body = webhook_body(reference)
    post_webhook(billing, body, signed(body))
    report = process(billing)
    assert (report.processed, report.waiting) == (0, 1)
    assert state(billing, invoice) == ("unpaid", ["pending"], 0)
    event = billing.db.execute(text("select status, error, processed_at from payment_events")).one()
    assert (event.status, event.error, event.processed_at) == (
        "received",
        "Paystack answered 500",
        None,
    )

    billing.gateway.answers[reference] = paid_at_paystack(reference, invoice["amount_kobo"])
    assert payment_run(as_platform(billing.db), billing.gateway).processed == 1
    assert state(billing, invoice) == ("paid", ["succeeded"], 1)


def test_a_permanent_paystack_refusal_fails_the_payment(billing: Billing) -> None:
    invoice, reference = paying(billing)
    billing.gateway.answers[reference] = GatewayError("Paystack answered 404", temporary=False)
    body = webhook_body(reference)
    post_webhook(billing, body, signed(body))
    assert process(billing).failed == 1
    assert state(billing, invoice) == ("unpaid", ["failed"], 0)


def test_money_for_a_closed_invoice_is_flagged_for_a_refund(billing: Billing) -> None:
    """Two tries at paying: the first one wins and the second is flagged, never a second receipt."""
    invoice, first = paying(billing)
    _, second_try = send(billing.ngozi, "POST", f"/school/invoices/{invoice['id']}/pay")
    second = second_try["reference"]
    for reference, gateway_id in ((first, 1), (second, 2)):
        billing.gateway.answers[reference] = paid_at_paystack(
            reference, invoice["amount_kobo"], gateway_id=str(gateway_id)
        )
        body = webhook_body(reference, id=gateway_id)
        post_webhook(billing, body, signed(body))
    report = process(billing)
    assert (report.processed, report.failed) == (1, 1)
    assert state(billing, invoice) == ("paid", ["failed", "succeeded"], 1)
    assert "refund by hand" in billing.db.scalar(
        text("select failure_reason from payments where status = 'failed'")
    )


def test_one_bad_event_stops_no_other(billing: Billing, monkeypatch: pytest.MonkeyPatch) -> None:
    invoice, reference = paying(billing)
    billing.gateway.answers[reference] = paid_at_paystack(reference, invoice["amount_kobo"])
    for raw in (webhook_body("SF-first", id=1), webhook_body(reference, id=2)):
        post_webhook(billing, raw, signed(raw))
    real = processing.process_event
    calls: list[int] = []

    def flaky(db: Session, event_id: uuid.UUID, gateway: Any) -> str:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("something unexpected")
        return real(db, event_id, gateway)

    monkeypatch.setattr(processing, "process_event", flaky)
    report = process(billing)
    assert len(calls) == 2
    assert report.waiting == 1 and report.processed + report.failed == 1


def test_the_background_run_never_crashes(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> Any:
        raise RuntimeError("ngozi@gmc.example unreachable")

    monkeypatch.setattr(processing, "real_batches", broken)
    processing.process_soon()


def test_the_background_run_waits_for_its_settings_and_sends_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(processing.trigger, "send_soon", lambda: sent.append("emails"))
    monkeypatch.setattr(processing, "real_batches", lambda: None)
    monkeypatch.setattr(processing, "real_gateway", lambda: RecordingGateway())
    processing.process_soon()
    assert sent == []

    monkeypatch.setattr(processing, "real_batches", lambda: lambda: None)
    for processed, expected in ((0, []), (1, ["emails"])):
        report = processing.ProcessReport(processed, 0, 0, 0)

        def pending(*_: object, r: processing.ProcessReport = report) -> processing.ProcessReport:
            return r

        monkeypatch.setattr(processing, "process_pending", pending)
        processing.process_soon()
        assert sent == expected


# --- the daily run --------------------------------------------------------------------------------


def cron(b: Billing, authorization: str | None) -> Any:
    headers = {} if authorization is None else {"Authorization": authorization}
    return client_for(b.app).get("/api/v1/cron/payments", headers=headers)


def test_the_daily_run_needs_the_secret(billing: Billing) -> None:
    calls: list[str] = []
    billing.app.dependency_overrides[get_cron_secret] = lambda: SecretStr(CRON)
    billing.app.dependency_overrides[get_payment_runner] = lambda: lambda: calls.append("run")
    for authorization in (None, "", f"Bearer {CRON}x", CRON):
        response = cron(billing, authorization)
        assert (response.status_code, response.json()["code"]) == (401, "cron_refused")
    billing.app.dependency_overrides[get_cron_secret] = lambda: None
    assert cron(billing, "Bearer None").status_code == 401
    assert calls == []


def test_the_daily_run_processes_what_is_left(billing: Billing) -> None:
    invoice, reference = paying(billing)
    billing.gateway.answers[reference] = paid_at_paystack(reference, invoice["amount_kobo"])
    body = webhook_body(reference)
    post_webhook(billing, body, signed(body))
    billing.app.dependency_overrides[get_cron_secret] = lambda: SecretStr(CRON)
    billing.app.dependency_overrides[get_payment_runner] = lambda: (
        lambda: payment_run(as_platform(billing.db), billing.gateway)
    )
    response = cron(billing, f"Bearer {CRON}")
    assert response.status_code == 200
    assert response.json() == {
        "processed": 1,
        "ignored": 0,
        "failed": 0,
        "waiting": 0,
        "subscriptions_refreshed": 0,
    }
    assert response.headers["cache-control"] == "no-store"
    assert state(billing, invoice) == ("paid", ["succeeded"], 1)


def test_without_the_platform_login_the_daily_run_says_so(billing: Billing) -> None:
    billing.app.dependency_overrides[get_cron_secret] = lambda: SecretStr(CRON)
    billing.app.dependency_overrides[get_payment_runner] = lambda: None
    assert cron(billing, f"Bearer {CRON}").status_code == 503


# --- receipts -------------------------------------------------------------------------------------


def test_a_receipt_exists_only_for_a_paid_invoice(billing: Billing) -> None:
    """D-095."""
    invoice = invoice_of(billing)
    url = f"/school/invoices/{invoice['id']}/receipt"
    assert send(billing.ngozi, "GET", url)[0] == 404
    send(
        billing.owner,
        "POST",
        f"/platform/invoices/{invoice['id']}/manual-payment",
        {"reference": "BANK-1", "note": "Teller"},
    )
    status, receipt = send(billing.ngozi, "GET", url)
    assert status == 200
    assert receipt["receipt_number"].startswith("SF-RCPT-")
    assert (receipt["school_name"], receipt["term"]) == (
        "Greenfield Model College",
        "First Term 2026/2027",
    )
    assert (receipt["plan"], receipt["billable_students"], receipt["amount_kobo"]) == (
        "Basic",
        3,
        300_000,
    )
    assert receipt["reference"] == "BANK-1"


def test_the_super_admin_can_resend_a_receipt(billing: Billing) -> None:
    pay_by_webhook(billing)
    payment = billing.db.scalar(text("select id from payments"))
    before = billing.db.scalar(text("select count(*) from email_outbox"))
    assert send(billing.owner, "POST", f"/platform/payments/{payment}/resend-receipt")[0] == 204
    assert billing.db.scalar(text("select count(*) from email_outbox")) == before + 1
    assert (
        send(billing.owner, "POST", f"/platform/payments/{uuid.uuid4()}/resend-receipt")[0] == 404
    )
    assert "payments.resend_receipt" in audit_actions(billing, billing.gmc)


def test_the_receipt_page_escapes_and_reads_well() -> None:
    import datetime as dt

    html = receipt_html(
        Receipt(
            receipt_number="SF-RCPT-000123",
            school_name="<b>Greenfield</b>",
            term="First Term 2026/2027",
            plan="Standard",
            billable_students=580,
            amount_kobo=29_000_000,
            reference="T123",
            paid_at=dt.datetime(2027, 1, 5, 9, 0, tzinfo=dt.UTC),
        )
    )
    assert "&lt;b&gt;Greenfield" in html and "<b>Greenfield" not in html
    assert "₦290,000" in html and "5 Jan 2027" in html and "SF-RCPT-000123" in html


@pytest.mark.skipif(not pdf.available(), reason="WeasyPrint needs Pango (CI has it)")
def test_a_receipt_downloads_as_a_pdf(billing: Billing) -> None:
    invoice, _ = pay_by_webhook(billing)
    response = billing.ngozi.get(f"/api/v1/school/invoices/{invoice['id']}/receipt.pdf")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["cache-control"] == "private, no-store"


def test_money_and_dates_read_the_design_way() -> None:
    import datetime as dt

    assert money(32_100_000) == "₦321,000"
    assert money(100_050) == "₦1,000.50"
    assert nice_date(dt.date(2027, 1, 5)) == "5 Jan 2027"


# --- the gateway and its key ----------------------------------------------------------------------


def answering(status: int, **options: Any) -> Any:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, **options)

    return handler


def paystack(handler: Any) -> PaystackGateway:
    return PaystackGateway(SECRET, client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_paystack_gets_what_its_api_expects() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "POST":
            data = {"authorization_url": "https://checkout.paystack.com/abc", "reference": "SF-1"}
        else:
            data = {
                "status": "success",
                "amount": 300000,
                "currency": "NGN",
                "reference": "SF-1",
                "id": 99,
            }
        return httpx.Response(200, json={"status": True, "data": data})

    gateway = paystack(handler)
    url = gateway.initialize(
        email="ngozi@gmc.example", amount_kobo=300_000, reference="SF-1", callback_url=BASE + "/cb"
    )
    assert url == "https://checkout.paystack.com/abc"
    assert gateway.verify("SF-1") == Verified("success", 300_000, "NGN", "SF-1", "99")
    start, check = seen
    assert str(start.url) == "https://api.paystack.co/transaction/initialize"
    assert start.headers["authorization"] == f"Bearer {SECRET}"
    assert json.loads(start.content) == {
        "email": "ngozi@gmc.example",
        "amount": "300000",
        "currency": "NGN",
        "reference": "SF-1",
        "callback_url": BASE + "/cb",
    }
    assert str(check.url) == "https://api.paystack.co/transaction/verify/SF-1"
    assert check.headers["authorization"] == f"Bearer {SECRET}"


@pytest.mark.parametrize(
    ("status", "temporary"),
    [(500, True), (503, True), (429, True), (400, False), (401, False), (404, False)],
)
def test_paystack_failures_say_whether_to_try_again(status: int, temporary: bool) -> None:
    gateway = paystack(answering(status, json={"message": "no"}))
    with pytest.raises(GatewayError) as caught:
        gateway.verify("SF-1")
    assert caught.value.temporary is temporary
    assert SECRET not in str(caught.value)


def test_a_network_error_or_an_odd_answer_is_temporary() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(GatewayError) as caught:
        paystack(down).verify("SF-1")
    assert caught.value.temporary is True
    for odd in (
        {"status": True},
        {"data": {"status": "success"}},
        {"data": {"amount": "lots", "status": "x", "currency": "NGN", "reference": "r", "id": 1}},
    ):
        with pytest.raises(GatewayError) as caught:
            paystack(answering(200, json=odd)).verify("SF-1")
        assert caught.value.temporary is True
    with pytest.raises(GatewayError):
        paystack(answering(200, text="not json")).verify("SF-1")


def test_only_test_keys_are_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-negotiable: only test keys in the MVP."""
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("APP_BASE_URL", BASE)
    monkeypatch.setenv("APP_SECRET_KEY", "x" * 40)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/x")
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", "sk_live_fake")
    with pytest.raises(ValidationError) as caught:
        load_settings(env_file=None)
    assert "sk_live_fake" not in str(caught.value)
    monkeypatch.setenv("PAYSTACK_SECRET_KEY", SECRET)
    key = load_settings(env_file=None).paystack_secret_key
    assert key is not None and key.get_secret_value() == SECRET


@pytest.mark.parametrize("role", ["app_user", "app_verifier", "app_sender"])
def test_only_the_platform_runs_the_billing_functions(db_session: Session, role: str) -> None:
    for function in (
        "platform_billing_term(uuid)",
        "platform_term_label(uuid)",
        "platform_billing_summary()",
        "platform_post_billing_notice(uuid, text, text)",
    ):
        allowed = db_session.scalar(
            text("select has_function_privilege(:r, :f, 'execute')"), {"r": role, "f": function}
        )
        assert allowed is False, (role, function)


def test_a_school_admin_cannot_mark_a_payment_paid_directly(billing: Billing) -> None:
    """Row and column rights: a school can start a payment but never finish one."""
    _, reference = paying(billing)
    db = billing.db
    db.execute(text("savepoint before"))
    db.execute(text("set local role app_user"))
    with pytest.raises(Exception, match="permission denied"):
        db.execute(
            text("update payments set status = 'succeeded' where reference = :r"), {"r": reference}
        )
    db.execute(text("rollback to savepoint before"))
