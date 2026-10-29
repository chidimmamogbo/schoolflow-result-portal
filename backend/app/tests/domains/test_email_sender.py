"""The email sender (BUILD_PROMPT 9.2; SPEC F18; D-078 to D-083, D-153, D-176).

Behaviour: the sender, logged in as app_sender, sends the queued emails in
order (priority, then oldest), at most the daily limit counted across the
day, through the EmailProvider. Activation and reset emails carry a fresh
link made at that moment: only its hash is stored, it cancels the account's
older link of that kind, and the link works (72 hours, or 1 hour for a
reset). School emails come from the school's name with the school's email as
Reply-To; platform emails from "SchoolFlow". A link request is written for
who the address belongs to. Temporary failures retry after 1 min, 5 min,
30 min, 2 h and 12 h, then the email is Failed; a permanent failure fails at
once; error notes never keep an address. Emails never carry scores. The
Resend provider sends exactly what Resend's API expects. All data is
fictional.
"""

import datetime as dt
import json
import re
import secrets
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import token_hash
from app.platform.email.provider import (
    OutgoingEmail,
    RecordingProvider,
    ResendProvider,
    SendError,
)
from app.platform.email.sender import RETRY_GAPS, send_due
from app.tests.auth_support import (
    ORIGIN,
    PASSWORD,
    build_auth_app,
    client_for,
    make_login,
    use_fast_hashing,
)
from app.tests.factories import create_school, queue_email

BASE = "https://schoolflow.example"
FROM = "notify.meritiaa.com"


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    return build_auth_app(db_session)


@pytest.fixture
def gmc(db_session: Session) -> uuid.UUID:
    return create_school(db_session, code="GMC", name="Greenfield Model College")


@contextmanager
def as_sender(db: Session) -> Generator[None]:
    """The sender's own database login, on the rolled-back test transaction."""
    db.execute(text("set local role app_sender"))
    try:
        yield
    finally:
        db.execute(text("reset role"))


def run(db: Session, provider: RecordingProvider, limit: int = 95) -> Any:
    with as_sender(db):
        return send_due(db, provider, base_url=BASE, from_domain=FROM, daily_limit=limit)


def outbox(db: Session, email_id: uuid.UUID) -> Any:
    return db.execute(
        text(
            "select status, attempts, next_attempt_at, last_error, provider_message_id, sent_at"
            " from email_outbox where id = :id"
        ),
        {"id": email_id},
    ).one()


def link_in(email: OutgoingEmail, path: str) -> str:
    match = re.search(rf"{re.escape(BASE)}{re.escape(path)}#token=([A-Za-z0-9_-]+)", email.text)
    assert match, email.text
    assert match.group(0) in email.html
    return match.group(1)


def activation(db: Session, school: uuid.UUID | None, user: uuid.UUID, to: str) -> uuid.UUID:
    data = {"user_id": str(user), "full_name": "Ngozi Okeke", "username": "ngozi.okeke"}
    if school is not None:
        data |= {"school_code": "GMC", "school_name": "Greenfield Model College"}
    return queue_email(
        db, school, to_address=to, email_type="activation", template="activation",
        template_data=data, priority=1,
    )  # fmt: skip


