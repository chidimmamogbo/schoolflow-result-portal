"""Login, sessions and passwords (BUILD_PROMPT 9.2b; SPEC F02; D-033 to D-042).

Behaviour: staff and parents log in with email or username, students with
their school code and username or admission number; every failure (wrong
code, name or password, deactivated, not activated, expired temporary
password, throttled) gives one identical answer after one password check;
a paused school is mentioned only after a correct password; sessions are an
opaque HttpOnly cookie whose hash alone is stored, ending when idle or old,
on logout, on logout-all and on deactivation; every state change needs the
CSRF token and our own Origin; a temporary password allows only me, change
password and logout; links are single use, expiring and kept when the new
password is refused; forgot password answers the same for everyone and
queues an email only for a verified, active, non-student account; there is
no register route. Requests run as app_user. All data is fictional.
"""

import hashlib
import hmac
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.auth import passwords, throttle
from schoolflow_api.auth.passwords import MIN_LENGTH, MIN_LENGTH_STUDENT, is_common
from schoolflow_api.auth.tokens import CSRF_COOKIE, SESSION_COOKIE, token_hash
from schoolflow_api.db import use_context
from schoolflow_api.files.storage import LocalFileStorage, get_file_storage
from schoolflow_api.settings import get_settings
from tests.auth_support import (
    ORIGIN,
    PASSWORD,
    STUDENT_PASSWORD,
    build_auth_app,
    client_for,
    csrf,
    log_in,
    logged_in,
    make_link,
    make_login,
    use_fast_hashing,
)
from tests.db_support import acting_as, refused
from tests.factories import create_school, create_student, post_notice

LOGIN_FAILED = "That login didn't work. Check your details and try again."
SCHOOL_PAUSED = "Your school's access is paused. Contact your school admin."


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    return build_auth_app(db_session)


@pytest.fixture
def gmc(db_session: Session) -> uuid.UUID:
    return create_school(db_session, code="GMC", name="Greenfield Model College")


@pytest.fixture
def bsa(db_session: Session) -> uuid.UUID:
    return create_school(db_session, code="BSA", name="Bright Stars Academy")


@pytest.fixture
def tunde(db_session: Session, gmc: uuid.UUID) -> uuid.UUID:
    return make_login(
        db_session, username="tunde.adebayo", email="tunde@gmc.example", school_id=gmc
    )


