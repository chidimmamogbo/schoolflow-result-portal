"""Each school's own login page and the platform's (CHANGE C, D-182; SPEC F02, AC24.4).

Behaviour: /login/{code} logs in only that school's staff, its students on the
Student tab and parents linked to it; /platform/login only the super admin.
A right password on the wrong page gets exactly the wrong-password answer and
counts as a failure. A school's page details come from its code, also while it
is suspended; an old code forwards to the new one for 30 days and never logs
anyone in. All data is fictional.
"""

import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import SESSION_COOKIE
from app.tests.auth_support import (
    ORIGIN,
    PASSWORD,
    STUDENT_PASSWORD,
    build_auth_app,
    client_for,
    make_login,
    use_fast_hashing,
)
from app.tests.db_support import refused
from app.tests.factories import create_school, parent_accepts_link

LOGIN_FAILED = "That login didn't work. Check your details and try again."


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
def people(db_session: Session, gmc: uuid.UUID, bsa: uuid.UUID) -> dict[str, uuid.UUID]:
    """A teacher in each school, a GMC pupil, a parent of both schools, the super admin."""
    parent = make_login(
        db_session,
        username="ikenna.obi",
        email="ikenna.obi@home.example",
        school_id=gmc,
        role="parent",
    )
    parent_accepts_link(db_session, parent, bsa)
    return {
        "tunde": make_login(db_session, username="tunde.adebayo", school_id=gmc),
        "kemi": make_login(db_session, username="kemi.balogun", school_id=bsa),
        "pupil": make_login(
            db_session,
            username="chukwuemeka.obi",
            school_id=gmc,
            student=True,
            password=STUDENT_PASSWORD,
        ),
        "parent": parent,
        "owner": make_login(db_session, username="platform.admin", is_super_admin=True),
    }


