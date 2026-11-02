"""When emails go out (SPEC F18; D-082, D-176, D-177).

Behaviour: a request that queues an email (in Python or inside a database
function, on the school's session or the platform's) starts one sender run
in the background after its transaction commits, so the email leaves within
seconds; a request that queues nothing, or fails, starts none. The run never
crashes the app and does nothing until the sender's login and the Resend key
are set. A daily cron call (GET /cron/emails, Vercel's
"Authorization: Bearer <CRON_SECRET>") sends whatever is left; without the
right secret it is refused (also when no secret is set), and without the
sender's settings it answers 503. A run sends in batches until nothing is
due, and two runs at once never go past the daily limit together: the second
one waits its turn by sending nothing. All data is fictional.
"""

import logging
import uuid
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.platform.email import trigger
from app.platform.email.provider import RecordingProvider
from app.platform.email.sender import SENDER_LOCK, SendReport, send_due
from app.src.cron.router import get_cron_secret, get_email_runner
from app.tests.auth_support import (
    ORIGIN,
    build_auth_app,
    build_platform_app,
    client_for,
    csrf,
    logged_in,
    make_login,
    use_fast_hashing,
)
from app.tests.factories import create_school, queue_email

BASE = "https://schoolflow.example"
FROM = "notify.meritiaa.com"
SECRET = "a-long-random-cron-secret-for-tests"  # noqa: S105 (fictional)


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def gmc(db_session: Session) -> uuid.UUID:
    return create_school(db_session, code="GMC", name="Greenfield Model College")


@contextmanager
def as_sender(db: Session) -> Generator[Session]:
    db.execute(text("set local role app_sender"))
    try:
        yield db
    finally:
        db.execute(text("reset role"))


def runner(db: Session, provider: RecordingProvider, limit: int = 95) -> Callable[[], SendReport]:
    """What the app runs: the whole sender, as app_sender, on the test transaction."""

    def run() -> SendReport:
        return trigger.send_all(
            lambda: as_sender(db), provider, base_url=BASE, from_domain=FROM, daily_limit=limit
        )

    return run


def with_kick(app: FastAPI, kicks: list[str], run: Callable[[], Any] | None = None) -> FastAPI:
    def kick() -> None:
        kicks.append("run")
        if run is not None:
            run()

    app.dependency_overrides[trigger.get_email_kick] = lambda: kick
    return app


def waiting_email(db: Session, school: uuid.UUID, to: str) -> uuid.UUID:
    return queue_email(
        db, school, to_address=to, email_type="password_changed", template="password_changed",
        template_data={"full_name": "Ngozi Okeke"}, priority=1,
    )  # fmt: skip


def forgot(client: TestClient, email: str) -> int:
    return client.post(
        "/api/v1/auth/password/forgot", json={"email": email}, headers={"Origin": ORIGIN}
    ).status_code


# --- right after the request -----------------------------------------------------------
def test_an_email_queued_by_a_request_goes_out_right_after_it(
    db_session: Session, gmc: uuid.UUID
) -> None:
    make_login(
        db_session, username="tunde.adebayo", email="tunde@gmc.example", school_id=gmc,
        role="teacher",
    )  # fmt: skip
    provider = RecordingProvider()
    kicks: list[str] = []
    app = with_kick(build_auth_app(db_session), kicks, runner(db_session, provider))
    # The reset email is queued inside a database function, not by queue_email().
    assert forgot(client_for(app), "tunde@gmc.example") == 202
    assert kicks == ["run"]
    assert [(e.to, e.subject) for e in provider.sent] == [
        ("tunde@gmc.example", "Reset your SchoolFlow password")
    ]
    assert db_session.scalar(text("select status from email_outbox")) == "sent"


def test_requests_that_queue_nothing_start_no_run(db_session: Session, gmc: uuid.UUID) -> None:
    make_login(
        db_session, username="tunde.adebayo", email="tunde@gmc.example", school_id=gmc,
        role="teacher",
    )  # fmt: skip
    kicks: list[str] = []
    app = with_kick(build_auth_app(db_session), kicks)
    client = logged_in(app, "tunde.adebayo")
    assert client.get("/api/v1/auth/me").status_code == 200
    # A failed request queues nothing that survives, so it starts nothing either.
    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "not my password at all", "new_password": "x" * 20},
        headers=csrf(client),
    )
    assert response.status_code >= 400
    assert kicks == []


def test_platform_emails_go_out_right_away_too(db_session: Session) -> None:
    from app.tests.domains.test_platform import school_form

    make_login(db_session, username="platform.owner", full_name="Ada Platform", is_super_admin=True)
    kicks: list[str] = []
    app = with_kick(build_platform_app(db_session), kicks)
    owner = logged_in(app, "platform.owner")
    response = owner.post("/api/v1/platform/schools", json=school_form(), headers=csrf(owner))
    assert response.status_code == 201, response.json()
    assert kicks == ["run"]