def problem(client: TestClient, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    response = client.request(method, url, **kwargs)
    body: dict[str, Any] = response.json()
    body.pop("request_id", None)
    body["_status"] = response.status_code
    return body


def count_sessions(db_session: Session, user_id: uuid.UUID) -> int:
    return int(
        db_session.scalar(
            text("select count(*) from user_sessions where user_id = :id"), {"id": user_id}
        )
        or 0
    )


# --- logging in -----------------------------------------------------------------


def test_staff_log_in_with_username_or_email(app: FastAPI, tunde: uuid.UUID) -> None:
    """AT-09.1, AC02.5."""
    for identifier in ("tunde.adebayo", "Tunde@GMC.example"):
        client = client_for(app)
        assert log_in(client, identifier) == 200
        assert client.get("/api/v1/auth/me").json()["user"]["username"] == "tunde.adebayo"


def test_the_cookies_are_set_safely(app: FastAPI, tunde: uuid.UUID) -> None:
    """D-037, D-038: __Host- cookies, HttpOnly session, script-readable CSRF token."""
    client = client_for(app)
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": "tunde.adebayo", "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert response.json() == {"must_change_password": False}
    cookies = response.headers.get_list("set-cookie")
    session = next(c for c in cookies if c.startswith(f"{SESSION_COOKIE}="))
    token = next(c for c in cookies if c.startswith(f"{CSRF_COOKIE}="))
    for cookie in (session, token):
        lowered = cookie.lower()
        assert "secure" in lowered
        assert "path=/" in lowered
        assert "samesite=lax" in lowered
        assert "domain=" not in lowered
    assert "httponly" in session.lower()
    assert "httponly" not in token.lower()


def test_only_the_session_hash_is_stored(
    app: FastAPI, db_session: Session, tunde: uuid.UUID
) -> None:
    """D-037: a stolen database copy holds no usable session token."""
    client = logged_in(app, "tunde.adebayo")
    token = client.cookies.get(SESSION_COOKIE) or ""
    assert len(token) >= 43  # 32 random bytes, base64url
    stored = db_session.scalar(
        text("select token_hash from user_sessions where user_id = :id"), {"id": tunde}
    )
    secret = get_settings().app_secret_key.get_secret_value().encode()
    assert stored == hmac.new(secret, token.encode(), hashlib.sha256).digest()
    assert token.encode() not in bytes(stored)


def test_student_logs_in_with_school_code_and_admission_number(
    app: FastAPI, db_session: Session, gmc: uuid.UUID, bsa: uuid.UUID
) -> None:
    """AT-09.2, AT-09.3, AC02.6: the same admission number in two schools never mixes."""
    for school_id, username in ((gmc, "chukwuemeka.obi"), (bsa, "amaka.eze")):
        user_id = make_login(
            db_session,
            username=username,
            school_id=school_id,
            student=True,
            password=STUDENT_PASSWORD,
        )
        create_student(db_session, school_id, "2026/014", "Obi", "Pupil", user_id=user_id)

    client = logged_in(app, "2026/014", STUDENT_PASSWORD, school_code="gmc")
    assert client.get("/api/v1/auth/me").json()["user"]["username"] == "chukwuemeka.obi"
    client = logged_in(app, "amaka.eze", STUDENT_PASSWORD, school_code="BSA")
    assert client.get("/api/v1/auth/me").json()["user"]["username"] == "amaka.eze"
    # The other school's password does not open Greenfield's pupil.
    assert log_in(client_for(app), "amaka.eze", STUDENT_PASSWORD, school_code="GMC") == 401


def test_each_tab_finds_only_its_own_accounts(
    app: FastAPI, db_session: Session, gmc: uuid.UUID, tunde: uuid.UUID
) -> None:
    """D-033: student usernames need the school code; staff never log in with one."""
    make_login(db_session, username="ada.nwosu", school_id=gmc, student=True)
    assert log_in(client_for(app), "ada.nwosu") == 401
    assert log_in(client_for(app), "tunde.adebayo", school_code="GMC") == 401
    assert log_in(client_for(app), "ada.nwosu", school_code="GMC") == 200


def test_every_login_failure_looks_the_same(
    app: FastAPI,
    db_session: Session,
    gmc: uuid.UUID,
    tunde: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AT-09.4, AC02.7, AC03.3, D-034: one answer, one password check, whatever was wrong."""
    pupil = make_login(db_session, username="ada.nwosu", school_id=gmc, student=True)
    create_student(db_session, gmc, "GMC/2026/014", "Nwosu", "Ada", user_id=pupil)
    gone = make_login(db_session, username="old.teacher", school_id=gmc)
    db_session.execute(text("update users set is_active = false where id = :id"), {"id": gone})
    make_login(db_session, username="new.teacher", school_id=gmc, password=None)
    stale = make_login(db_session, username="slip.teacher", school_id=gmc, temporary=True)
    db_session.execute(
        text(
            "update users set temp_password_expires_at = now() - interval '1 minute' where id = :id"
        ),
        {"id": stale},
    )

    # Count real Argon2 checks inside the hasher, not calls to our own function.
    checks: list[int] = []
    hasher = passwords.PASSWORD_HASH

    class CountingHash:
        def hash(self, password: str) -> str:
            return hasher.hash(password)

        def verify(self, password: str, stored: str) -> bool:
            checks.append(1)
            return hasher.verify(password, stored)

        def verify_and_update(self, password: str, stored: str) -> tuple[bool, str | None]:
            checks.append(1)
            return hasher.verify_and_update(password, stored)

    monkeypatch.setattr(passwords, "PASSWORD_HASH", CountingHash())

    attempts = [
        {"identifier": "GMC/2026/014", "password": PASSWORD, "school_code": "XYZ"},
        {"identifier": "GMC/2026/099", "password": PASSWORD, "school_code": "GMC"},
        {"identifier": "GMC/2026/014", "password": "wrong-password-here", "school_code": "GMC"},
        {"identifier": "nobody.here", "password": PASSWORD},
        {"identifier": "tunde.adebayo", "password": "wrong-password-here"},
        {"identifier": "old.teacher", "password": PASSWORD},
        {"identifier": "new.teacher", "password": PASSWORD},
        {"identifier": "slip.teacher", "password": PASSWORD},
    ]
    answers: list[dict[str, Any]] = []
    for attempt in attempts:
        client = client_for(app)
        before = len(checks)
        answers.append(
            problem(client, "POST", "/api/v1/auth/login", json=attempt, headers={"Origin": ORIGIN})
        )
        assert len(checks) - before == 1, attempt
        assert SESSION_COOKIE not in client.cookies

    assert all(answer == answers[0] for answer in answers), answers
    assert answers[0]["_status"] == 401
    assert answers[0]["title"] == LOGIN_FAILED
    assert answers[0]["code"] == "login_failed"


def test_a_paused_school_is_named_only_after_a_correct_password(
    app: FastAPI, db_session: Session, gmc: uuid.UUID, tunde: uuid.UUID
) -> None:
    """AT-X.2, D-034."""
    db_session.execute(text("update schools set status = 'suspended' where id = :id"), {"id": gmc})
    wrong = problem(
        client_for(app),
        "POST",
        "/api/v1/auth/login",
        json={"identifier": "tunde.adebayo", "password": "wrong-password-here"},
        headers={"Origin": ORIGIN},
    )
    assert wrong["title"] == LOGIN_FAILED

    client = client_for(app)
    right = problem(
        client,
        "POST",
        "/api/v1/auth/login",
        json={"identifier": "tunde.adebayo", "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert right["_status"] == 403
    assert right["code"] == "school_paused"
    assert right["title"] == SCHOOL_PAUSED
    assert SESSION_COOKIE not in client.cookies
    assert count_sessions(db_session, tunde) == 0


def test_a_paused_membership_cannot_log_in_or_use_a_session(
    app: FastAPI, db_session: Session, gmc: uuid.UUID, tunde: uuid.UUID
) -> None:
    client = logged_in(app, "tunde.adebayo")
    db_session.execute(
        text("update school_memberships set status = 'paused' where user_id = :id"), {"id": tunde}
    )
    assert client.get("/api/v1/auth/me").json()["code"] == "school_paused"
    assert log_in(client_for(app), "tunde.adebayo") == 403


def test_repeated_failures_are_throttled_even_with_the_right_password(
    app: FastAPI, db_session: Session, tunde: uuid.UUID
) -> None:
    """AT-09.5, AC02.4, D-042: growing delays after 5 failures, no permanent lockout."""
    for _ in range(throttle.FREE_FAILURES):
        assert log_in(client_for(app), "tunde.adebayo", "wrong-password-here") == 401
    # Locked for 30 seconds: the right password gets the same generic answer.
    client = client_for(app)
    assert log_in(client, "tunde.adebayo") == 401
    assert SESSION_COOKIE not in client.cookies
    # The email names the same account, so it is locked too.
    assert log_in(client_for(app), "tunde@gmc.example") == 401

    # The wait is over: the right password works and the count starts again.
    db_session.execute(text("update login_throttles set locked_until = now() - interval '1 s'"))
    assert log_in(client_for(app), "tunde.adebayo") == 200
    assert db_session.scalar(text("select count(*) from login_throttles")) == 0


def test_the_delays_grow_and_stop_at_fifteen_minutes() -> None:
    assert [throttle.delay_after(n) for n in range(1, 11)] == [
        0,
        0,
        0,
        0,
        30,
        60,
        300,
        900,
        900,
        900,
    ]


def test_logins_from_another_site_are_refused(app: FastAPI, tunde: uuid.UUID) -> None:
    """D-038: the Origin check stops login forgery from another site."""
    response = client_for(app).post(
        "/api/v1/auth/login",
        json={"identifier": "tunde.adebayo", "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"


def test_login_refuses_extra_fields(app: FastAPI, tunde: uuid.UUID) -> None:
    response = client_for(app).post(
        "/api/v1/auth/login",
        json={"identifier": "tunde.adebayo", "password": PASSWORD, "role": "super_admin"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 422


def test_there_is_no_register_route(app: FastAPI) -> None:
    """AT-05.1, AC02.1."""
    client = client_for(app)
    for path in ("/api/v1/auth/register", "/api/v1/auth/signup", "/register", "/signup"):
        for method in ("GET", "POST"):
            response = client.request(method, path, headers={"Origin": ORIGIN})
            assert response.status_code in {404, 405}, (method, path)
            assert response.status_code == 404 or method == "GET", (method, path)


# --- sessions -------------------------------------------------------------------


def test_no_session_or_a_forged_one_is_refused(app: FastAPI, tunde: uuid.UUID) -> None:
    client = client_for(app)
    assert problem(client, "GET", "/api/v1/auth/me")["code"] == "not_signed_in"
    client.cookies.set(SESSION_COOKIE, "made-up-token-made-up-token-made-up-token-123")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_ends_only_this_session(app: FastAPI, db_session: Session, tunde: uuid.UUID) -> None:
    phone = logged_in(app, "tunde.adebayo")
    laptop = logged_in(app, "tunde.adebayo")
    response = phone.post("/api/v1/auth/logout", headers=csrf(phone))
    assert response.status_code == 204
    assert phone.get("/api/v1/auth/me").status_code == 401
    assert laptop.get("/api/v1/auth/me").status_code == 200
    assert count_sessions(db_session, tunde) == 1


def test_logout_all_ends_every_session(app: FastAPI, db_session: Session, tunde: uuid.UUID) -> None:
    phone = logged_in(app, "tunde.adebayo")
    laptop = logged_in(app, "tunde.adebayo")
    assert laptop.post("/api/v1/auth/logout-all", headers=csrf(laptop)).status_code == 204
    assert phone.get("/api/v1/auth/me").status_code == 401
    assert laptop.get("/api/v1/auth/me").status_code == 401
    assert count_sessions(db_session, tunde) == 0


def test_refresh_swaps_the_token(app: FastAPI, tunde: uuid.UUID) -> None:
    """D-037: rotation; the old token stops working at once."""
    client = logged_in(app, "tunde.adebayo")
    old = client.cookies.get(SESSION_COOKIE) or ""
    assert client.post("/api/v1/auth/refresh", headers=csrf(client)).status_code == 200
    new = client.cookies.get(SESSION_COOKIE) or ""
    assert new and new != old
    assert client.get("/api/v1/auth/me").status_code == 200
    stale = client_for(app)
    stale.cookies.set(SESSION_COOKIE, old)
    assert stale.get("/api/v1/auth/me").status_code == 401


def test_sessions_end_when_idle_or_too_old(
    app: FastAPI, db_session: Session, tunde: uuid.UUID
) -> None:
    """D-037: 12 hours idle and 7 days in all for school users."""
    client = logged_in(app, "tunde.adebayo")
    db_session.execute(text("update user_sessions set last_seen_at = now() - interval '11 hours'"))
    assert client.get("/api/v1/auth/me").status_code == 200
    db_session.execute(text("update user_sessions set last_seen_at = now() - interval '13 hours'"))
    assert client.get("/api/v1/auth/me").status_code == 401

    client = logged_in(app, "tunde.adebayo")
    db_session.execute(
        text(
            "update user_sessions set created_at = now() - interval '8 days',"
            " expires_at = now() - interval '1 minute'"
        )
    )
    assert client.get("/api/v1/auth/me").status_code == 401


def test_super_admin_sessions_are_shorter(app: FastAPI, db_session: Session) -> None:
    """D-037: 1 hour idle and 12 hours in all for the super admin."""
    make_login(db_session, username="platform.owner", is_super_admin=True)
    client = logged_in(app, "platform.owner")
    expires_in = db_session.scalar(
        text("select extract(epoch from expires_at - created_at) from user_sessions")
    )
    assert float(expires_in) == 12 * 3600
    db_session.execute(
        text("update user_sessions set last_seen_at = now() - interval '61 minutes'")
    )
    assert client.get("/api/v1/auth/me").status_code == 401


def test_deactivation_ends_access_at_once(
    app: FastAPI, db_session: Session, tunde: uuid.UUID
) -> None:
    """AC03.3."""
    client = logged_in(app, "tunde.adebayo")
    db_session.execute(text("update users set is_active = false where id = :id"), {"id": tunde})
    assert client.get("/api/v1/auth/me").status_code == 401


def test_state_changes_need_the_csrf_token(app: FastAPI, tunde: uuid.UUID) -> None:
    """D-038: double-submit token tied to the session, plus the Origin check."""
    client = logged_in(app, "tunde.adebayo")
    url = "/api/v1/auth/logout"
    assert problem(client, "POST", url)["code"] == "csrf_failed"
    assert client.post(url, headers={"X-CSRF-Token": "guess"}).status_code == 403
    other = logged_in(app, "tunde.adebayo")
    assert (
        client.post(url, headers={"X-CSRF-Token": csrf(other)["X-CSRF-Token"]}).status_code == 403
    )
    headers = {**csrf(client), "Origin": "https://evil.example"}
    assert client.post(url, headers=headers).status_code == 403
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post(url, headers=csrf(client)).status_code == 204


# --- temporary passwords and changing a password -------------------------------------


def test_a_temporary_password_must_be_changed_first(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    """AT-09.2, AC02.2, D-040: only me, change password and logout until it is changed."""
    make_login(
        db_session,
        username="chukwuemeka.obi",
        school_id=gmc,
        student=True,
        password="temp-slip-words-four",  # noqa: S106 (fictional)
        temporary=True,
    )
    client = client_for(app)
    response = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": "chukwuemeka.obi",
            "password": "temp-slip-words-four",
            "school_code": "GMC",
        },
        headers={"Origin": ORIGIN},
    )
    assert response.json() == {"must_change_password": True}
    assert client.get("/api/v1/auth/me").json()["must_change_password"] is True
    assert problem(client, "POST", "/api/v1/auth/refresh", headers=csrf(client))["code"] == (
        "password_change_required"
    )

    same = {"current_password": "temp-slip-words-four", "new_password": "temp-slip-words-four"}
    assert (
        problem(client, "POST", "/api/v1/auth/change-password", json=same, headers=csrf(client))[
            "code"
        ]
        == "password_unchanged"
    )
    short = {"current_password": "temp-slip-words-four", "new_password": "x" * 9}
    assert (
        problem(client, "POST", "/api/v1/auth/change-password", json=short, headers=csrf(client))[
            "code"
        ]
        == "password_too_short"
    )
    new = {"current_password": "temp-slip-words-four", "new_password": "x9-yam-pod-k"}
    response = client.post("/api/v1/auth/change-password", json=new, headers=csrf(client))
    assert response.status_code == 204
    me = client.get("/api/v1/auth/me").json()
    assert me["must_change_password"] is False
    assert client.post("/api/v1/auth/refresh", headers=csrf(client)).status_code == 200
    user = db_session.execute(
        text(
            "select must_change_password, temp_password_expires_at from users"
            " where username = 'chukwuemeka.obi'"
        )
    ).one()
    assert tuple(user) == (False, None)


def test_password_rules(app: FastAPI, tunde: uuid.UUID) -> None:
    """D-036: 15 characters for staff and parents, never a common password."""
    assert (MIN_LENGTH, MIN_LENGTH_STUDENT) == (15, 10)
    assert is_common("Password1234567")
    assert not is_common(PASSWORD)
    client = logged_in(app, "tunde.adebayo")
    url = "/api/v1/auth/change-password"

    def change(current: str, new: str) -> dict[str, Any]:
        return problem(
            client,
            "POST",
            url,
            json={"current_password": current, "new_password": new},
            headers=csrf(client),
        )

    assert change(PASSWORD, "y" * 14)["code"] == "password_too_short"
    assert change(PASSWORD, "password1234567")["code"] == "password_too_common"
    assert change(PASSWORD, "y" * 129)["code"] == "password_too_long"
    wrong = change("not-my-password-at-all", "a-fresh-long-passphrase")
    assert (wrong["_status"], wrong["code"]) == (400, "current_password_wrong")
    done = client.post(
        url,
        json={"current_password": PASSWORD, "new_password": "a-fresh-long-passphrase"},
        headers=csrf(client),
    )
    assert done.status_code == 204


def test_changing_the_password_ends_other_sessions_and_sends_a_notice(
    app: FastAPI, db_session: Session, tunde: uuid.UUID
) -> None:
    """D-037 rotation, D-041: other sessions end; a 'password changed' email is queued."""
    other = logged_in(app, "tunde.adebayo")
    client = logged_in(app, "tunde.adebayo")
    old = client.cookies.get(SESSION_COOKIE)
    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "a-fresh-long-passphrase"},
        headers=csrf(client),
    )
    assert response.status_code == 204
    assert client.cookies.get(SESSION_COOKIE) != old
    assert client.get("/api/v1/auth/me").status_code == 200
    assert other.get("/api/v1/auth/me").status_code == 401
    assert count_sessions(db_session, tunde) == 1
    emails = db_session.execute(
        text("select template, to_address, template_data from email_outbox")
    ).all()
    assert [(e.template, e.to_address) for e in emails] == [
        ("password_changed", "tunde@gmc.example")
    ]
    assert "password" not in str(emails[0].template_data).replace("password_changed", "")
    assert log_in(client_for(app), "tunde.adebayo", "a-fresh-long-passphrase") == 200


# --- activation and reset links ------------------------------------------------------


def link_post(app: FastAPI, path: str, token: str, password: str) -> TestClient:
    client = client_for(app)
    client.post(path, json={"token": token, "password": password}, headers={"Origin": ORIGIN})
    return client


def test_activation_sets_the_password_verifies_the_email_and_logs_in(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    """AT-06.1, D-039."""
    ngozi = make_login(
        db_session,
        username="ngozi.okeke",
        email="ngozi@gmc.example",
        school_id=gmc,
        role="school_admin",
        is_primary=True,
        password=None,
    )
    db_session.execute(
        text("update users set email_verified_at = null where id = :id"), {"id": ngozi}
    )
    make_link(db_session, ngozi, "activation", "activation-token-for-ngozi-okeke-0001")

    client = client_for(app)
    response = client.post(
        "/api/v1/auth/activate",
        json={"token": "activation-token-for-ngozi-okeke-0001", "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200
    assert response.headers["referrer-policy"] == "no-referrer"
    assert client.get("/api/v1/auth/me").json()["user"]["username"] == "ngozi.okeke"
    verified = db_session.scalar(
        text("select email_verified_at is not null from users where id = :id"), {"id": ngozi}
    )
    assert verified is True

    again = problem(
        client_for(app),
        "POST",
        "/api/v1/auth/activate",
        json={"token": "activation-token-for-ngozi-okeke-0001", "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert (again["_status"], again["code"]) == (400, "link_invalid")


@pytest.mark.parametrize("problem_kind", ["expired", "tampered", "wrong_purpose", "cancelled"])
def test_bad_links_set_no_password(
    app: FastAPI, db_session: Session, gmc: uuid.UUID, problem_kind: str
) -> None:
    """AT-06.2, AC02.3."""
    user = make_login(db_session, username="amaka.eze", school_id=gmc, password=None)
    token = "a-perfectly-good-link-token-for-amaka-0002"  # noqa: S105 (fictional)
    link_id = make_link(db_session, user, "activation", token)
    sent = token
    path = "/api/v1/auth/activate"
    if problem_kind == "expired":
        db_session.execute(
            text("update account_tokens set expires_at = now() - interval '1 second'")
        )
    elif problem_kind == "tampered":
        sent = token[:-1] + "3"
    elif problem_kind == "wrong_purpose":
        path = "/api/v1/auth/password/reset"
    else:
        db_session.execute(
            text("update account_tokens set cancelled_at = now() where id = :id"), {"id": link_id}
        )
    answer = problem(
        client_for(app),
        "POST",
        path,
        json={"token": sent, "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert (answer["_status"], answer["code"]) == (400, "link_invalid")
    assert db_session.scalar(
        text("select password_hash is null from users where id = :id"), {"id": user}
    )


def test_a_refused_password_keeps_the_link(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    """AT-06.3: nothing is saved and the link still works."""
    user = make_login(db_session, username="amaka.eze", school_id=gmc, password=None)
    make_link(db_session, user, "activation", "keep-this-link-token-for-amaka-0003")
    for weak, code in (
        ("y" * 14, "password_too_short"),
        ("password1234567", "password_too_common"),
    ):
        answer = problem(
            client_for(app),
            "POST",
            "/api/v1/auth/activate",
            json={"token": "keep-this-link-token-for-amaka-0003", "password": weak},
            headers={"Origin": ORIGIN},
        )
        assert answer["code"] == code
    client = link_post(
        app, "/api/v1/auth/activate", "keep-this-link-token-for-amaka-0003", PASSWORD
    )
    assert client.get("/api/v1/auth/me").status_code == 200


def test_forgot_password_answers_the_same_and_sends_only_when_allowed(
    app: FastAPI, db_session: Session, gmc: uuid.UUID, tunde: uuid.UUID
) -> None:
    """AT-28.2, AC02.8, D-041: verified, active, non-student accounts only."""
    pupil = make_login(
        db_session, username="ada.nwosu", email="ada@pupil.example", school_id=gmc, student=True
    )
    create_student(db_session, gmc, "GMC/2026/014", "Nwosu", "Ada", user_id=pupil)
    unverified = make_login(
        db_session, username="new.parent", email="parent@home.example", school_id=gmc, role="parent"
    )
    db_session.execute(
        text("update users set email_verified_at = null where id = :id"), {"id": unverified}
    )
    gone = make_login(db_session, username="old.teacher", email="old@gmc.example", school_id=gmc)
    db_session.execute(text("update users set is_active = false where id = :id"), {"id": gone})

    answers: list[dict[str, Any]] = []
    for email in (
        "TUNDE@gmc.example",
        "nobody@nowhere.example",
        "ada@pupil.example",
        "ada.nwosu",
        "GMC/2026/014",
        "parent@home.example",
        "old@gmc.example",
    ):
        answers.append(
            problem(
                client_for(app),
                "POST",
                "/api/v1/auth/password/forgot",
                json={"email": email},
                headers={"Origin": ORIGIN},
            )
        )
    assert all(answer == answers[0] for answer in answers)
    assert answers[0]["_status"] == 202

    emails = db_session.execute(
        text("select template, to_address, template_data, priority from email_outbox")
    ).all()
    assert [(e.template, e.to_address) for e in emails] == [("password_reset", "tunde@gmc.example")]
    # The link is made by the sender at send time (D-081): no token in the outbox.
    assert set(emails[0].template_data) == {"user_id", "full_name"}
    assert emails[0].priority == 1


def test_a_reset_link_works_once_and_ends_every_other_session(
    app: FastAPI, db_session: Session, tunde: uuid.UUID
) -> None:
    """AT-29.4, F02 rule 9."""
    other = logged_in(app, "tunde.adebayo")
    make_link(db_session, tunde, "reset", "reset-token-for-tunde-adebayo-00000004")
    client = link_post(
        app,
        "/api/v1/auth/password/reset",
        "reset-token-for-tunde-adebayo-00000004",
        "a-fresh-long-passphrase",
    )
    assert client.get("/api/v1/auth/me").status_code == 200
    assert other.get("/api/v1/auth/me").status_code == 401
    assert count_sessions(db_session, tunde) == 1
    templates = db_session.scalars(text("select template from email_outbox")).all()
    assert templates == ["password_changed"]
    again = link_post(
        app,
        "/api/v1/auth/password/reset",
        "reset-token-for-tunde-adebayo-00000004",
        "another-long-passphrase",
    )
    assert again.get("/api/v1/auth/me").status_code == 401
    assert log_in(client_for(app), "tunde.adebayo", "a-fresh-long-passphrase") == 200


# --- the school login link and /auth/me --------------------------------------------------


def test_the_school_login_link_shows_only_public_details(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    """AT-09.6, F02 rule 2."""
    client = client_for(app)
    assert client.get("/api/v1/auth/schools/gmc/public").json() == {
        "code": "GMC",
        "name": "Greenfield Model College",
        "colour": "#1E6B45",
        "logo_url": None,
    }
    assert client.get("/api/v1/auth/schools/NOPE/public").status_code == 404
    db_session.execute(text("update schools set status = 'suspended' where id = :id"), {"id": gmc})
    assert client.get("/api/v1/auth/schools/GMC/public").status_code == 404


def test_me_describes_the_principal(app: FastAPI, db_session: Session, gmc: uuid.UUID) -> None:
    """BUILD_PROMPT 9.2b: user, school, role, permissions, primary flag, features, notices."""
    ngozi = make_login(
        db_session,
        username="ngozi.okeke",
        full_name="Ngozi Okeke",
        email="ngozi@gmc.example",
        school_id=gmc,
        role="school_admin",
        is_primary=True,
    )
    with acting_as(db_session, "app_user", school_id=gmc, user_id=ngozi):
        post_notice(db_session, gmc)
    db_session.execute(
        text(
            "insert into notice_recipients (school_id, notice_id, user_id)"
            " select school_id, id, :id from notices"
        ),
        {"id": ngozi},
    )
    me = logged_in(app, "ngozi.okeke").get("/api/v1/auth/me").json()
    assert me["user"] == {
        "id": str(ngozi),
        "full_name": "Ngozi Okeke",
        "username": "ngozi.okeke",
        "email": "ngozi@gmc.example",
    }
    assert me["school"] == {
        "id": str(gmc),
        "code": "GMC",
        "name": "Greenfield Model College",
        "colour": "#1E6B45",
    }
    assert me["role"] == "school_admin"
    assert me["is_primary"] is True
    assert me["is_super_admin"] is False
    assert "school_admins.create" in me["permissions"]
    assert "scores.enter" not in me["permissions"]
    assert set(me["features"]) == {
        "results",
        "report_cards",
        "parent_portal",
        "notice_board",
        "email_notifications",
    }
    assert me["form_class"] is None
    assert me["unread_notices"] == 1
    assert me["schools"] == [
        {"id": str(gmc), "name": "Greenfield Model College", "role": "school_admin"}
    ]


def test_me_for_the_super_admin_has_no_school(app: FastAPI, db_session: Session) -> None:
    make_login(db_session, username="platform.owner", is_super_admin=True)
    me = logged_in(app, "platform.owner").get("/api/v1/auth/me").json()
    assert me["school"] is None
    assert me["role"] == "super_admin"
    assert "schools.manage" in me["permissions"]
    assert me["features"] == []


def test_a_parent_in_two_schools_chooses_one_of_their_own(
    app: FastAPI, db_session: Session, gmc: uuid.UUID, bsa: uuid.UUID
) -> None:
    """D-138: the school comes from the parent's own memberships, never anyone else's."""
    from tests.factories import parent_accepts_link

    parent = make_login(
        db_session, username="ikenna.obi", email="ikenna@home.example", school_id=gmc, role="parent"
    )
    parent_accepts_link(db_session, parent, bsa)
    other = create_school(db_session, code="RCS", name="Royal Crest Schools")
    client = logged_in(app, "ikenna.obi")
    me = client.get("/api/v1/auth/me").json()
    assert {school["name"] for school in me["schools"]} == {
        "Greenfield Model College",
        "Bright Stars Academy",
    }
    chosen = client.get("/api/v1/auth/me", headers={"X-School-Id": str(bsa)}).json()
    assert chosen["school"]["code"] == "BSA"
    assert client.get("/api/v1/auth/me", headers={"X-School-Id": str(other)}).status_code == 404
    assert client.get("/api/v1/auth/me", headers={"X-School-Id": "not-a-uuid"}).status_code == 404


# --- the database side (migration 20) ----------------------------------------------------


def test_app_roles_cannot_read_throttles_or_call_auth_functions_they_do_not_need(
    db_session: Session,
) -> None:
    calls: dict[str, Callable[[], object]] = {
        "login_throttles": lambda: db_session.execute(text("select * from login_throttles")),
        "auth_login_account": lambda: db_session.execute(
            text("select * from auth_login_account(null, 'x')")
        ),
    }
    for role in ("app_verifier", "app_sender", "app_platform"):
        with acting_as(db_session, role):
            for call in calls.values():
                with refused(db_session):
                    call()
    with acting_as(db_session, "app_user"), refused(db_session):
        db_session.execute(text("select * from login_throttles"))


def test_the_session_lookup_names_only_live_sessions(db_session: Session, tunde: uuid.UUID) -> None:
    db_session.execute(
        text(
            "insert into user_sessions (user_id, token_hash, expires_at)"
            " values (:id, :hash, now() + interval '1 day')"
        ),
        {"id": tunde, "hash": token_hash("live-session-token")},
    )
    with acting_as(db_session, "app_user"):
        found = db_session.scalar(
            text("select auth_session_account(:h)"), {"h": token_hash("live-session-token")}
        )
        missing = db_session.scalar(
            text("select auth_session_account(:h)"), {"h": token_hash("other-token")}
        )
    assert (found, missing) == (tunde, None)


def test_the_school_login_link_serves_the_logo_and_nothing_else(
    app: FastAPI, db_session: Session, gmc: uuid.UUID, tmp_path: Path
) -> None:
    """CHANGE 2026-10-22, F02 rule 2, AT-09.6: the logo is public; signatures never are."""
    storage = LocalFileStorage(tmp_path)
    app.dependency_overrides[get_file_storage] = lambda: storage
    client = client_for(app)
    assert client.get("/api/v1/auth/schools/GMC/logo").status_code == 404  # no logo yet

    uploader = make_login(db_session, username="ngozi.okeke", school_id=gmc, role="school_admin")

    def stored(purpose: str, data: bytes) -> uuid.UUID:
        key = f"schools/{gmc}/{purpose}/{uuid.uuid4().hex}.png"
        storage.put(key, data, "image/png")
        use_context(db_session, school_id=gmc, user_id=uploader)  # the database names the uploader
        file_id: uuid.UUID = db_session.scalar(
            text(
                "insert into files (school_id, purpose, storage_key, content_type, size_bytes,"
                " sha256, original_name) values (:s, :p, :k, 'image/png', :n, :h, 'x.png')"
                " returning id"
            ),
            {"s": gmc, "p": purpose, "k": key, "n": len(data), "h": hashlib.sha256(data).digest()},
        )
        use_context(db_session)
        return file_id

    signature = stored("signature", b"\x89PNG signature bytes")
    db_session.execute(
        text("update schools set logo_file_id = :f where id = :s"), {"f": signature, "s": gmc}
    )
    assert client.get("/api/v1/auth/schools/GMC/logo").status_code == 404  # not a logo

    logo = stored("logo", b"\x89PNG logo bytes")
    db_session.execute(
        text("update schools set logo_file_id = :f where id = :s"), {"f": logo, "s": gmc}
    )
    response = client.get("/api/v1/auth/schools/gmc/logo")
    assert response.status_code == 200
    assert response.content == b"\x89PNG logo bytes"
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=3600"
    etag = response.headers["etag"]
    assert (
        client.get("/api/v1/auth/schools/GMC/logo", headers={"If-None-Match": etag}).status_code
        == 304
    )
    assert client.get("/api/v1/auth/schools/GMC/public").json()["logo_url"] == (
        "/api/v1/auth/schools/GMC/logo"
    )
    assert client.get("/api/v1/auth/schools/NOPE/logo").status_code == 404
    db_session.execute(text("update schools set status = 'suspended' where id = :id"), {"id": gmc})
    assert client.get("/api/v1/auth/schools/GMC/logo").status_code == 404
