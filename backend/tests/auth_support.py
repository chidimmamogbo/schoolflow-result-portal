"""Helpers for the auth and authorization tests (BUILD_PROMPT 9.2b, 9.2c).

`build_auth_app` gives the real app on the rolled-back test session, but
running each request as the app's own database role (app_user), so
row-level security and grants apply exactly as on Neon. `make_login` makes a
fictional account with a password; `logged_in` returns a client with its
session and CSRF cookies. All names, emails and passwords are fictional.
"""

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import CursorResult, text
from sqlalchemy.orm import Session

from schoolflow_api.auth import passwords
from schoolflow_api.auth.passwords import hash_password
from schoolflow_api.auth.tokens import CSRF_COOKIE, CSRF_HEADER, token_hash
from schoolflow_api.core.deps import get_db, get_rate_limiter
from schoolflow_api.core.ratelimit import RateLimiter
from schoolflow_api.db import use_context
from schoolflow_api.main import create_app
from schoolflow_api.platform.deps import get_platform_db
from schoolflow_api.settings import get_settings
from tests.factories import add_membership, create_user

PASSWORD = "fictional-blue-mango-river"  # noqa: S105 (fictional; 26 characters, not common)
STUDENT_PASSWORD = "mango-river-9"  # noqa: S105 (fictional; 13 characters)
_base = urlsplit(str(get_settings().app_base_url))
ORIGIN = f"{_base.scheme}://{_base.netloc}"


