"""A new parent joins from a school's link request (SPEC F03 rule 8; D-138, D-177).

Behaviour: when a school's link request goes to an email that has no
SchoolFlow account, the email carries a link to /join. POST /auth/join with
that link's token and a password the parent chooses (at least 15 characters)
creates the parent account with the request's email (already verified: the
parent proved they read it), gives it a username made from the name the
school typed, links it to the school as a parent and to the school's
guardian record, accepts the request and logs the parent in. The link works
once. A wrong, used, expired, cancelled or declined link, or one from a
paused school or for a guardian who already has a login, is refused with the
usual "link expired" answer; a weak password is refused and the link keeps
working; an email that has since gained an account is told to log in and
accept instead. A request from another site (its Origin) is refused. All data
is fictional.
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import new_token, token_hash
from app.tests.auth_support import (
    ORIGIN,
    PASSWORD,
    build_auth_app,
    client_for,
    log_in,
    make_login,
    use_fast_hashing,
)
from app.tests.factories import create_guardian, create_school

EMAIL = "chiamaka.eze@home.example"
NEW_PASSWORD = "palm wine under the mango tree"  # noqa: S105 (fictional; 30 characters)


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    return build_auth_app(db_session)


@pytest.fixture
def gmc(db_session: Session) -> uuid.UUID:
    return create_school(db_session, code="GMC", name="Greenfield Model College")


def link_request(
    db: Session,
    school: uuid.UUID,
    *,
    email: str = EMAIL,
    name: str = "Chiamaka Eze",
    expires: str = "14 days",
) -> tuple[uuid.UUID, uuid.UUID, str]:
    """A school's open request with a link the sender has just made."""
    db.execute(text("select set_config('app.school_id', :s, true)"), {"s": str(school)})
    guardian = create_guardian(db, school, name, email=email)
    token = new_token()
    request_id: uuid.UUID = db.scalar(
        text(
            "insert into parent_link_requests"
            " (school_id, guardian_id, email, token_hash, created_at, expires_at)"
            " values (:s, :g, :e, :h, now() - interval '20 days', now() + cast(:x as interval))"
            " returning id"
        ),
        {"s": school, "g": guardian, "e": email, "h": token_hash(token), "x": expires},
    )
    return guardian, request_id, token


def join(
    client: TestClient, token: str, password: str = NEW_PASSWORD
) -> tuple[int, dict[str, str]]:
    response = client.post(
        "/api/v1/auth/join",
        json={"token": token, "password": password},
        headers={"Origin": ORIGIN},
    )
    return response.status_code, response.json()


