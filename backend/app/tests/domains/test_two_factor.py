"""Two-factor login for the super admin (CHANGE D, D-043; SPEC F02 rule 11).

Behaviour: after the password on /platform/login the session only waits for
a code (5 minutes) and every other route refuses it; the first login sets up
the authenticator (a secret shown as a QR code and text, the same until
confirmed) and the first right code shows 10 one-time recovery codes; later
logins take a code from the app (this step or one either side, each step once)
or one recovery code; wrong codes count as failed logins; the secret and the
codes are unreadable by the app's database roles; reset-super-admin starts
two-factor again; without TOTP_ENCRYPTION_KEY the routes answer 503. All data
is fictional.
"""

import uuid
from typing import Any

import pyotp
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.cli.super_admin import reset_super_admin
from app.core.config import Settings
from app.core.security import SESSION_COOKIE
from app.src.two_factor.router import get_clock, get_totp_cipher
from app.src.two_factor.services import NOT_SET_UP, Cipher
from app.tests.auth_support import (
    ORIGIN,
    PASSWORD,
    TEST_CIPHER,
    build_auth_app,
    client_for,
    csrf,
    make_login,
    use_fast_hashing,
)
from app.tests.db_support import refused
from app.tests.factories import create_school

NOW = 1_800_000_000  # a fixed moment (whole seconds), so codes are predictable
STEP = 30


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


class Clock:
    def __init__(self) -> None:
        self.now: int = NOW

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def app(db_session: Session, clock: Clock) -> FastAPI:
    app = build_auth_app(db_session)
    app.dependency_overrides[get_clock] = lambda: clock
    return app


@pytest.fixture
def owner(db_session: Session) -> uuid.UUID:
    return make_login(db_session, username="platform.admin", is_super_admin=True)