def post(client: TestClient, url: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    response = client.post(f"/api/v1{url}", json=body, headers={"Origin": ORIGIN})
    answer: dict[str, Any] = response.json()
    answer.pop("request_id", None)
    return response.status_code, answer


def at_school(
    client: TestClient, code: str, identifier: str, password: str = PASSWORD, tab: str = "staff"
) -> tuple[int, dict[str, Any]]:
    return post(
        client,
        "/auth/login",
        {"identifier": identifier, "password": password, "school_code": code, "tab": tab},
    )


def at_platform(
    client: TestClient, identifier: str, password: str = PASSWORD
) -> tuple[int, dict[str, Any]]:
    return post(client, "/auth/platform/login", {"identifier": identifier, "password": password})


def wrong_password_answer(app: FastAPI) -> dict[str, Any]:
    status, answer = at_school(client_for(app), "GMC", "nobody.here", "wrong-password-here")
    assert status == 401
    return answer


# --- the right page -----------------------------------------------------------------


def test_each_person_logs_in_on_their_own_page(
    app: FastAPI, gmc: uuid.UUID, bsa: uuid.UUID, people: dict[str, uuid.UUID]
) -> None:
    """F02 rule 1: staff, students (Student tab) and the super admin on their own page."""
    for code, identifier, password, tab, school in (
        ("GMC", "tunde.adebayo", PASSWORD, "staff", gmc),
        ("bsa", "kemi.balogun", PASSWORD, "staff", bsa),
        ("GMC", "chukwuemeka.obi", STUDENT_PASSWORD, "student", gmc),
    ):
        client = client_for(app)
        status, answer = at_school(client, code, identifier, password, tab)
        assert (status, answer["school_id"]) == (200, str(school)), identifier
        assert SESSION_COOKIE in client.cookies

    client = client_for(app)
    status, answer = at_platform(client, "platform.admin")
    assert (status, answer["school_id"]) == (200, None)
    assert client.get("/api/v1/auth/me").json()["is_super_admin"] is True


def test_a_parent_logs_in_on_each_linked_school_page(
    app: FastAPI, db_session: Session, gmc: uuid.UUID, bsa: uuid.UUID, people: dict[str, uuid.UUID]
) -> None:
    """F02 rule 1 (D-138): a parent of two schools uses either page and starts there."""
    for code, school in (("GMC", gmc), ("BSA", bsa)):
        status, answer = at_school(client_for(app), code, "ikenna.obi@home.example")
        assert (status, answer["school_id"]) == (200, str(school))

    rcs = create_school(db_session, code="RCS", name="Rosebud Children's School")
    assert rcs
    status, answer = at_school(client_for(app), "RCS", "ikenna.obi@home.example")
    assert (status, answer) == (401, wrong_password_answer(app))


# --- the wrong page: the wrong-password answer ---------------------------------------


@pytest.mark.parametrize(
    ("door", "identifier", "password", "tab"),
    [
        ("BSA", "tunde.adebayo", PASSWORD, "staff"),  # a GMC teacher on BSA's page
        ("GMC", "kemi.balogun", PASSWORD, "staff"),  # a BSA teacher on GMC's page
        ("BSA", "chukwuemeka.obi", STUDENT_PASSWORD, "student"),  # a GMC pupil on BSA's page
        ("GMC", "chukwuemeka.obi", STUDENT_PASSWORD, "staff"),  # a pupil on the staff tab
        ("GMC", "tunde.adebayo", PASSWORD, "student"),  # a teacher on the Student tab
        ("GMC", "platform.admin", PASSWORD, "staff"),  # the super admin on a school page
        ("XYZ", "tunde.adebayo", PASSWORD, "staff"),  # a code that does not exist
        ("platform", "tunde.adebayo", PASSWORD, "staff"),  # a teacher on the platform page
        ("platform", "ikenna.obi@home.example", PASSWORD, "staff"),  # a parent there
    ],
)
def test_the_wrong_page_gives_the_wrong_password_answer(
    app: FastAPI,
    db_session: Session,
    people: dict[str, uuid.UUID],
    door: str,
    identifier: str,
    password: str,
    tab: str,
) -> None:
    """F02 rules 1, 3 and 11 (D-182): never says the account belongs elsewhere."""
    expected = wrong_password_answer(app)
    client = client_for(app)
    if door == "platform":
        status, answer = at_platform(client, identifier, password)
    else:
        status, answer = at_school(client, door, identifier, password, tab)
    assert (status, answer) == (401, expected)
    assert SESSION_COOKIE not in client.cookies
    assert db_session.scalar(text("select count(*) from user_sessions")) == 0


def test_the_wrong_page_counts_as_a_failure(
    app: FastAPI, db_session: Session, people: dict[str, uuid.UUID]
) -> None:
    """D-042: trying an account on other pages is throttled like guessing its password."""
    for _ in range(5):
        assert at_school(client_for(app), "BSA", "tunde.adebayo")[0] == 401
    # Now locked: even the right page gets the generic answer until the wait is over.
    assert at_school(client_for(app), "GMC", "tunde.adebayo")[0] == 401
    db_session.execute(text("update login_throttles set locked_until = now() - interval '1 s'"))
    assert at_school(client_for(app), "GMC", "tunde.adebayo")[0] == 200


def test_the_old_open_login_is_gone(app: FastAPI, people: dict[str, uuid.UUID]) -> None:
    """F02 rule 1: every login names its school (or uses the platform page)."""
    status, _ = post(
        client_for(app), "/auth/login", {"identifier": "tunde.adebayo", "password": PASSWORD}
    )
    assert status == 422


# --- the page details -----------------------------------------------------------------


def public(app: FastAPI, code: str) -> tuple[int, dict[str, Any]]:
    response = client_for(app).get(f"/api/v1/auth/schools/{code}/public")
    body: dict[str, Any] = response.json()
    body.pop("request_id", None)
    return response.status_code, body


def test_a_school_page_shows_its_own_look(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    """F02 rules 2 and 12: defaults first, then the school's own choices."""
    status, page = public(app, "gmc")
    assert status == 200
    assert (page["code"], page["name"]) == ("GMC", "Greenfield Model College")
    assert (page["layout"], page["picture"], page["message"], page["photo_url"]) == (
        "half",
        "pattern",
        None,
        None,
    )
    db_session.execute(
        text(
            "update schools set login_layout = 'behind', login_picture = 'people',"
            " login_message = 'Knowledge, Discipline and Service' where id = :id"
        ),
        {"id": gmc},
    )
    page = public(app, "GMC")[1]
    assert (page["layout"], page["picture"], page["message"]) == (
        "behind",
        "people",
        "Knowledge, Discipline and Service",
    )


def test_a_suspended_school_page_looks_normal_and_says_so_after_login(
    app: FastAPI, db_session: Session, gmc: uuid.UUID, people: dict[str, uuid.UUID]
) -> None:
    """F02 rule 13, AC24.3: its status stays private until a correct password."""
    db_session.execute(text("update schools set status = 'suspended' where id = :id"), {"id": gmc})
    assert public(app, "GMC")[0] == 200
    status, answer = at_school(client_for(app), "GMC", "tunde.adebayo")
    assert (status, answer["code"]) == (403, "school_paused")
    assert at_school(client_for(app), "GMC", "tunde.adebayo", "wrong-password-here")[0] == 401


def test_an_unknown_code_is_not_found(app: FastAPI, gmc: uuid.UUID) -> None:
    status, answer = public(app, "XYZ")
    assert (status, answer["code"]) == (404, "school_not_found")


def test_an_old_code_forwards_for_thirty_days_but_never_logs_in(
    app: FastAPI, db_session: Session, gmc: uuid.UUID, people: dict[str, uuid.UUID]
) -> None:
    """AC24.4 (D-182): GMC becomes GMCE."""
    db_session.execute(text("update schools set code = 'GMCE' where id = :id"), {"id": gmc})
    assert public(app, "GMC")[1]["code"] == "GMCE"
    assert public(app, "GMCE")[1]["code"] == "GMCE"
    assert at_school(client_for(app), "GMC", "tunde.adebayo")[0] == 401
    assert at_school(client_for(app), "GMCE", "tunde.adebayo")[0] == 200

    db_session.execute(
        text("update school_code_changes set changed_at = now() - interval '31 days'")
    )
    assert public(app, "GMC")[0] == 404


def test_a_new_school_with_an_old_code_wins(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    """A code given up and taken by another school is that school's straight away."""
    db_session.execute(text("update schools set code = 'GMCE' where id = :id"), {"id": gmc})
    create_school(db_session, code="GMC", name="Golden Meadow College")
    assert public(app, "GMC")[1]["name"] == "Golden Meadow College"


def test_nobody_reads_the_old_codes(db_session: Session, gmc: uuid.UUID) -> None:
    """Only the owner-run trigger writes the list; the app roles cannot touch it."""
    db_session.execute(text("update schools set code = 'GMCE' where id = :id"), {"id": gmc})
    for role in ("app_user", "app_platform", "app_verifier", "app_sender"):
        with refused(db_session, "42501"):
            db_session.execute(text(f"set local role {role}"))
            db_session.execute(text("select * from school_code_changes"))


def test_the_login_message_is_short_and_one_line(db_session: Session, gmc: uuid.UUID) -> None:
    """F02 rule 12: up to 80 characters, one line; a photo picture needs a photo."""
    for change in (
        "login_message = :long",
        "login_message = 'Line one\nLine two'",
        "login_message = '   '",
        "login_picture = 'photo'",
        "login_layout = 'sideways'",
    ):
        with refused(db_session, "23514"):
            db_session.execute(
                text(f"update schools set {change} where id = :id"),  # noqa: S608 (fixed)
                {"id": gmc, "long": "x" * 81},
            )