def test_a_new_parent_joins_and_is_logged_in(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    guardian, request_id, token = link_request(db_session, gmc)
    client = client_for(app)
    status, body = join(client, token)
    assert (status, body) == (200, {"must_change_password": False})

    me = client.get("/api/v1/auth/me").json()
    assert me["role"] == "parent" and me["school"]["code"] == "GMC"
    assert me["user"]["full_name"] == "Chiamaka Eze"
    assert me["user"]["email"] == EMAIL
    assert me["user"]["username"] == "chiamaka.eze"

    account = db_session.execute(
        text(
            "select u.id, u.email_verified_at, u.must_change_password, g.user_id as guardian_user,"
            " r.accepted_at from users u, guardians g, parent_link_requests r"
            " where u.email = :e and g.id = :g and r.id = :r"
        ),
        {"e": EMAIL, "g": guardian, "r": request_id},
    ).one()
    assert account.email_verified_at is not None and not account.must_change_password
    assert account.guardian_user == account.id
    assert account.accepted_at is not None

    # The link works once; the new password logs in with the email.
    assert join(client_for(app), token)[1]["code"] == "link_invalid"
    assert log_in(client_for(app), EMAIL, NEW_PASSWORD) == 200


def test_a_weak_password_is_refused_and_the_link_still_works(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    _, _, token = link_request(db_session, gmc)
    status, body = join(client_for(app), token, "too short")
    assert (status, body["code"]) == (422, "password_too_short")
    assert db_session.scalar(text("select count(*) from users where email = :e"), {"e": EMAIL}) == 0
    assert join(client_for(app), token)[0] == 200


@pytest.mark.parametrize(
    "change", ["wrong", "expired", "cancelled", "declined", "paused", "guardian_has_login"]
)
def test_a_link_that_cannot_be_used_is_refused(
    app: FastAPI, db_session: Session, gmc: uuid.UUID, change: str
) -> None:
    guardian, request_id, token = link_request(
        db_session, gmc, expires="-1 minute" if change == "expired" else "14 days"
    )
    if change == "guardian_has_login":
        # The school has since given this guardian a login another way.
        other = make_login(db_session, username="eze.family", school_id=gmc, role="parent")
        db_session.execute(
            text("update guardians set user_id = :u where id = :g"), {"u": other, "g": guardian}
        )
    if change in ("cancelled", "declined"):
        db_session.execute(
            text(
                "update parent_link_requests set cancelled_at = case when :c = 'cancelled'"
                " then now() end, declined_at = case when :c = 'declined' then now() end"
                " where id = :r"
            ),
            {"r": request_id, "c": change},
        )
    if change == "paused":
        db_session.execute(
            text("update schools set status = 'suspended' where id = :s"),
            {"s": gmc},
        )
    status, body = join(client_for(app), new_token() if change == "wrong" else token)
    assert (status, body["code"]) == (400, "link_invalid")
    assert db_session.scalar(text("select count(*) from users where email = :e"), {"e": EMAIL}) == 0


def test_an_email_that_now_has_an_account_is_told_to_log_in(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    _, request_id, token = link_request(db_session, gmc)
    bsa = create_school(db_session, code="BSA", name="Bright Star Academy")
    make_login(db_session, username="chiamaka.e", email=EMAIL, school_id=bsa, role="parent")
    status, body = join(client_for(app), token)
    assert (status, body["code"]) == (409, "email_has_account")
    # The request stays open, so she can accept it after logging in.
    assert db_session.scalar(
        text("select accepted_at is null from parent_link_requests where id = :r"),
        {"r": request_id},
    )


def test_a_taken_username_gets_a_number(app: FastAPI, db_session: Session, gmc: uuid.UUID) -> None:
    make_login(db_session, username="chiamaka.eze", full_name="Chiamaka Eze", password=PASSWORD)
    _, _, token = link_request(db_session, gmc, name="  Chiamaka  Eze-Obi ")
    client = client_for(app)
    assert join(client, token)[0] == 200
    assert client.get("/api/v1/auth/me").json()["user"]["username"] == "chiamaka.eze.obi"

    make_login(db_session, username="chiamaka.eze.2", full_name="Chiamaka Eze", password=PASSWORD)
    _, _, second = link_request(db_session, gmc, email="other@home.example", name="Chiamaka Eze")
    client = client_for(app)
    assert join(client, second)[0] == 200
    assert client.get("/api/v1/auth/me").json()["user"]["username"] == "chiamaka.eze.3"


def test_a_name_with_no_letters_still_gets_a_username(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    _, _, token = link_request(db_session, gmc, name="Ọ̀")
    client = client_for(app)
    assert join(client, token)[0] == 200
    assert client.get("/api/v1/auth/me").json()["user"]["username"] == "parent"


def test_join_needs_our_own_site(app: FastAPI, db_session: Session, gmc: uuid.UUID) -> None:
    _, _, token = link_request(db_session, gmc)
    response = client_for(app).post(
        "/api/v1/auth/join",
        json={"token": token, "password": NEW_PASSWORD},
        headers={"Origin": "https://schoolflow.example.evil"},
    )
    assert (response.status_code, response.json()["code"]) == (403, "csrf_failed")
    assert join(client_for(app), token)[0] == 200


def test_only_the_app_may_join_links(db_session: Session) -> None:
    for role in ("app_platform", "app_verifier", "app_sender"):
        allowed = db_session.scalar(
            text("select has_function_privilege(:r, 'join_parent_link(bytea, text)', 'execute')"),
            {"r": role},
        )
        assert allowed is False, role