def password_step(app: FastAPI) -> tuple[TestClient, dict[str, Any]]:
    client = client_for(app)
    response = client.post(
        "/api/v1/auth/platform/login",
        json={"identifier": "platform.admin", "password": PASSWORD},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200, response.json()
    return client, response.json()


def post(client: TestClient, url: str, body: Any = None) -> tuple[int, dict[str, Any]]:
    response = client.post(f"/api/v1{url}", json=body, headers=csrf(client))
    answer: dict[str, Any] = response.json()
    answer.pop("request_id", None)
    return response.status_code, answer


def set_up(app: FastAPI) -> tuple[str, list[str]]:
    """A full first login: password, scan, first code. The secret and the codes."""
    client, first = password_step(app)
    assert first["two_factor"] == "setup"
    _, shown = post(client, "/auth/two-factor/setup")
    status, done = post(
        client,
        "/auth/two-factor/setup/confirm",
        {"code": pyotp.TOTP(shown["secret"]).at(NOW)},
    )
    assert status == 200, done
    return shown["secret"], done["recovery_codes"]


# --- the half-signed-in step -------------------------------------------------------


def test_a_password_alone_only_waits_for_the_code(app: FastAPI, owner: uuid.UUID) -> None:
    client, first = password_step(app)
    assert first == {"must_change_password": False, "school_id": None, "two_factor": "setup"}
    me = client.get("/api/v1/auth/me")
    assert (me.status_code, me.json()["code"]) == (401, "two_factor_required")
    assert client.get("/api/v1/platform/schools").status_code == 401
    assert client.get("/api/v1/auth/two-factor/recovery-codes").status_code == 401


def test_the_waiting_step_ends_after_five_minutes(
    app: FastAPI, db_session: Session, owner: uuid.UUID
) -> None:
    client, _ = password_step(app)
    left = db_session.scalar(
        text("select expires_at - now() from user_sessions where user_id = :u"), {"u": owner}
    )
    assert 299 <= left.total_seconds() <= 300
    db_session.execute(
        text(
            "update user_sessions set created_at = now() - interval '10 min',"
            " last_seen_at = now() - interval '6 min', expires_at = now() - interval '1 s'"
        )
    )
    assert post(client, "/auth/two-factor/setup")[0] == 401


def test_other_accounts_cannot_use_the_code_routes(
    app: FastAPI, db_session: Session, owner: uuid.UUID
) -> None:
    school = create_school(db_session, code="GMC", name="Greenfield Model College")
    make_login(db_session, username="tunde.adebayo", school_id=school)
    client = client_for(app)
    client.post(
        "/api/v1/auth/login",
        json={"identifier": "tunde.adebayo", "password": PASSWORD, "school_code": "GMC"},
        headers={"Origin": ORIGIN},
    )
    for url in ("/auth/two-factor/setup", "/auth/two-factor/verify", "/auth/two-factor/recovery"):
        status, answer = post(client, url, {"code": "123456"} if "setup" not in url else None)
        assert (status, answer["code"]) == (401, "not_signed_in"), url


# --- set-up ---------------------------------------------------------------------------


def test_set_up_shows_one_secret_until_it_is_confirmed(
    app: FastAPI, db_session: Session, owner: uuid.UUID
) -> None:
    client, _ = password_step(app)
    _, first = post(client, "/auth/two-factor/setup")
    _, again = post(client, "/auth/two-factor/setup")
    assert first["secret"] == again["secret"]
    assert first["qr_svg"].startswith("<svg")
    # Stored encrypted: the database never holds the secret as text.
    sealed = bytes(
        db_session.scalar(text("select totp_secret from users where id = :u"), {"u": owner})
    )
    assert first["secret"].encode() not in sealed
    assert TEST_CIPHER.open(sealed) == first["secret"]


def test_a_wrong_first_code_keeps_waiting(app: FastAPI, owner: uuid.UUID) -> None:
    client, _ = password_step(app)
    _, shown = post(client, "/auth/two-factor/setup")
    for code in ("000000", "abcdef", "1234567", pyotp.TOTP(shown["secret"]).at(NOW - 2 * STEP)):
        status, answer = post(client, "/auth/two-factor/setup/confirm", {"code": code})
        assert (status, answer["code"]) == (401, "code_failed"), code
    assert client.get("/api/v1/auth/me").status_code == 401


def test_the_first_right_code_signs_in_and_shows_ten_codes_once(
    app: FastAPI, db_session: Session, owner: uuid.UUID
) -> None:
    client, _ = password_step(app)
    old_token = client.cookies.get(SESSION_COOKIE)
    _, shown = post(client, "/auth/two-factor/setup")
    status, done = post(
        client, "/auth/two-factor/setup/confirm", {"code": pyotp.TOTP(shown["secret"]).at(NOW)}
    )
    assert status == 200
    codes = done["recovery_codes"]
    assert len(codes) == 10 and len(set(codes)) == 10
    assert all(len(code) == 11 and code[5] == "-" for code in codes)
    # A new token for the full session (D-037); the waiting one is gone.
    assert client.cookies.get(SESSION_COOKIE) != old_token
    assert client.get("/api/v1/auth/me").json()["is_super_admin"] is True
    left = db_session.scalar(
        text("select expires_at - now() from user_sessions where user_id = :u"), {"u": owner}
    )
    assert left.total_seconds() > 11 * 3600
    # Only hashes are kept.
    stored = db_session.scalars(text("select code_hash from recovery_codes")).all()
    assert len(stored) == 10 and all(
        code.encode() not in bytes(h) for code in codes for h in stored
    )
    # Set-up cannot run twice.
    assert post(client, "/auth/two-factor/setup")[0] in (401, 409)


# --- later logins -------------------------------------------------------------------


def test_later_logins_take_a_code_once(app: FastAPI, clock: Clock, owner: uuid.UUID) -> None:
    secret, _ = set_up(app)
    totp = pyotp.TOTP(secret)
    clock.now = NOW + 10 * STEP
    client, first = password_step(app)
    assert first["two_factor"] == "code"
    # The app's clock may be one step out either way; two steps is too far.
    assert (
        post(client, "/auth/two-factor/verify", {"code": totp.at(clock.now - 2 * STEP)})[0] == 401
    )
    assert post(client, "/auth/two-factor/verify", {"code": totp.at(clock.now - STEP)})[0] == 200
    # The same code (the same step, or an earlier one) never works twice.
    again, _ = password_step(app)
    assert post(again, "/auth/two-factor/verify", {"code": totp.at(clock.now - STEP)})[0] == 401
    assert post(again, "/auth/two-factor/verify", {"code": totp.at(clock.now)})[0] == 200


def test_a_recovery_code_works_once(app: FastAPI, owner: uuid.UUID) -> None:
    _, codes = set_up(app)
    client, _ = password_step(app)
    status, answer = post(client, "/auth/two-factor/recovery", {"code": codes[0].lower()})
    assert (status, answer["codes_left"]) == (200, 9)
    assert client.get("/api/v1/auth/me").status_code == 200
    again, _ = password_step(app)
    assert post(again, "/auth/two-factor/recovery", {"code": codes[0]})[0] == 401
    assert post(again, "/auth/two-factor/recovery", {"code": "AAAAA-AAAAA"})[0] == 401


def test_wrong_codes_are_throttled_like_passwords(
    app: FastAPI, db_session: Session, clock: Clock, owner: uuid.UUID
) -> None:
    """D-042: five free tries, then even the right code waits."""
    secret, _ = set_up(app)
    clock.now = NOW + 10 * STEP
    client, _ = password_step(app)
    for _ in range(5):
        assert post(client, "/auth/two-factor/verify", {"code": "000000"})[0] == 401
    right = pyotp.TOTP(secret).at(clock.now)
    assert post(client, "/auth/two-factor/verify", {"code": right})[0] == 401
    db_session.execute(text("update login_throttles set locked_until = now() - interval '1 s'"))
    assert post(client, "/auth/two-factor/verify", {"code": right})[0] == 200


def test_new_recovery_codes_need_a_fresh_code(app: FastAPI, clock: Clock, owner: uuid.UUID) -> None:
    secret, old_codes = set_up(app)
    clock.now = NOW + 10 * STEP
    client, _ = password_step(app)
    post(client, "/auth/two-factor/verify", {"code": pyotp.TOTP(secret).at(clock.now)})
    assert client.get("/api/v1/auth/two-factor/recovery-codes").json()["codes_left"] == 10
    assert post(client, "/auth/two-factor/recovery-codes", {"code": "000000"})[0] == 401
    clock.now += STEP
    status, fresh = post(
        client, "/auth/two-factor/recovery-codes", {"code": pyotp.TOTP(secret).at(clock.now)}
    )
    assert status == 200 and set(fresh["recovery_codes"]).isdisjoint(old_codes)
    waiting, _ = password_step(app)
    assert post(waiting, "/auth/two-factor/recovery", {"code": old_codes[1]})[0] == 401


# --- the database and the server ----------------------------------------------------


def test_the_app_roles_cannot_read_the_secret_or_the_codes(
    db_session: Session, owner: uuid.UUID
) -> None:
    for role in ("app_user", "app_platform", "app_verifier", "app_sender"):
        for sql in (
            "select totp_secret from users",
            "select totp_last_step from users",
            "select code_hash from recovery_codes",
        ):
            with refused(db_session, "42501"):
                db_session.execute(text(f"set local role {role}"))
                db_session.execute(text(sql))


def test_reset_super_admin_starts_two_factor_again(
    app: FastAPI, db_session: Session, owner: uuid.UUID
) -> None:
    set_up(app)
    reset_super_admin(db_session, username="platform.admin", password=PASSWORD)
    row = db_session.execute(
        text("select totp_secret, totp_confirmed_at from users where id = :u"), {"u": owner}
    ).one()
    assert (row.totp_secret, row.totp_confirmed_at) == (None, None)
    assert db_session.scalar(text("select count(*) from recovery_codes")) == 0
    assert password_step(app)[1]["two_factor"] == "setup"


def test_without_the_key_the_code_routes_answer_503(app: FastAPI, owner: uuid.UUID) -> None:
    def no_key() -> Cipher:
        raise NOT_SET_UP

    app.dependency_overrides[get_totp_cipher] = no_key
    client, _ = password_step(app)
    status, answer = post(client, "/auth/two-factor/setup")
    assert (status, answer["code"]) == (503, "two_factor_unavailable")


def test_a_secret_sealed_with_another_key_cannot_be_used(app: FastAPI, owner: uuid.UUID) -> None:
    set_up(app)
    app.dependency_overrides[get_totp_cipher] = lambda: Cipher(b"another-fictional-key-32-bytes!!")
    client, _ = password_step(app)
    assert post(client, "/auth/two-factor/verify", {"code": "123456"})[0] == 503


@pytest.mark.parametrize("key", ["short", "not base64 at all !!", "A" * 10])
def test_the_key_must_be_32_bytes_of_base64(key: str) -> None:
    with pytest.raises(ValueError, match="32 random bytes"):
        Settings.model_validate(
            {
                "app_secret_key": "x" * 40,
                "database_url": "postgresql+psycopg://u:p@localhost/db",
                "totp_encryption_key": key,
            }
        )