def test_the_background_run_waits_for_its_settings_and_never_crashes(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(trigger, "configured_runner", lambda: None)
    trigger.send_soon()  # nothing to do, nothing raised

    def broken() -> SendReport:
        raise RuntimeError("tunde@gmc.example could not be reached")

    monkeypatch.setattr(trigger, "configured_runner", lambda: broken)
    with caplog.at_level(logging.WARNING):
        trigger.send_soon()
    [record] = [r for r in caplog.records if r.name == "app.platform.email.trigger"]
    assert record.getMessage() == "email run failed"
    # Only the kind of error, never its text.
    assert getattr(record, "fields", None) == {"error": "RuntimeError"}
    assert "tunde@" not in caplog.text


def test_the_runner_needs_the_sender_login_and_the_resend_key() -> None:
    from app.core.config import Settings

    settings = Settings.model_construct(
        app_base_url=BASE, email_from_domain=FROM, email_daily_limit=95,
        database_url_sender=None, resend_api_key=None,
    )  # fmt: skip
    assert trigger.runner_for(settings) is None
    with_login = settings.model_copy(
        update={"database_url_sender": SecretStr("postgresql+psycopg://app_sender@db/x")}
    )
    assert trigger.runner_for(with_login) is None  # no Resend key
    with_key = settings.model_copy(update={"resend_api_key": SecretStr("re_test_key")})
    assert trigger.runner_for(with_key) is None  # no sender login


# --- a whole run -----------------------------------------------------------------------
def test_a_run_sends_in_batches_until_nothing_is_due(db_session: Session, gmc: uuid.UUID) -> None:
    for n in range(3):
        waiting_email(db_session, gmc, f"parent{n}@home.example")
    provider = RecordingProvider()
    report = trigger.send_all(
        lambda: as_sender(db_session), provider, base_url=BASE, from_domain=FROM,
        daily_limit=95, batch=2,
    )  # fmt: skip
    assert (report.sent, report.retried, report.failed, report.waiting) == (3, 0, 0, 0)
    assert len(provider.sent) == 3


def test_a_second_run_at_the_same_time_sends_nothing(
    db_engine: Engine, db_session: Session, gmc: uuid.UUID
) -> None:
    waiting_email(db_session, gmc, "parent@home.example")
    provider = RecordingProvider()
    with db_engine.connect() as other:
        # Another run holds the sender's turn in its own transaction.
        other.execute(text("select pg_advisory_xact_lock(:k)"), {"k": SENDER_LOCK})
        with as_sender(db_session):
            report = send_due(db_session, provider, base_url=BASE, from_domain=FROM, daily_limit=95)
        other.rollback()
    assert (report.sent, report.waiting) == (0, 0)
    assert provider.sent == []
    with as_sender(db_session):
        report = send_due(db_session, provider, base_url=BASE, from_domain=FROM, daily_limit=95)
    assert report.sent == 1


# --- the daily cron call ---------------------------------------------------------------
@pytest.fixture
def cron_app(db_session: Session) -> Iterator[tuple[FastAPI, RecordingProvider]]:
    app = build_auth_app(db_session)
    provider = RecordingProvider()
    app.dependency_overrides[get_cron_secret] = lambda: SecretStr(SECRET)
    app.dependency_overrides[get_email_runner] = lambda: runner(db_session, provider)
    yield app, provider


def cron(app: FastAPI, authorization: str | None) -> Any:
    headers = {} if authorization is None else {"Authorization": authorization}
    return client_for(app).get("/api/v1/cron/emails", headers=headers)


def test_the_daily_run_sends_what_is_left(
    cron_app: tuple[FastAPI, RecordingProvider], db_session: Session, gmc: uuid.UUID
) -> None:
    app, provider = cron_app
    waiting_email(db_session, gmc, "parent@home.example")
    response = cron(app, f"Bearer {SECRET}")
    assert response.status_code == 200
    assert response.json() == {"sent": 1, "retried": 0, "failed": 0, "waiting": 0}
    assert response.headers["cache-control"] == "no-store"
    assert [e.to for e in provider.sent] == ["parent@home.example"]


@pytest.mark.parametrize(
    "authorization", [None, "", f"Bearer {SECRET}x", SECRET, f"bearer {SECRET}", "Bearer "]
)
def test_the_daily_run_needs_the_secret(
    cron_app: tuple[FastAPI, RecordingProvider],
    db_session: Session,
    gmc: uuid.UUID,
    authorization: str | None,
) -> None:
    app, provider = cron_app
    waiting_email(db_session, gmc, "parent@home.example")
    response = cron(app, authorization)
    assert (response.status_code, response.json()["code"]) == (401, "cron_refused")
    assert provider.sent == []


def test_without_a_secret_set_nobody_can_start_the_run(
    cron_app: tuple[FastAPI, RecordingProvider],
) -> None:
    app, _ = cron_app
    app.dependency_overrides[get_cron_secret] = lambda: None
    for authorization in ("Bearer None", "Bearer ", "Bearer"):
        assert cron(app, authorization).status_code == 401


def test_without_the_sender_settings_the_daily_run_says_so(
    cron_app: tuple[FastAPI, RecordingProvider],
) -> None:
    app, _ = cron_app
    app.dependency_overrides[get_email_runner] = lambda: None
    response = cron(app, f"Bearer {SECRET}")
    assert (response.status_code, response.json()["code"]) == (503, "email_not_set_up")