def test_an_activation_email_carries_a_fresh_working_link(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    ngozi = make_login(
        db_session, username="ngozi.okeke", email="ngozi@gmc.example", school_id=gmc,
        role="school_admin", is_primary=True, password=None,
    )  # fmt: skip
    first = activation(db_session, gmc, ngozi, "ngozi@gmc.example")
    provider = RecordingProvider()
    report = run(db_session, provider)
    assert (report.sent, report.retried, report.failed, report.waiting) == (1, 0, 0, 0)

    [email] = provider.sent
    assert email.sender == f"Greenfield Model College <no-reply@{FROM}>"
    assert (email.to, email.reply_to) == ("ngozi@gmc.example", "office@gmc.example")
    assert email.subject == "Set up your Greenfield Model College account"
    assert "ngozi.okeke" in email.text and "GMC" in email.text
    token = link_in(email, "/activate")
    row = outbox(db_session, first)
    assert (row.status, row.attempts, row.provider_message_id) == ("sent", 1, "msg-1")
    assert row.sent_at is not None
    assert email.idempotency_key.endswith(":1")

    # Only the hash is kept; the outbox never holds the link.
    stored = db_session.scalar(
        text("select token_hash from account_tokens where user_id = :u and cancelled_at is null"),
        {"u": ngozi},
    )
    assert stored == token_hash(token)
    data = db_session.scalar(
        text("select template_data::text from email_outbox where id = :id"), {"id": first}
    )
    assert token not in data

    # A resend cancels the first link; the newest one works.
    activation(db_session, gmc, ngozi, "ngozi@gmc.example")
    run(db_session, provider)
    newest = link_in(provider.sent[-1], "/activate")
    client = client_for(app)
    old = client.post(
        "/api/v1/auth/activate",
        json={"token": token, "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert old.status_code == 400
    new = client.post(
        "/api/v1/auth/activate",
        json={"token": newest, "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert new.status_code == 200


def test_reset_links_last_an_hour(db_session: Session, gmc: uuid.UUID) -> None:
    amina = make_login(db_session, username="amina.bello", email="amina@gmc.example", school_id=gmc)
    queue_email(
        db_session, gmc, to_address="amina@gmc.example", email_type="password_reset",
        template="password_reset",
        template_data={"user_id": str(amina), "full_name": "Amina Bello"},
        priority=1,
    )  # fmt: skip
    provider = RecordingProvider()
    run(db_session, provider)
    [email] = provider.sent
    assert email.subject == "Reset your SchoolFlow password"
    link_in(email, "/reset-password")
    left = db_session.scalar(
        text(
            "select expires_at - now() from account_tokens where user_id = :u and purpose = 'reset'"
        ),
        {"u": amina},
    )
    assert dt.timedelta(minutes=59) < left <= dt.timedelta(hours=1)


def test_order_and_the_daily_limit(db_session: Session, gmc: uuid.UUID) -> None:
    bulk = [
        queue_email(db_session, gmc, to_address=f"parent{i}@home.example", priority=5,
                    template_data=results_data())
        for i in range(3)
    ]  # fmt: skip
    urgent = queue_email(
        db_session, gmc, to_address="admin@gmc.example", email_type="password_changed",
        template="password_changed", template_data={"full_name": "Ngozi Okeke"}, priority=1,
    )  # fmt: skip
    provider = RecordingProvider()
    report = run(db_session, provider, limit=2)
    assert (report.sent, report.waiting) == (2, 2)
    # Priority first; emails queued in one test transaction share a time, so any bulk one next.
    assert provider.sent[0].to == "admin@gmc.example"
    assert provider.sent[1].to.startswith("parent")
    assert outbox(db_session, urgent).status == "sent"
    assert sorted(outbox(db_session, e).status for e in bulk) == ["queued", "queued", "sent"]
    # The limit counts the whole day: one more today, then nothing.
    assert run(db_session, provider, limit=3).sent == 1
    assert run(db_session, provider, limit=3).sent == 0


def results_data() -> dict[str, Any]:
    return {
        "full_name": "Ikenna Obi", "school_name": "Greenfield Model College",
        "class_name": "JSS 1A", "term_name": "First Term", "session_name": "2026/2027",
        "updated": False, "login_path": "/login",
    }  # fmt: skip


def test_results_emails_say_where_to_look_never_the_scores(
    db_session: Session, gmc: uuid.UUID
) -> None:
    queue_email(db_session, gmc, to_address="ikenna@home.example", template_data=results_data())
    provider = RecordingProvider()
    run(db_session, provider)
    [email] = provider.sent
    assert email.subject == "First Term results for JSS 1A are ready"
    assert f"{BASE}/login" in email.text and "2026/2027" in email.text
    assert not re.search(r"\b\d{2}\b(?!/)", email.text.replace("2026/2027", ""))


def test_temporary_failures_retry_then_the_email_fails(db_session: Session, gmc: uuid.UUID) -> None:
    email_id = queue_email(
        db_session, gmc, to_address="ikenna@home.example", template_data=results_data()
    )
    provider = RecordingProvider(
        failures=[SendError("Resend said 500 for ikenna@home.example", temporary=True)] * 5
    )
    for attempt, gap in enumerate(RETRY_GAPS, start=1):
        report = run(db_session, provider)
        row = outbox(db_session, email_id)
        assert row.attempts == attempt
        if attempt < 5:
            assert (report.retried, row.status) == (1, "queued")
            waited = row.next_attempt_at - db_session.scalar(text("select now()"))
            assert abs(waited - gap) < dt.timedelta(seconds=5)
            assert run(db_session, provider).sent == 0  # not due yet
            db_session.execute(
                text("update email_outbox set next_attempt_at = now() where id = :id"),
                {"id": email_id},
            )
        else:
            assert (report.failed, row.status) == (1, "failed")
        assert "@" not in (row.last_error or "") and "[address]" in row.last_error


def test_a_permanent_failure_fails_at_once(db_session: Session, gmc: uuid.UUID) -> None:
    email_id = queue_email(
        db_session, gmc, to_address="bad@home.example", template_data=results_data()
    )
    provider = RecordingProvider(failures=[SendError("422 invalid to", temporary=False)])
    assert run(db_session, provider).failed == 1
    row = outbox(db_session, email_id)
    assert (row.status, row.attempts, row.last_error) == ("failed", 1, "422 invalid to")


def link_request(db: Session, school: uuid.UUID, to: str) -> uuid.UUID:
    guardian = db.scalar(
        text("insert into guardians (school_id, full_name) values (:s, 'Ikenna Obi') returning id"),
        {"s": school},
    )
    request_id: uuid.UUID = db.scalar(
        text(
            "insert into parent_link_requests"
            " (school_id, guardian_id, email, token_hash, expires_at)"
            " values (:s, :g, :e, :h, now() + interval '14 days') returning id"
        ),
        {"s": school, "g": guardian, "e": to, "h": secrets.token_bytes(32)},
    )
    queue_email(
        db, school, to_address=to, email_type="parent_link_request", template="parent_link_request",
        template_data={"link_request_id": str(request_id),
                       "school_name": "Greenfield Model College",
                       "guardian_name": "Ikenna Obi"},
    )  # fmt: skip
    return request_id


def test_link_requests_are_written_for_whoever_owns_the_address(
    db_session: Session, gmc: uuid.UUID
) -> None:
    bsa = create_school(db_session, code="BSA", name="Bright Star Academy")
    make_login(
        db_session, username="ikenna.obi", email="ikenna@home.example", school_id=bsa, role="parent"
    )
    make_login(
        db_session,
        username="tunde.adebayo",
        email="tunde@gmc.example",
        school_id=gmc,
        role="teacher",
    )
    db_session.execute(text("select set_config('app.school_id', :s, true)"), {"s": str(gmc)})
    to_parent = link_request(db_session, gmc, "ikenna@home.example")
    to_staff = link_request(db_session, gmc, "tunde@gmc.example")
    to_nobody = link_request(db_session, gmc, "new.parent@home.example")
    placeholders = {
        r.id: r.token_hash
        for r in db_session.execute(text("select id, token_hash from parent_link_requests"))
    }
    provider = RecordingProvider()
    run(db_session, provider)
    by_address = {e.to: e for e in provider.sent}

    parent = by_address["ikenna@home.example"]
    assert "log in" in parent.text.lower() and f"{BASE}/login" in parent.text
    assert "#token=" not in parent.text
    staff = by_address["tunde@gmc.example"]
    assert "another email" in staff.text and "#token=" not in staff.text
    nobody = by_address["new.parent@home.example"]
    token = link_in(nobody, "/join")
    hashes = {
        r.id: r.token_hash
        for r in db_session.execute(text("select id, token_hash from parent_link_requests"))
    }
    assert hashes[to_nobody] == token_hash(token)
    assert hashes[to_parent] == placeholders[to_parent]  # no link is made for them
    assert hashes[to_staff] == placeholders[to_staff]


def test_platform_emails_come_from_schoolflow(db_session: Session, gmc: uuid.UUID) -> None:
    # A school exists, so a platform email must not pick up its name by mistake.
    assert gmc is not None
    owner = make_login(
        db_session,
        username="platform.owner",
        email="owner@schoolflow.example",
        is_super_admin=True,
        password=None,
    )
    activation(db_session, None, owner, "owner@schoolflow.example")
    provider = RecordingProvider()
    run(db_session, provider)
    [email] = provider.sent
    assert (email.sender, email.reply_to) == (f"SchoolFlow <no-reply@{FROM}>", None)
    assert email.subject == "Set up your SchoolFlow account"


def test_only_the_sender_prepares_emails(db_session: Session) -> None:
    for role in ("app_user", "app_platform", "app_verifier"):
        allowed = db_session.scalar(
            text("select has_function_privilege(:r, 'email_prepare(uuid, bytea)', 'EXECUTE')"),
            {"r": role},
        )
        assert allowed is False, role


# --- the Resend provider -----------------------------------------------------------------------

EMAIL = OutgoingEmail(
    sender="Greenfield Model College <no-reply@notify.meritiaa.com>",
    to="ikenna@home.example",
    subject="First Term results for JSS 1A are ready",
    html="<p>Hello</p>",
    text="Hello",
    reply_to="office@gmc.example",
    idempotency_key="results_published:abc:1",
)


def provider_with(handler: Any) -> ResendProvider:
    return ResendProvider(
        "re_test_not_a_real_key", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_resend_gets_what_its_api_expects() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "49a3999c-0ce1-4ea6-ab68-afcd6dc2e794"})

    assert provider_with(handler).send(EMAIL) == "49a3999c-0ce1-4ea6-ab68-afcd6dc2e794"
    [request] = seen
    assert (request.method, str(request.url)) == ("POST", "https://api.resend.com/emails")
    assert request.headers["authorization"] == "Bearer re_test_not_a_real_key"
    assert request.headers["idempotency-key"] == "results_published:abc:1"
    assert json.loads(request.content) == {
        "from": EMAIL.sender,
        "to": ["ikenna@home.example"],
        "subject": EMAIL.subject,
        "html": "<p>Hello</p>",
        "text": "Hello",
        "reply_to": "office@gmc.example",
    }


@pytest.mark.parametrize(
    ("status", "temporary"),
    [(429, True), (500, True), (503, True), (422, False), (401, False), (409, False)],
)
def test_resend_failures_say_whether_to_retry(status: int, temporary: bool) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"message": "no", "name": "x"})

    provider = provider_with(handler)
    with pytest.raises(SendError) as failure:
        provider.send(EMAIL)
    assert failure.value.temporary is temporary
    assert str(status) in str(failure.value) and "re_test" not in str(failure.value)


def test_a_network_error_is_temporary() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    with pytest.raises(SendError) as failure:
        provider_with(handler).send(EMAIL)
    assert failure.value.temporary is True
