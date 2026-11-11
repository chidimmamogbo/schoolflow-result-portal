"""The super admin commands (BUILD_PROMPT 9.2v; SPEC section 4; D-046, D-180).

Behaviour: `create-super-admin` makes a platform login from the command line
only (there is no route for it), with a password typed twice at the prompt or
read from a named environment variable, checked against the staff password
rules and never printed. `reset-super-admin` gives an existing super admin a
new password and signs them out everywhere; it refuses any other account, so
the command line can never reset a school admin, teacher or parent. Both write
an audit event with no secret in it. All data is fictional.
"""

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.cli.__main__ import main
from app.tests.auth_support import (
    PASSWORD,
    build_auth_app,
    client_for,
    log_in,
    make_login,
    use_fast_hashing,
)
from app.tests.factories import create_school

NEW_PASSWORD = "quiet-orange-harbour-lamp"  # noqa: S105 (fictional; 25 characters)


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    return build_auth_app(db_session)


class Run:
    """Runs the command on the rolled-back test session, with typed answers."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.printed: list[str] = []

    def __call__(self, *args: str, answers: tuple[str, ...] = ()) -> int:
        typed = iter(answers)

        @contextmanager
        def connect() -> Generator[Session]:
            yield self.db

        def ask(_: str) -> str:
            return next(typed)

        return main(list(args), connect=connect, ask=ask, out=self.printed.append)

    @property
    def output(self) -> str:
        return "\n".join(self.printed)


@pytest.fixture
def run(db_session: Session) -> Run:
    return Run(db_session)


CREATE = ("create-super-admin", "--username", "platform.admin", "--full-name", "Platform Admin")


def account(db: Session, username: str) -> Any:
    return db.execute(
        text(
            "select id, is_super_admin, must_change_password, email, password_hash"
            " from users where username = :u"
        ),
        {"u": username},
    ).first()


def can_log_in(app: FastAPI, username: str, password: str) -> bool:
    return log_in(client_for(app), username, password) == 200


def test_a_super_admin_is_made_and_can_log_in(app: FastAPI, run: Run, db_session: Session) -> None:
    code = run(*CREATE, "--email", "Admin@Platform.Example", answers=(PASSWORD, PASSWORD))
    assert code == 0
    made = account(db_session, "platform.admin")
    assert made.is_super_admin and not made.must_change_password
    assert made.email == "admin@platform.example"
    assert made.password_hash != PASSWORD
    assert (
        db_session.scalar(
            text("select count(*) from school_memberships where user_id = :u"), {"u": made.id}
        )
        == 0
    )
    assert can_log_in(app, "platform.admin", PASSWORD)
    assert PASSWORD not in run.output
    assert "platform.admin" in run.output


def test_the_password_can_come_from_a_named_variable(
    app: FastAPI, run: Run, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIRST_ADMIN_PASSWORD", PASSWORD)
    assert run(*CREATE, "--password-env", "FIRST_ADMIN_PASSWORD") == 0
    assert can_log_in(app, "platform.admin", PASSWORD)
    assert PASSWORD not in run.output


def test_a_missing_variable_is_refused(run: Run, db_session: Session) -> None:
    assert run(*CREATE, "--password-env", "NOT_SET_ANYWHERE_XYZ") == 2
    assert account(db_session, "platform.admin") is None


def test_two_different_typings_are_refused(run: Run, db_session: Session) -> None:
    assert run(*CREATE, answers=(PASSWORD, PASSWORD + "x")) == 2
    assert account(db_session, "platform.admin") is None
    assert "do not match" in run.output


@pytest.mark.parametrize(
    ("password", "word"),
    [("short-but-ok", "15 characters"), ("password1234567", "too common")],
)
def test_weak_passwords_are_refused(
    run: Run, db_session: Session, password: str, word: str
) -> None:
    assert run(*CREATE, answers=(password, password)) == 2
    assert account(db_session, "platform.admin") is None
    assert word in run.output
    assert password not in run.output


def test_a_taken_username_is_refused(run: Run, db_session: Session) -> None:
    make_login(db_session, username="platform.admin", full_name="Somebody Else")
    assert run(*CREATE, answers=(PASSWORD, PASSWORD)) == 1
    assert not account(db_session, "platform.admin").is_super_admin
    assert "taken" in run.output


def test_a_badly_formed_username_is_refused(run: Run, db_session: Session) -> None:
    bad = ("create-super-admin", "--username", "Platform Admin", "--full-name", "Platform Admin")
    assert run(*bad, answers=(PASSWORD, PASSWORD)) == 1
    assert db_session.scalar(text("select count(*) from users where is_super_admin")) == 0
    # The operator is told what a username may hold, not just that it failed.
    assert "3 to 30 small letters" in run.output


def test_making_one_is_audited_without_the_password(run: Run, db_session: Session) -> None:
    run(*CREATE, answers=(PASSWORD, PASSWORD))
    made = account(db_session, "platform.admin")
    event = db_session.execute(
        text(
            "select school_id, actor_role, target_id, new_values from audit_events"
            " where action = 'platform.super_admin_created'"
        )
    ).one()
    assert (event.school_id, event.actor_role, event.target_id) == (None, "system", made.id)
    assert event.new_values == {"username": "platform.admin"}


def test_a_reset_gives_a_new_password_and_signs_out_everywhere(
    app: FastAPI, run: Run, db_session: Session
) -> None:
    run(*CREATE, answers=(PASSWORD, PASSWORD))
    signed_in = client_for(app)
    assert log_in(signed_in, "platform.admin", PASSWORD) == 200
    assert signed_in.get("/api/v1/auth/me").status_code == 200

    reset = ("reset-super-admin", "--username", "platform.admin")
    assert run(*reset, answers=(NEW_PASSWORD, NEW_PASSWORD)) == 0
    assert signed_in.get("/api/v1/auth/me").status_code == 401
    assert not can_log_in(app, "platform.admin", PASSWORD)
    assert can_log_in(app, "platform.admin", NEW_PASSWORD)
    assert NEW_PASSWORD not in run.output
    actions = set(
        db_session.scalars(text("select action from audit_events where target_table = 'users'"))
    )
    assert "platform.super_admin_reset" in actions


def test_a_reset_clears_a_temporary_password(run: Run, db_session: Session) -> None:
    run(*CREATE, answers=(PASSWORD, PASSWORD))
    db_session.execute(
        text(
            "update users set must_change_password = true,"
            " temp_password_expires_at = now() + interval '1 day' where username = 'platform.admin'"
        )
    )
    assert (
        run("reset-super-admin", "--username", "platform.admin", answers=(NEW_PASSWORD,) * 2) == 0
    )
    assert not account(db_session, "platform.admin").must_change_password


def test_the_command_line_never_resets_anyone_else(
    app: FastAPI, run: Run, db_session: Session
) -> None:
    """SPEC section 4: the super admin resets school admins only, never through here."""
    school = create_school(db_session, code="GMC", name="Greenfield Model College")
    make_login(
        db_session,
        username="ngozi.okeke",
        full_name="Ngozi Okeke",
        school_id=school,
        role="school_admin",
        is_primary=True,
    )
    for username in ("ngozi.okeke", "nobody.here"):
        assert run("reset-super-admin", "--username", username, answers=(NEW_PASSWORD,) * 2) == 1
        assert "No super admin" in run.output
    assert can_log_in(app, "ngozi.okeke", PASSWORD)
    assert not can_log_in(app, "ngozi.okeke", NEW_PASSWORD)


def test_a_reset_checks_the_new_password_too(run: Run, db_session: Session) -> None:
    run(*CREATE, answers=(PASSWORD, PASSWORD))
    before = account(db_session, "platform.admin").password_hash
    assert run("reset-super-admin", "--username", "platform.admin", answers=("tiny",) * 2) == 2
    assert account(db_session, "platform.admin").password_hash == before


def test_without_a_command_it_explains_itself(run: Run) -> None:
    assert run() == 2
    assert "create-super-admin" in run.output


def test_ids_are_real_uuids(run: Run, db_session: Session) -> None:
    run(*CREATE, answers=(PASSWORD, PASSWORD))
    assert isinstance(account(db_session, "platform.admin").id, uuid.UUID)
