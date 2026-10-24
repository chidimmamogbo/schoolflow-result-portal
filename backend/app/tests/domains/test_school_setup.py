"""A school sets itself up (BUILD_PROMPT 9.2e, first part; SPEC F03, F04, F08 rule 0, F25).

Behaviour: school admins edit their contacts and colour (never the name,
code, features or levels), the assessment mode and head's title of levels
that are on (a mode change waits for next term once the term's entries
have started); they manage sessions and terms (one active term, terms
inside their session and never overlapping), classes and arms at levels
that are on, departments, subjects and the subjects each arm takes, always
inside their own school; only the principal adds and removes additional
admins, up to the platform limit; login support reaches the school's own
people, never the principal from inside the school, never an account
shared with another school, never another school's people; every change is
audited. Teachers and parents are refused. All data is fictional.
"""

import uuid
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.tests.auth_support import (
    build_auth_app,
    client_for,
    csrf,
    log_in,
    logged_in,
    make_login,
    use_fast_hashing,
)
from app.tests.db_support import acting_as, refused, violates
from app.tests.factories import (
    add_arm_subject,
    create_arm,
    create_class,
    create_school,
    create_session,
    create_structure,
    create_subject,
    create_term,
    parent_accepts_link,
)


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    return build_auth_app(db_session)


@pytest.fixture
def gmc(db_session: Session) -> dict[str, uuid.UUID]:
    school = create_school(db_session, code="GMC", name="Greenfield Model College")
    return {
        "school": school,
        "ngozi": make_login(
            db_session,
            username="ngozi.okeke",
            full_name="Ngozi Okeke",
            email="ngozi@gmc.example",
            school_id=school,
            role="school_admin",
            is_primary=True,
        ),
        "emeka": make_login(
            db_session,
            username="emeka.vp",
            full_name="Emeka Obi",
            email="emeka@gmc.example",
            school_id=school,
            role="school_admin",
        ),
        "tunde": make_login(
            db_session, username="tunde.adebayo", email="tunde@gmc.example", school_id=school
        ),
    }


@pytest.fixture
def principal(app: FastAPI, gmc: dict[str, uuid.UUID]) -> TestClient:
    return logged_in(app, "ngozi.okeke")


@pytest.fixture
def deputy(app: FastAPI, gmc: dict[str, uuid.UUID]) -> TestClient:
    return logged_in(app, "emeka.vp")


@pytest.fixture
def teacher(app: FastAPI, gmc: dict[str, uuid.UUID]) -> TestClient:
    return logged_in(app, "tunde.adebayo")


def send(client: TestClient, method: str, url: str, body: Any = None) -> tuple[int, Any]:
    response = client.request(method, f"/api/v1{url}", json=body, headers=csrf(client))
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def code_of(result: tuple[int, Any]) -> tuple[int, str | None]:
    status, body = result
    return status, cast(dict[str, Any], body or {}).get("code")


def actions(db_session: Session) -> list[str]:
    return sorted(db_session.scalars(text("select action from audit_events")))


# --- school settings and levels -----------------------------------------------------------


def test_school_admins_edit_contacts_and_colour_only(
    principal: TestClient, deputy: TestClient, teacher: TestClient, db_session: Session
) -> None:
    status, school = send(principal, "GET", "/school")
    assert status == 200
    assert (school["code"], school["name"]) == ("GMC", "Greenfield Model College")
    assert {lvl["level"]: lvl["enabled"] for lvl in school["levels"]} == {
        "nursery": False,
        "primary": False,
        "junior_secondary": True,
        "senior_secondary": True,
    }
    status, school = send(deputy, "PATCH", "/school", {"phone": "08099990000", "colour": "#0B5D3B"})
    assert status == 200, school
    assert (school["phone"], school["colour"]) == ("08099990000", "#0B5D3B")
    for body in ({"name": "New Name"}, {"code": "NEW"}, {"colour": "green"}, {"state": "Atlantis"}):
        assert send(principal, "PATCH", "/school", body)[0] == 422, body
    assert code_of(send(teacher, "PATCH", "/school", {"phone": "08011112222"})) == (
        403,
        "permission_denied",
    )
    assert actions(db_session) == ["school.update"]