def use_fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests make hundreds of hashes; a tiny Argon2 cost keeps the suite quick."""
    fast = PasswordHash((Argon2Hasher(memory_cost=1024, time_cost=1, parallelism=1),))
    monkeypatch.setattr(passwords, "PASSWORD_HASH", fast)


def build_auth_app(db_session: Session) -> FastAPI:
    """The real app; each request runs as app_user on the test session."""
    app = create_app(app_env="local")

    def test_db() -> Iterator[Session]:
        # A fresh request: nobody signed in yet, and the app's own role. Its own
        # savepoint plays the request's transaction: a failed request undoes only
        # its own work, never the test's set-up.
        use_context(db_session)
        request = db_session.begin_nested()
        db_session.execute(text("set local role app_user"))
        try:
            yield db_session
            db_session.flush()
            db_session.execute(text("reset role"))
            request.commit()
        except Exception:
            request.rollback()  # also undoes the role change
            raise
        finally:
            use_context(db_session)

    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter.for_session(db_session)
    return app


def client_for(app: FastAPI) -> TestClient:
    # https, so the browser-style cookie jar sends the Secure cookies back.
    return TestClient(app, base_url="https://testserver")


def make_login(
    db_session: Session,
    *,
    username: str,
    full_name: str = "Tunde Adebayo",
    email: str | None = None,
    school_id: uuid.UUID | None = None,
    role: str | None = None,
    password: str | None = PASSWORD,
    is_primary: bool = False,
    is_super_admin: bool = False,
    student: bool = False,
    temporary: bool = False,
) -> uuid.UUID:
    """An activated account (owner-made), linked to a school when one is given."""
    user_id = create_user(
        db_session,
        username=username,
        full_name=full_name,
        email=email,
        is_super_admin=is_super_admin,
        student_school_id=school_id if student else None,
    )
    db_session.execute(
        text(
            "update users set password_hash = :hash, email_verified_at ="
            " case when email is null then null else now() end,"
            " must_change_password = :temporary,"
            " temp_password_expires_at = case when :temporary then now() + interval '7 days' end"
            " where id = :id"
        ),
        {
            "hash": hash_password(password) if password else None,
            "temporary": temporary,
            "id": user_id,
        },
    )
    if school_id is not None:
        add_membership(
            db_session,
            user_id,
            school_id,
            role or ("student" if student else "teacher"),
            is_primary=is_primary,
        )
    return user_id


def log_in(
    client: TestClient,
    identifier: str,
    password: str = PASSWORD,
    school_code: str | None = None,
) -> int:
    body: dict[str, str] = {"identifier": identifier, "password": password}
    if school_code is not None:
        body["school_code"] = school_code
    response = client.post("/api/v1/auth/login", json=body, headers={"Origin": ORIGIN})
    return response.status_code


def logged_in(
    app: FastAPI,
    identifier: str,
    password: str = PASSWORD,
    school_code: str | None = None,
) -> TestClient:
    client = client_for(app)
    status = log_in(client, identifier, password, school_code)
    assert status == 200, status
    return client


def csrf(client: TestClient) -> dict[str, str]:
    """What the frontend adds to every state-changing request (D-038)."""
    return {CSRF_HEADER: client.cookies.get(CSRF_COOKIE) or "", "Origin": ORIGIN}


def make_link(
    db_session: Session,
    user_id: uuid.UUID,
    purpose: str,
    token: str,
    *,
    expires_in: timedelta = timedelta(hours=1),
) -> uuid.UUID:
    """A link as the email sender makes it at send time (D-081): hash only."""
    link_id: uuid.UUID = db_session.scalar(
        text(
            "insert into account_tokens (user_id, purpose, token_hash, created_at, expires_at)"
            " values (:user_id, :purpose, :hash, :now - interval '2 hours', :expires)"
            " returning id"
        ),
        {
            "user_id": user_id,
            "purpose": purpose,
            "hash": token_hash(token),
            "now": datetime.now(UTC),
            "expires": datetime.now(UTC) + expires_in,
        },
    )
    return link_id


# Where use_context() keeps (school_id, user_id) in session.info (schoolflow_api/db.py).
CONTEXT_KEY = "schoolflow_context"
SET_CONTEXT = text(
    "select set_config('app.school_id', :s, true), set_config('app.user_id', :u, true)"
)


class PlatformAsRole:
    """The platform's database session in tests: the test session, but each
    statement runs as app_platform with the platform's own context.

    In production the platform session is a second connection logged in as
    app_platform (DATABASE_URL_PLATFORM). Tests keep everything in one rolled-
    back transaction, so this wrapper switches role around each statement and
    then puts back the app_user role and context of the request's own session.
    Only what platform code uses is provided.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self.info: dict[str, object] = {}

    def in_transaction(self) -> bool:
        return False  # use_context() then only records the context in .info

    def _as_platform[T](self, run: Callable[[], T]) -> T:
        school_id, user_id = cast(tuple[object, object], self.info.get(CONTEXT_KEY, (None, None)))
        self._session.execute(text("set local role app_platform"))
        self._session.execute(
            SET_CONTEXT,
            {"s": str(school_id or ""), "u": str(user_id or "")},
        )
        result = run()
        # Only after success: after an error the request's savepoint is rolled back.
        self._session.execute(text("set local role app_user"))
        user_school, user_user = self._session.info.get(CONTEXT_KEY, (None, None))
        self._session.execute(
            SET_CONTEXT,
            {"s": str(user_school or ""), "u": str(user_user or "")},
        )
        return result

    def execute(self, statement: Any, params: Any = None) -> Any:
        result = self._as_platform(lambda: self._session.execute(statement, params))
        rows = cast(CursorResult[Any], result)
        return BufferedResult(list(rows)) if rows.returns_rows else result

    def scalar(self, statement: Any, params: Any = None) -> Any:
        return self._as_platform(lambda: self._session.scalar(statement, params))

    def scalars(self, statement: Any, params: Any = None) -> Any:
        return self._as_platform(lambda: list(self._session.scalars(statement, params)))


class BufferedResult:
    """Rows fetched while the role was app_platform, readable afterwards."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def __iter__(self) -> Iterator[Any]:
        return iter(self._rows)

    def one(self) -> Any:
        if len(self._rows) != 1:
            raise AssertionError(f"expected one row, got {len(self._rows)}")
        return self._rows[0]

    def first(self) -> Any:
        return self._rows[0] if self._rows else None

    def all(self) -> list[Any]:
        return list(self._rows)


def build_platform_app(db_session: Session) -> FastAPI:
    """build_auth_app plus the platform session wrapper (D-051)."""
    app = build_auth_app(db_session)
    platform = PlatformAsRole(db_session)

    def test_platform_db() -> Iterator[Session]:
        platform.info.clear()
        yield cast(Session, platform)

    app.dependency_overrides[get_platform_db] = test_platform_db
    return app