def test_assessment_mode_and_head_title_per_level(
    principal: TestClient, teacher: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    """F08 rule 0, F12 rule 0, D-050."""
    status, body = send(
        principal,
        "PUT",
        "/school/levels/junior_secondary",
        {"assessment_mode": "skill_ratings", "head_title": "Head of school"},
    )
    assert status == 200, body
    assert body == {
        "level": "junior_secondary",
        "assessment_mode": "skill_ratings",
        "head_title": "Head of school",
        "applies_from": "this_term",
    }
    assert code_of(
        send(principal, "PUT", "/school/levels/nursery", {"head_title": "Proprietor"})
    ) == (404, "level_disabled")
    assert (
        send(principal, "PUT", "/school/levels/junior_secondary", {"assessment_mode": "grades"})[0]
        == 422
    )
    assert send(principal, "PUT", "/school/levels/junior_secondary", {"head_title": " "})[0] == 422
    assert code_of(
        send(teacher, "PUT", "/school/levels/junior_secondary", {"head_title": "Boss"})
    ) == (403, "permission_denied")

    # Once the term's entries have started, a mode change waits for next term (AC08.6).
    year = create_session(db_session, gmc["school"])
    term = create_term(db_session, gmc["school"], year, 1, is_active=True)
    structure = create_structure(db_session, gmc["school"], "senior_secondary", term)
    db_session.execute(
        text("update assessment_structures set locked_at = now() where id = :id"), {"id": structure}
    )
    status, body = send(
        principal, "PUT", "/school/levels/senior_secondary", {"assessment_mode": "skill_ratings"}
    )
    assert (status, body["applies_from"]) == (200, "next_term")
    assert (
        db_session.scalar(
            text("select assessment_mode from assessment_structures where id = :id"),
            {"id": structure},
        )
        == "scores"
    )


# --- sessions and terms ------------------------------------------------------------------


def test_sessions_and_terms(principal: TestClient, teacher: TestClient) -> None:
    """F04, AC04.1: one active term; terms inside their session, never overlapping."""
    status, year = send(
        principal,
        "POST",
        "/school/sessions",
        {"name": "2026/2027", "starts_on": "2026-09-07", "ends_on": "2027-07-23"},
    )
    assert status == 201, year
    assert (
        send(
            principal,
            "POST",
            "/school/sessions",
            {"name": "2026/2028", "starts_on": "2026-09-07", "ends_on": "2027-07-23"},
        )[0]
        == 422
    )
    assert code_of(
        send(
            principal,
            "POST",
            "/school/sessions",
            {"name": "2027/2028", "starts_on": "2027-07-01", "ends_on": "2028-07-20"},
        )
    ) == (409, "sessions_overlap")

    terms = f"/school/sessions/{year['id']}/terms"
    status, first = send(
        principal,
        "POST",
        terms,
        {
            "term_number": 1,
            "starts_on": "2026-09-08",
            "ends_on": "2026-12-11",
            "next_term_begins": "2027-01-05",
        },
    )
    assert status == 201, first
    status, second = send(
        principal,
        "POST",
        terms,
        {"term_number": 2, "starts_on": "2027-01-05", "ends_on": "2027-04-02"},
    )
    assert status == 201
    assert code_of(
        send(
            principal,
            "POST",
            terms,
            {"term_number": 3, "starts_on": "2027-03-30", "ends_on": "2027-07-20"},
        )
    ) == (409, "terms_overlap")
    assert code_of(
        send(
            principal,
            "POST",
            terms,
            {"term_number": 3, "starts_on": "2027-04-26", "ends_on": "2027-08-20"},
        )
    ) == (422, "term_outside_session")
    assert (
        send(
            principal,
            "POST",
            terms,
            {"term_number": 4, "starts_on": "2027-04-26", "ends_on": "2027-07-20"},
        )[0]
        == 422
    )

    assert send(principal, "POST", f"/school/terms/{first['id']}/activate")[0] == 200
    assert send(principal, "POST", f"/school/terms/{second['id']}/activate")[0] == 200
    status, listing = send(teacher, "GET", "/school/sessions")
    assert status == 200  # everyone in the school reads the calendar
    active = [t["term_number"] for s in listing for t in s["terms"] if t["is_active"]]
    assert active == [2]
    status, changed = send(
        principal, "PATCH", f"/school/terms/{first['id']}", {"next_term_begins": "2027-01-06"}
    )
    assert (status, changed["next_term_begins"]) == (200, "2027-01-06")
    assert code_of(
        send(
            teacher,
            "POST",
            "/school/sessions",
            {"name": "2030/2031", "starts_on": "2030-09-01", "ends_on": "2031-07-01"},
        )
    ) == (403, "permission_denied")


# --- classes, arms, departments and subjects -------------------------------------------------


def test_classes_and_arms_only_at_levels_that_are_on(
    principal: TestClient, db_session: Session
) -> None:
    """F04, AC04.2, AT-04.2."""
    status, jss1 = send(
        principal, "POST", "/school/classes", {"level": "junior_secondary", "name": "JSS 1"}
    )
    assert status == 201, jss1
    assert code_of(
        send(principal, "POST", "/school/classes", {"level": "primary", "name": "Primary 1"})
    ) == (404, "level_disabled")
    assert code_of(
        send(principal, "POST", "/school/classes", {"level": "junior_secondary", "name": "jss 1"})
    ) == (409, "name_taken")
    arms = f"/school/classes/{jss1['id']}/arms"
    status, arm_a = send(principal, "POST", arms, {"name": "A"})
    assert status == 201
    assert send(principal, "POST", arms, {"name": "B"})[0] == 201
    assert code_of(send(principal, "POST", arms, {"name": "a"})) == (409, "name_taken")
    status, listing = send(principal, "GET", "/school/classes")
    assert [(c["name"], [a["name"] for a in c["arms"]]) for c in listing] == [("JSS 1", ["A", "B"])]
    status, renamed = send(principal, "PATCH", f"/school/classes/{jss1['id']}", {"name": "JSS One"})
    assert (status, renamed["name"]) == (200, "JSS One")
    assert send(principal, "DELETE", f"/school/arms/{arm_a['id']}")[0] == 204
    assert "classes.create" in actions(db_session)


def test_departments_subjects_and_what_each_arm_takes(
    principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    status, sciences = send(principal, "POST", "/school/departments", {"name": "Sciences"})
    assert status == 201
    status, maths = send(
        principal,
        "POST",
        "/school/subjects",
        {
            "name": "Mathematics",
            "department_id": sciences["id"],
            "category": "Science and Mathematics",
        },
    )
    assert status == 201, maths
    status, english = send(principal, "POST", "/school/subjects", {"name": "English Language"})
    assert code_of(send(principal, "POST", "/school/subjects", {"name": "mathematics"})) == (
        409,
        "name_taken",
    )
    jss1 = create_class(db_session, gmc["school"], "junior_secondary", "JSS 1")
    arm = create_arm(db_session, gmc["school"], jss1, "A")

    url = f"/school/arms/{arm}/subjects"
    status, taken = send(principal, "PUT", url, {"subject_ids": [maths["id"], english["id"]]})
    assert status == 200
    assert sorted(s["name"] for s in taken) == ["English Language", "Mathematics"]
    status, taken = send(principal, "PUT", url, {"subject_ids": [english["id"]]})
    assert [s["name"] for s in taken] == ["English Language"]
    # A subject in use cannot be deleted; an unused one can.
    assert code_of(send(principal, "DELETE", f"/school/subjects/{english['id']}"))[0] == 409
    assert send(principal, "DELETE", f"/school/subjects/{maths['id']}")[0] == 204
    status, listing = send(principal, "GET", "/school/subjects")
    assert [s["name"] for s in listing] == ["English Language"]


def test_another_schools_records_are_not_found(principal: TestClient, db_session: Session) -> None:
    """AC01.2, AT-06.4: ids from BSA are simply not found at GMC."""
    bsa = create_school(
        db_session, code="BSA", name="Bright Stars Academy", school_type="nursery_primary"
    )
    year = create_session(db_session, bsa)
    term = create_term(db_session, bsa, year, 1)
    pry1 = create_class(db_session, bsa, "primary", "Primary 1")
    arm = create_arm(db_session, bsa, pry1, "A")
    subject = create_subject(db_session, bsa, "Basic Science")
    add_arm_subject(db_session, bsa, arm, subject)
    attempts: list[tuple[str, str, Any]] = [
        ("PATCH", f"/school/classes/{pry1}", {"name": "Mine now"}),
        ("DELETE", f"/school/classes/{pry1}", None),
        ("POST", f"/school/classes/{pry1}/arms", {"name": "Z"}),
        ("PATCH", f"/school/arms/{arm}", {"name": "Z"}),
        ("PUT", f"/school/arms/{arm}/subjects", {"subject_ids": []}),
        ("PATCH", f"/school/subjects/{subject}", {"name": "Mine"}),
        (
            "POST",
            f"/school/sessions/{year}/terms",
            {"term_number": 2, "starts_on": "2027-01-05", "ends_on": "2027-04-02"},
        ),
        ("POST", f"/school/terms/{term}/activate", None),
    ]
    for method, url, body in attempts:
        assert send(principal, method, url, body)[0] == 404, url
    own_class = create_class(
        db_session,
        db_session.scalar(text("select id from schools where code = 'GMC'")),
        "junior_secondary",
        "JSS 1",
    )
    own_arm = create_arm(
        db_session,
        db_session.scalar(text("select id from schools where code = 'GMC'")),
        own_class,
        "A",
    )
    assert (
        send(principal, "PUT", f"/school/arms/{own_arm}/subjects", {"subject_ids": [str(subject)]})[
            0
        ]
        == 404
    )
    assert db_session.scalar(text("select name from classes where id = :id"), {"id": pry1}) == (
        "Primary 1"
    )


# --- additional school admins (F03 rule 2) ----------------------------------------------------


def test_only_the_principal_adds_admins_up_to_the_limit(
    app: FastAPI, principal: TestClient, deputy: TestClient, db_session: Session
) -> None:
    """AT-06.5, AT-06.6, AC03.1, AC03.4."""
    status, admins = send(deputy, "GET", "/school/admins")
    assert status == 200
    assert admins["places_left"] == 1
    assert [(a["username"], a["is_primary"]) for a in admins["admins"]] == [
        ("ngozi.okeke", True),
        ("emeka.vp", False),
    ]
    new_admin = {
        "full_name": "Bisi Ade",
        "username": "bisi.ade",
        "email": "bisi@gmc.example",
        "login_method": "activation",
    }
    assert code_of(send(deputy, "POST", "/school/admins", new_admin)) == (403, "permission_denied")
    status, created = send(principal, "POST", "/school/admins", new_admin)
    assert status == 201, created
    assert created["temporary_password"] is None
    assert (
        db_session.scalar(
            text(
                "select count(*) from email_outbox where template = 'activation'"
                " and to_address = 'bisi@gmc.example'"
            )
        )
        == 1
    )
    status, body = send(
        principal,
        "POST",
        "/school/admins",
        {
            "full_name": "Chi Uzo",
            "username": "chi.uzo",
            "email": "chi@gmc.example",
            "login_method": "temporary_password",
        },
    )
    assert (status, body["code"]) == (409, "admin_limit")
    assert body["title"] == "You can add up to 2 school admins."


def test_admins_with_a_slip_taken_names_and_removal(
    app: FastAPI,
    principal: TestClient,
    deputy: TestClient,
    db_session: Session,
    gmc: dict[str, uuid.UUID],
) -> None:
    db_session.execute(
        text("delete from school_memberships where user_id = :id"), {"id": gmc["emeka"]}
    )
    status, created = send(
        principal,
        "POST",
        "/school/admins",
        {"full_name": "Chi Uzo", "username": "chi.uzo", "login_method": "temporary_password"},
    )
    assert status == 201, created
    slip = created["temporary_password"]
    assert len(slip.split("-")) == 4
    assert log_in(client_for(app), "chi.uzo", slip) == 200
    assert code_of(
        send(
            principal,
            "POST",
            "/school/admins",
            {"full_name": "X", "username": "tunde.adebayo", "login_method": "temporary_password"},
        )
    ) == (409, "username_taken")
    assert code_of(
        send(
            principal,
            "POST",
            "/school/admins",
            {
                "full_name": "X",
                "username": "x.y",
                "email": "tunde@gmc.example",
                "login_method": "activation",
            },
        )
    ) == (409, "email_taken")
    assert (
        send(
            principal,
            "POST",
            "/school/admins",
            {"full_name": "X", "username": "x.z", "login_method": "activation"},
        )[0]
        == 422
    )

    assert send(principal, "DELETE", f"/school/admins/{created['id']}")[0] == 204
    assert log_in(client_for(app), "chi.uzo", slip) == 403  # no school any more
    assert send(principal, "DELETE", f"/school/admins/{gmc['ngozi']}")[0] == 404
    assert send(principal, "DELETE", f"/school/admins/{gmc['tunde']}")[0] == 404
    assert {"school_admins.create", "school_admins.remove"} <= set(actions(db_session))


# --- login support for the school's people (F03 rule 6) ---------------------------------------


def test_a_temporary_password_for_a_pupil(
    app: FastAPI, deputy: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    """AT-28.3: shown once; other sessions end; changed at next login; never audited."""
    pupil = make_login(
        db_session, username="chukwuemeka.obi", school_id=gmc["school"], student=True
    )
    pupil_phone = logged_in(app, "chukwuemeka.obi", school_code="GMC")
    status, body = send(deputy, "POST", f"/school/people/{pupil}/temporary-password")
    assert status == 201
    slip = body["temporary_password"]
    assert pupil_phone.get("/api/v1/auth/me").status_code == 401
    stored = db_session.scalar(
        text("select password_hash from users where id = :id"), {"id": pupil}
    )
    assert verify_password(slip, stored)[0]
    audit = db_session.execute(
        text(
            "select actor_role, old_values, new_values from audit_events"
            " where action = 'users.temporary_password'"
        )
    ).one()
    assert audit.actor_role == "school_admin"
    assert slip not in str(tuple(audit))
    client = client_for(app)
    assert log_in(client, "chukwuemeka.obi", slip, school_code="GMC") == 200
    assert client.get("/api/v1/auth/me").json()["must_change_password"] is True


def test_reset_link_sign_out_deactivate_and_reactivate(
    app: FastAPI, principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    tunde_phone = logged_in(app, "tunde.adebayo")
    base = f"/school/people/{gmc['tunde']}"
    status, body = send(principal, "POST", f"{base}/send-reset-link", {"sign_out_all": True})
    assert status == 202, body
    assert tunde_phone.get("/api/v1/auth/me").status_code == 401
    assert (
        db_session.scalar(
            text("select to_address from email_outbox where template = 'password_reset'")
        )
        == "tunde@gmc.example"
    )
    tunde_phone = logged_in(app, "tunde.adebayo")
    assert send(principal, "POST", f"{base}/sign-out-all")[0] == 204
    assert tunde_phone.get("/api/v1/auth/me").status_code == 401
    logged_in(app, "tunde.adebayo")
    assert send(principal, "POST", f"{base}/deactivate")[0] == 204
    assert (
        db_session.scalar(
            text("select count(*) from user_sessions where user_id = :id"), {"id": gmc["tunde"]}
        )
        == 0
    )
    assert log_in(client_for(app), "tunde.adebayo") == 401
    assert send(principal, "POST", f"{base}/reactivate")[0] == 204
    assert log_in(client_for(app), "tunde.adebayo") == 200
    assert code_of(send(principal, "POST", f"{base}/resend-activation")) == (
        409,
        "already_activated",
    )
    no_email = make_login(db_session, username="no.mail", school_id=gmc["school"])
    assert code_of(
        send(
            principal, "POST", f"/school/people/{no_email}/send-reset-link", {"sign_out_all": False}
        )
    ) == (409, "no_email")


def test_login_support_respects_who_may_reset_whom(
    principal: TestClient,
    deputy: TestClient,
    teacher: TestClient,
    db_session: Session,
    gmc: dict[str, uuid.UUID],
) -> None:
    """F03 rules 2, 5, 9; D-048; AC03.9."""
    action = "sign-out-all"
    # Additional admins never reset another admin; the principal resets additional admins.
    assert code_of(send(deputy, "POST", f"/school/people/{gmc['ngozi']}/{action}")) == (
        403,
        "permission_denied",
    )
    assert send(principal, "POST", f"/school/people/{gmc['emeka']}/{action}")[0] == 204
    # Nobody in the school resets the principal; the super admin does (F03 rule 5).
    assert code_of(send(principal, "POST", f"/school/people/{gmc['ngozi']}/{action}")) == (
        409,
        "own_account",
    )
    # Teachers have no login support at all.
    assert code_of(send(teacher, "POST", f"/school/people/{gmc['emeka']}/{action}")) == (
        403,
        "permission_denied",
    )

    # A parent linked to two schools is managed only by the parent (D-138).
    bsa = create_school(db_session, code="BSA", name="Bright Stars Academy")
    parent = make_login(
        db_session,
        username="ikenna.obi",
        email="ikenna@home.example",
        school_id=gmc["school"],
        role="parent",
    )
    parent_accepts_link(db_session, parent, bsa)
    for shared_action in ("temporary-password", "deactivate", "sign-out-all"):
        assert code_of(send(principal, "POST", f"/school/people/{parent}/{shared_action}")) == (
            403,
            "shared_account",
        )
    # Another school's people are not found.
    stranger = make_login(db_session, username="bsa.teacher", school_id=bsa)
    assert send(principal, "POST", f"/school/people/{stranger}/{action}")[0] == 404
    assert db_session.scalar(text("select count(*) from users where must_change_password")) == 0


def test_the_database_lets_only_school_admins_edit_these_columns(
    db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    """Migration 22: a second wall behind the API's permission checks."""
    school = gmc["school"]
    with acting_as(db_session, "app_user", school_id=school, user_id=gmc["tunde"]):
        with violates(db_session, "school_settings_by_school_admin"):
            db_session.execute(text("update schools set colour = '#000000'"))
        with violates(db_session, "school_settings_by_school_admin"):
            db_session.execute(text("update school_levels set head_title = 'Boss'"))
    with acting_as(db_session, "app_user", school_id=school, user_id=gmc["ngozi"]):
        db_session.execute(text("update schools set colour = '#000000'"))
        db_session.execute(text("update school_levels set head_title = 'Proprietor'"))
        for refused_change in (
            "update schools set name = 'Renamed'",
            "update schools set code = 'NEW'",
            "update schools set status = 'suspended'",
            "update school_levels set enabled = true",
        ):
            with refused(db_session):
                db_session.execute(text(refused_change))
    other = create_school(db_session, code="BSA", name="Bright Stars Academy")
    with acting_as(db_session, "app_user", school_id=school, user_id=gmc["ngozi"]):
        changed = db_session.execute(
            text("update schools set colour = '#111111' where id = :id returning id"),
            {"id": other},
        ).first()
        assert changed is None  # another school's row is not even visible
