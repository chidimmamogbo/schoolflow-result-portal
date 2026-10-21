"""The super admin's platform pages (BUILD_PROMPT 9.2d; SPEC F03 rule 5, F24, F25).

Behaviour: only the super admin reaches /platform; creating a school makes
the school, its features, report card levels from the school type, its
subscription, the principal (activated by an emailed link, no password
sent) and two queued emails, all audited, and refuses a taken code; the
super admin edits details, changes the code (confirmed; the old code stops
working), suspends with a reason and reactivates, switches features and
levels (at least one level on; confirmation naming the classes with
unpublished results), sees usage and activity; login support reaches school
admins only (email, reset link, temporary password shown once, sign out,
deactivate, reactivate, make principal), never other roles and never "log
in as"; platform settings are validated and audited; logs show status only.
Platform work runs as app_platform. All data is fictional.
"""

import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.auth.passwords import hash_password, verify_password
from schoolflow_api.platform.deps import PlatformDb
from tests.auth_support import (
    PASSWORD,
    STUDENT_PASSWORD,
    build_platform_app,
    client_for,
    csrf,
    log_in,
    logged_in,
    make_login,
    use_fast_hashing,
)
from tests.db_support import acting_as, refused
from tests.factories import (
    add_arm_subject,
    create_arm,
    create_class,
    create_school,
    create_session,
    create_sheet,
    create_structure,
    create_student,
    create_subject,
    create_term,
)

ALL_FEATURES = {
    "results": True,
    "report_cards": True,
    "parent_portal": True,
    "correction_queue": True,
    "notice_board": True,
    "email_notifications": True,
}


def school_form(**changes: Any) -> dict[str, Any]:
    form: dict[str, Any] = {
        "name": "Greenfield Model College",
        "email": "office@gmc.example",
        "phone": "08010000001",
        "address": "12 Unity Road",
        "city": "Enugu",
        "state": "Enugu",
        "country": "Nigeria",
        "code": "GMC",
        "school_type": "secondary_only",
        "colour": "#1E6B45",
        "features": dict(ALL_FEATURES),
        "billing": "on",
        "principal": {
            "full_name": "Ngozi Okeke",
            "username": "ngozi.okeke",
            "email": "ngozi@gmc.example",
        },
    }
    form.update(changes)
    return form


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    return build_platform_app(db_session)


@pytest.fixture
def owner(app: FastAPI, db_session: Session) -> TestClient:
    make_login(db_session, username="platform.owner", full_name="Ada Platform", is_super_admin=True)
    return logged_in(app, "platform.owner")


def send(client: TestClient, method: str, url: str, body: Any = None) -> tuple[int, Any]:
    response = client.request(method, f"/api/v1{url}", json=body, headers=csrf(client))
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def create(client: TestClient, **changes: Any) -> uuid.UUID:
    status, body = send(client, "POST", "/platform/schools", school_form(**changes))
    assert status == 201, body
    return uuid.UUID(body["id"])


def audit_actions(db_session: Session, school_id: uuid.UUID | None = None) -> list[str]:
    return list(
        db_session.scalars(
            text(
                "select action from audit_events where school_id is not distinct from :s"
                " order by created_at, action"
            ),
            {"s": school_id},
        )
    )


# --- creating a school ----------------------------------------------------------------


def test_the_super_admin_creates_a_school_with_its_principal(
    owner: TestClient, db_session: Session
) -> None:
    """AT-01.1, AC24.2, AC25.1."""
    school_id = create(owner)
    school = db_session.execute(
        text("select code, status, school_type from schools where id = :id"), {"id": school_id}
    ).one()
    assert tuple(school) == ("GMC", "active", "secondary_only")
    levels = dict(
        db_session.execute(
            text("select level, enabled from school_levels where school_id = :id"),
            {"id": school_id},
        ).all()
    )
    assert levels == {
        "nursery": False,
        "primary": False,
        "junior_secondary": True,
        "senior_secondary": True,
    }
    features = dict(
        db_session.execute(
            text("select feature, enabled from school_features where school_id = :id"),
            {"id": school_id},
        ).all()
    )
    assert features == ALL_FEATURES
    subscription = db_session.execute(
        text("select billing_enabled, status from school_subscriptions where school_id = :id"),
        {"id": school_id},
    ).one()
    assert tuple(subscription) == (True, "active")

    principal = db_session.execute(
        text(
            "select u.id, u.full_name, u.email, u.password_hash, m.role, m.is_primary"
            " from users u join school_memberships m on m.user_id = u.id"
            " where u.username = 'ngozi.okeke'"
        )
    ).one()
    assert (principal.full_name, principal.email) == ("Ngozi Okeke", "ngozi@gmc.example")
    assert (principal.role, principal.is_primary) == ("school_admin", True)
    assert principal.password_hash is None  # set by the person, from the link

    emails = db_session.execute(
        text(
            "select template, to_address, template_data, school_id from email_outbox"
            " order by template"
        )
    ).all()
    assert [(e.template, e.to_address) for e in emails] == [
        ("activation", "ngozi@gmc.example"),
        ("school_setup", "office@gmc.example"),
    ]
    assert all(e.school_id == school_id for e in emails)
    assert emails[0].template_data == {
        "user_id": str(principal.id),
        "full_name": "Ngozi Okeke",
        "username": "ngozi.okeke",
        "school_code": "GMC",
        "school_name": "Greenfield Model College",
    }
    assert emails[1].template_data == {
        "school_name": "Greenfield Model College",
        "school_code": "GMC",
        "login_path": "/login/GMC",
    }
    assert "password" not in str([e.template_data for e in emails]).lower()
    assert audit_actions(db_session, school_id) == ["schools.create"]


def test_a_nursery_and_primary_school_on_a_free_pilot(
    owner: TestClient, db_session: Session
) -> None:
    """AT-02.1: the preset levels and their modes; billing as free pilot."""
    features = dict(ALL_FEATURES, correction_queue=False)
    school_id = create(
        owner,
        code="BSA",
        name="Bright Stars Academy",
        email="hello@bsa.example",
        school_type="nursery_primary",
        billing="free_pilot",
        features=features,
        principal={
            "full_name": "Chiamaka Nwafor",
            "username": "chiamaka.nwafor",
            "email": "chiamaka@bsa.example",
        },
    )
    levels = {
        row.level: (row.enabled, row.assessment_mode)
        for row in db_session.execute(
            text("select level, enabled, assessment_mode from school_levels where school_id = :id"),
            {"id": school_id},
        )
    }
    assert levels["nursery"] == (True, "skill_ratings")
    assert levels["primary"] == (True, "scores")
    assert levels["junior_secondary"][0] is False
    assert (
        db_session.scalar(
            text("select status from school_subscriptions where school_id = :id"), {"id": school_id}
        )
        == "free_pilot"
    )
    assert (
        db_session.scalar(
            text(
                "select enabled from school_features where school_id = :id"
                " and feature = 'correction_queue'"
            ),
            {"id": school_id},
        )
        is False
    )


def test_a_taken_school_code_is_refused(owner: TestClient, db_session: Session) -> None:
    """AT-01.2, AC24.1: a field error on School code; nothing is created."""
    create(owner)
    status, body = send(
        owner,
        "POST",
        "/platform/schools",
        school_form(
            code="gmc",
            principal={
                "full_name": "Another Head",
                "username": "another.head",
                "email": "head@other.example",
            },
        ),
    )
    assert (status, body["code"]) == (409, "code_taken")
    assert body["errors"] == [
        {"loc": ["body", "code"], "msg": "This school code is taken.", "type": "code_taken"}
    ]
    assert db_session.scalar(text("select count(*) from schools")) == 1
    assert (
        db_session.scalar(text("select count(*) from users where username = 'another.head'")) == 0
    )


def test_a_taken_principal_username_or_email_is_refused(
    owner: TestClient, db_session: Session
) -> None:
    other = create_school(db_session, code="RCS", name="Royal Crest Schools")
    make_login(db_session, username="ngozi.okeke", email="someone@else.example", school_id=other)
    status, body = send(owner, "POST", "/platform/schools", school_form())
    assert (status, body["code"]) == (409, "username_taken")
    principal = {"full_name": "Ngozi Okeke", "username": "ngozi.o", "email": "someone@else.example"}
    status, body = send(owner, "POST", "/platform/schools", school_form(principal=principal))
    assert (status, body["code"]) == (409, "email_taken")
    assert db_session.scalar(text("select count(*) from schools where code = 'GMC'")) == 0


def test_the_form_is_checked(owner: TestClient) -> None:
    """F24 rule 1: code format, colour, Nigerian state, every feature named."""
    bad = [
        school_form(code="G"),
        school_form(code="GMC-1"),
        school_form(colour="green"),
        school_form(state="Atlantis"),
        school_form(features={"results": True}),
        school_form(school_type="custom"),
        school_form(billing="maybe"),
        school_form(principal={"full_name": "N O", "username": "Bad Name", "email": "x@y.example"}),
        {**school_form(), "status": "suspended"},
    ]
    for form in bad:
        status, _ = send(owner, "POST", "/platform/schools", form)
        assert status == 422, form
    status, _ = send(
        owner, "POST", "/platform/schools", school_form(country="Ghana", state="Greater Accra")
    )
    assert status == 201


def test_only_the_super_admin_reaches_the_platform(
    app: FastAPI, owner: TestClient, db_session: Session
) -> None:
    """AT-01.3, AT-02.3, AC25.2."""
    school_id = create(owner)
    db_session.execute(
        text("update users set password_hash = :h where username = 'ngozi.okeke'"),
        {"h": hash_password(PASSWORD)},
    )
    principal = logged_in(app, "ngozi.okeke")
    for method, url, body in (
        ("GET", "/platform/schools", None),
        ("POST", "/platform/schools", school_form(code="NEW")),
        (
            "PUT",
            f"/platform/schools/{school_id}/levels",
            {"nursery": True, "primary": False, "secondary": True},
        ),
        ("GET", "/platform/settings", None),
        ("GET", "/platform/audit-log", None),
    ):
        status, response = send(principal, method, url, body)
        assert (status, response["code"]) == (403, "permission_denied"), url


def test_code_and_username_checks(owner: TestClient, db_session: Session) -> None:
    """F24 rule 1: checked as you type; student usernames are per school, so not taken."""
    create(owner)
    other = create_school(db_session, code="RCS", name="Royal Crest Schools")
    make_login(db_session, username="tunde.adebayo", school_id=other)
    make_login(db_session, username="ada.pupil", school_id=other, student=True)
    assert send(owner, "GET", "/platform/schools/check-code?code=gmc")[1] == {"available": False}
    assert send(owner, "GET", "/platform/schools/check-code?code=NEW1")[1] == {"available": True}
    assert send(owner, "GET", "/platform/schools/check-code?code=x")[0] == 422
    check = "/platform/usernames/check?username="
    assert send(owner, "GET", check + "tunde.adebayo")[1] == {"available": False}
    assert send(owner, "GET", check + "ada.pupil")[1] == {"available": True}
    assert send(owner, "GET", check + "fresh.name")[1] == {"available": True}
    assert send(owner, "GET", check + "No Spaces")[0] == 422


# --- schools: list, detail, edit, code, suspend -----------------------------------------------


def test_list_and_detail(owner: TestClient) -> None:
    gmc = create(owner)
    create(
        owner,
        code="BSA",
        name="Bright Stars Academy",
        email="hello@bsa.example",
        school_type="nursery_primary",
        principal={
            "full_name": "Chiamaka Nwafor",
            "username": "chiamaka.nwafor",
            "email": "chiamaka@bsa.example",
        },
    )
    status, listing = send(owner, "GET", "/platform/schools")
    assert status == 200
    assert [s["code"] for s in listing] == ["BSA", "GMC"]
    assert [s["code"] for s in send(owner, "GET", "/platform/schools?q=green")[1]] == ["GMC"]
    assert send(owner, "GET", "/platform/schools?status=suspended")[1] == []

    status, detail = send(owner, "GET", f"/platform/schools/{gmc}")
    assert status == 200
    assert detail["name"] == "Greenfield Model College"
    assert detail["features"] == ALL_FEATURES
    assert detail["levels"] == {"nursery": False, "primary": False, "secondary": True}
    assert detail["subscription"] == {"billing_enabled": True, "status": "active"}
    assert send(owner, "GET", f"/platform/schools/{uuid.uuid4()}")[0] == 404


def test_editing_details_is_validated_and_audited(owner: TestClient, db_session: Session) -> None:
    gmc = create(owner)
    status, body = send(
        owner,
        "PATCH",
        f"/platform/schools/{gmc}",
        {"name": "Greenfield Model College, Enugu", "colour": "#0B5D3B"},
    )
    assert status == 200, body
    assert (body["name"], body["colour"]) == ("Greenfield Model College, Enugu", "#0B5D3B")
    assert send(owner, "PATCH", f"/platform/schools/{gmc}", {"colour": "#12"})[0] == 422
    assert send(owner, "PATCH", f"/platform/schools/{gmc}", {"code": "NEW"})[0] == 422
    old, new = db_session.execute(
        text("select old_values, new_values from audit_events where action = 'schools.update'")
    ).one()
    assert old == {"name": "Greenfield Model College", "colour": "#1E6B45"}
    assert new == {"name": "Greenfield Model College, Enugu", "colour": "#0B5D3B"}


def test_changing_the_code_needs_confirmation_and_ends_the_old_code(
    app: FastAPI, owner: TestClient, db_session: Session
) -> None:
    """AC24.4."""
    gmc = create(owner)
    make_login(
        db_session, username="ada.pupil", school_id=gmc, student=True, password=STUDENT_PASSWORD
    )
    url = f"/platform/schools/{gmc}/change-code"
    status, body = send(owner, "POST", url, {"code": "GMCE"})
    assert (status, body["code"]) == (409, "confirmation_needed")
    status, body = send(owner, "POST", url, {"code": "GMCE", "confirm": True})
    assert status == 200, body
    assert log_in(client_for(app), "ada.pupil", STUDENT_PASSWORD, school_code="GMC") == 401
    assert log_in(client_for(app), "ada.pupil", STUDENT_PASSWORD, school_code="GMCE") == 200
    other = create(
        owner,
        code="RCS",
        name="Royal Crest Schools",
        email="info@rcs.example",
        principal={"full_name": "Femi Ade", "username": "femi.ade", "email": "femi@rcs.example"},
    )
    status, body = send(
        owner, "POST", f"/platform/schools/{other}/change-code", {"code": "gmce", "confirm": True}
    )
    assert (status, body["code"]) == (409, "code_taken")
    assert "schools.change_code" in audit_actions(db_session, gmc)


def test_suspending_needs_a_reason_and_pauses_logins(
    app: FastAPI, owner: TestClient, db_session: Session
) -> None:
    """AC24.3, AT-X.2."""
    gmc = create(owner)
    make_login(db_session, username="tunde.adebayo", school_id=gmc)
    teacher = logged_in(app, "tunde.adebayo")
    url = f"/platform/schools/{gmc}"
    assert send(owner, "POST", f"{url}/suspend", {})[0] == 422
    assert send(owner, "POST", f"{url}/suspend", {"reason": "   "})[0] == 422
    assert send(owner, "POST", f"{url}/suspend", {"reason": "Unpaid for two terms"})[0] == 204
    assert teacher.get("/api/v1/auth/me").json()["code"] == "school_paused"
    assert log_in(client_for(app), "tunde.adebayo") == 403
    reason = db_session.scalar(
        text("select reason from audit_events where action = 'schools.suspend'")
    )
    assert reason == "Unpaid for two terms"
    assert send(owner, "POST", f"{url}/reactivate", {})[0] == 204
    assert teacher.get("/api/v1/auth/me").status_code == 200


def test_the_set_up_email_can_be_sent_again(owner: TestClient, db_session: Session) -> None:
    gmc = create(owner)
    assert send(owner, "POST", f"/platform/schools/{gmc}/resend-setup-email")[0] == 202
    assert (
        db_session.scalar(text("select count(*) from email_outbox where template = 'school_setup'"))
        == 2
    )


# --- features and report card levels ------------------------------------------------------


def test_features_are_switched_and_audited(owner: TestClient, db_session: Session) -> None:
    gmc = create(owner)
    url = f"/platform/schools/{gmc}/features"
    status, body = send(owner, "PUT", url, dict(ALL_FEATURES, results=False))
    assert status == 200
    assert body["results"] is False
    assert send(owner, "PUT", url, {"results": False})[0] == 422
    assert send(owner, "PUT", url, dict(ALL_FEATURES, billing=True))[0] == 422
    old, new = db_session.execute(
        text("select old_values, new_values from audit_events where action = 'features.update'")
    ).one()
    assert (old, new) == ({"results": True}, {"results": False})


def test_levels_follow_the_toggles_and_keep_one_on(owner: TestClient, db_session: Session) -> None:
    """F25 rules 2 and 5, AT-02.2, AC25.5."""
    gmc = create(owner)
    url = f"/platform/schools/{gmc}/levels"
    status, body = send(owner, "PUT", url, {"nursery": False, "primary": False, "secondary": False})
    assert (status, body["code"]) == (422, "at_least_one_level")
    status, body = send(owner, "PUT", url, {"nursery": False, "primary": True, "secondary": True})
    assert status == 200, body
    assert body == {
        "levels": {"nursery": False, "primary": True, "secondary": True},
        "school_type": "custom",
    }
    status, body = send(owner, "PUT", url, {"nursery": True, "primary": True, "secondary": True})
    assert body["school_type"] == "all_levels"
    assert (
        db_session.scalar(text("select school_type from schools where id = :id"), {"id": gmc})
        == "all_levels"
    )
    assert audit_actions(db_session, gmc).count("report_card_levels.update") == 2


def test_turning_off_a_level_with_unpublished_results_needs_confirmation(
    owner: TestClient, db_session: Session
) -> None:
    """F25 rule 5, AT-04.3: the confirmation names the classes; data is kept."""
    gmc = create(owner)
    year = create_session(db_session, gmc)
    term = create_term(db_session, gmc, year, 1, is_active=True)
    jss1 = create_class(db_session, gmc, "junior_secondary", "JSS 1")
    arm = create_arm(db_session, gmc, jss1, "A")
    maths = create_subject(db_session, gmc, "Mathematics")
    add_arm_subject(db_session, gmc, arm, maths)
    structure = create_structure(db_session, gmc, "junior_secondary", term)
    create_sheet(db_session, gmc, term, arm, structure, maths)

    url = f"/platform/schools/{gmc}/levels"
    change = {"nursery": False, "primary": True, "secondary": False}
    status, body = send(owner, "PUT", url, change)
    assert (status, body["code"]) == (409, "confirmation_needed")
    assert body["detail"] == "Unpublished results this term: JSS 1."
    status, body = send(owner, "PUT", url, {**change, "confirm": True})
    assert status == 200
    assert db_session.scalar(text("select count(*) from result_sheets")) == 1


# --- usage and activity --------------------------------------------------------------------


def test_usage_counts_without_reading_pupils_records(
    owner: TestClient, db_session: Session
) -> None:
    """F24 rule 2 (D-051: the platform role cannot read pupils, so a narrow function counts)."""
    gmc = create(owner)
    make_login(db_session, username="tunde.adebayo", school_id=gmc)
    make_login(db_session, username="ikenna.obi", school_id=gmc, role="parent")
    create_student(db_session, gmc, "GMC/2026/014", "Obi", "Chukwuemeka")
    create_student(db_session, gmc, "GMC/2026/015", "Ibrahim", "Musa")
    status, usage = send(owner, "GET", f"/platform/schools/{gmc}/usage")
    assert status == 200
    assert {k: usage[k] for k in ("students", "staff", "parents", "results_published")} == {
        "students": 2,
        "staff": 2,
        "parents": 1,
        "results_published": 0,
    }
    assert usage["last_activity"] is not None  # the creation itself


def test_activity_lists_the_schools_platform_events(owner: TestClient) -> None:
    gmc = create(owner)
    send(owner, "POST", f"/platform/schools/{gmc}/suspend", {"reason": "Testing"})
    status, events = send(owner, "GET", f"/platform/schools/{gmc}/activity")
    assert status == 200
    # One test transaction gives every event the same time, so compare as a set.
    assert sorted(e["action"] for e in events) == ["schools.create", "schools.suspend"]
    suspended = next(e for e in events if e["action"] == "schools.suspend")
    assert (suspended["reason"], suspended["actor_name"]) == ("Testing", "Ada Platform")


# --- school admins and login support ------------------------------------------------------


@pytest.fixture
def gmc_admins(owner: TestClient, db_session: Session) -> dict[str, uuid.UUID]:
    gmc = create(owner)
    ngozi = db_session.scalar(text("select id from users where username = 'ngozi.okeke'"))
    db_session.execute(
        text("update users set password_hash = :h, email_verified_at = now() where id = :id"),
        {"h": hash_password(PASSWORD), "id": ngozi},
    )
    deputy = make_login(
        db_session,
        username="emeka.vp",
        email="emeka@gmc.example",
        school_id=gmc,
        role="school_admin",
    )
    teacher = make_login(
        db_session, username="tunde.adebayo", email="tunde@gmc.example", school_id=gmc
    )
    return {"school": gmc, "ngozi": ngozi, "deputy": deputy, "teacher": teacher}


def test_the_school_admins_tab(owner: TestClient, gmc_admins: dict[str, uuid.UUID]) -> None:
    status, admins = send(owner, "GET", f"/platform/schools/{gmc_admins['school']}/admins")
    assert status == 200
    assert [(a["username"], a["is_primary"], a["is_active"], a["activated"]) for a in admins] == [
        ("ngozi.okeke", True, True, True),
        ("emeka.vp", False, True, True),
    ]


def test_reset_link_to_a_new_email_signs_out_everywhere(
    app: FastAPI, owner: TestClient, db_session: Session, gmc_admins: dict[str, uuid.UUID]
) -> None:
    """AT-29.1, AC03.5: the super admin never sees a password."""
    ngozi_phone = logged_in(app, "ngozi.okeke")
    base = f"/platform/schools/{gmc_admins['school']}/admins/{gmc_admins['ngozi']}"
    status, body = send(owner, "PATCH", f"{base}/email", {"email": "Ngozi.New@gmc.example"})
    assert status == 200, body
    status, body = send(owner, "POST", f"{base}/send-reset-link", {"sign_out_all": True})
    assert (status, body) == (202, {"detail": "Reset link queued."})
    assert ngozi_phone.get("/api/v1/auth/me").status_code == 401
    reset = db_session.execute(
        text("select to_address, template_data from email_outbox where template = 'password_reset'")
    ).one()
    assert reset.to_address == "ngozi.new@gmc.example"
    assert set(reset.template_data) == {"user_id", "full_name"}
    assert db_session.scalar(
        text("select email_verified_at is null from users where id = :id"),
        {"id": gmc_admins["ngozi"]},
    )
    assert {"school_admins.email_change", "school_admins.reset_link"} <= set(
        audit_actions(db_session, gmc_admins["school"])
    )
    taken = send(owner, "PATCH", f"{base}/email", {"email": "tunde@gmc.example"})
    assert (taken[0], taken[1]["code"]) == (409, "email_taken")


def test_a_temporary_password_is_shown_once_and_never_stored_plainly(
    app: FastAPI, owner: TestClient, db_session: Session, gmc_admins: dict[str, uuid.UUID]
) -> None:
    """F03 rule 5, D-040, AC03.5."""
    ngozi_phone = logged_in(app, "ngozi.okeke")
    base = f"/platform/schools/{gmc_admins['school']}/admins/{gmc_admins['ngozi']}"
    status, body = send(owner, "POST", f"{base}/temporary-password")
    assert status == 201
    temporary = body["temporary_password"]
    assert len(temporary.split("-")) == 4
    stored = db_session.execute(
        text(
            "select password_hash, must_change_password, temp_password_expires_at"
            " > now() + interval '6 days 23 hours' as week from users where id = :id"
        ),
        {"id": gmc_admins["ngozi"]},
    ).one()
    assert temporary not in stored.password_hash
    assert verify_password(temporary, stored.password_hash)[0]
    assert (stored.must_change_password, stored.week) == (True, True)
    assert ngozi_phone.get("/api/v1/auth/me").status_code == 401
    audit = db_session.execute(
        text(
            "select old_values, new_values from audit_events"
            " where action = 'school_admins.temporary_password'"
        )
    ).one()
    assert temporary not in str(tuple(audit))
    client = client_for(app)
    assert log_in(client, "ngozi.okeke", temporary) == 200
    assert client.get("/api/v1/auth/me").json()["must_change_password"] is True


def test_sign_out_deactivate_reactivate_and_resend(
    app: FastAPI, owner: TestClient, db_session: Session, gmc_admins: dict[str, uuid.UUID]
) -> None:
    base = f"/platform/schools/{gmc_admins['school']}/admins/{gmc_admins['deputy']}"
    deputy = logged_in(app, "emeka.vp")
    assert send(owner, "POST", f"{base}/sign-out-all")[0] == 204
    assert deputy.get("/api/v1/auth/me").status_code == 401
    deputy = logged_in(app, "emeka.vp")
    assert send(owner, "POST", f"{base}/deactivate")[0] == 204
    assert deputy.get("/api/v1/auth/me").status_code == 401
    assert (
        db_session.scalar(
            text("select count(*) from user_sessions where user_id = :id"),
            {"id": gmc_admins["deputy"]},
        )
        == 0
    )
    assert log_in(client_for(app), "emeka.vp") == 401
    assert send(owner, "POST", f"{base}/reactivate")[0] == 204
    assert log_in(client_for(app), "emeka.vp") == 200
    status, body = send(owner, "POST", f"{base}/resend-activation")
    assert (status, body["code"]) == (409, "already_activated")
    db_session.execute(
        text("update users set password_hash = null where id = :id"), {"id": gmc_admins["deputy"]}
    )
    assert send(owner, "POST", f"{base}/resend-activation")[0] == 202
    assert (
        db_session.scalar(
            text(
                "select count(*) from email_outbox where template = 'activation'"
                " and to_address = 'emeka@gmc.example'"
            )
        )
        == 1
    )


def test_making_another_admin_the_principal(
    owner: TestClient, db_session: Session, gmc_admins: dict[str, uuid.UUID]
) -> None:
    base = f"/platform/schools/{gmc_admins['school']}/admins/{gmc_admins['deputy']}"
    assert send(owner, "POST", f"{base}/make-primary")[0] == 204
    primary = db_session.scalar(
        text("select user_id from school_memberships where is_primary and school_id = :s"),
        {"s": gmc_admins["school"]},
    )
    assert primary == gmc_admins["deputy"]


def test_login_support_never_reaches_other_roles(
    owner: TestClient, db_session: Session, gmc_admins: dict[str, uuid.UUID]
) -> None:
    """AT-29.2, AC03.6: teachers, parents and students are not found."""
    school = gmc_admins["school"]
    parent = make_login(
        db_session,
        username="ikenna.obi",
        email="ikenna@home.example",
        school_id=school,
        role="parent",
    )
    pupil = make_login(db_session, username="ada.pupil", school_id=school, student=True)
    other_school_admin = make_login(
        db_session,
        username="femi.ade",
        school_id=create_school(db_session, code="RCS", name="Royal Crest Schools"),
        role="school_admin",
    )
    for person in (gmc_admins["teacher"], parent, pupil, other_school_admin, uuid.uuid4()):
        base = f"/platform/schools/{school}/admins/{person}"
        for method, action, body in (
            ("PATCH", "email", {"email": "new@x.example"}),
            ("POST", "send-reset-link", {"sign_out_all": True}),
            ("POST", "temporary-password", None),
            ("POST", "sign-out-all", None),
            ("POST", "deactivate", None),
            ("POST", "make-primary", None),
        ):
            status, _ = send(owner, method, f"{base}/{action}", body)
            assert status == 404, (person, action)
    assert db_session.scalar(text("select count(*) from users where must_change_password")) == 0


def test_there_is_no_log_in_as(app: FastAPI) -> None:
    """AT-29.3, SPEC section 4: no impersonation route of any kind."""
    paths = " ".join(app.openapi()["paths"]).lower()
    for word in ("impersonat", "login-as", "log-in-as", "switch-user", "become"):
        assert word not in paths


# --- platform settings and logs -------------------------------------------------------------


def test_platform_settings_are_validated_and_audited(
    owner: TestClient, db_session: Session
) -> None:
    """F24 rule 4."""
    status, settings = send(owner, "GET", "/platform/settings")
    assert status == 200
    assert settings["security"]["max_additional_admins"] == 2
    assert settings["billing"]["cliff_protection"] is True
    assert settings["general"]["platform_name"] == "SchoolFlow"

    status, settings = send(
        owner,
        "PATCH",
        "/platform/settings",
        {
            "general": {"support_email": "help@schoolflow.example"},
            "security": {"max_additional_admins": 3},
        },
    )
    assert status == 200, settings
    assert settings["security"]["max_additional_admins"] == 3
    assert settings["general"]["support_email"] == "help@schoolflow.example"
    assert send(owner, "GET", "/platform/settings")[1] == settings

    for bad in (
        {"security": {"max_additional_admins": -1}},
        {"security": {"max_additional_admins": 11}},
        {"general": {"unknown": 1}},
        {"secret": {"x": 1}},
        {"general": {"support_email": "not-an-email"}},
    ):
        assert send(owner, "PATCH", "/platform/settings", bad)[0] == 422, bad
    changes = db_session.execute(
        text(
            "select old_values, new_values from audit_events"
            " where action = 'platform_settings.update'"
        )
    ).all()
    assert [tuple(c) for c in changes] == [
        (
            {"general.support_email": None, "security.max_additional_admins": 2},
            {
                "general.support_email": "help@schoolflow.example",
                "security.max_additional_admins": 3,
            },
        )
    ]


def test_the_logs(owner: TestClient, db_session: Session) -> None:
    """F24 rule 5: audit log filtered by school and action; email log shows status only."""
    gmc = create(owner)
    create(
        owner,
        code="BSA",
        name="Bright Stars Academy",
        email="hello@bsa.example",
        principal={
            "full_name": "Chiamaka Nwafor",
            "username": "chiamaka.nwafor",
            "email": "chiamaka@bsa.example",
        },
    )
    status, events = send(owner, "GET", f"/platform/audit-log?school_id={gmc}")
    assert status == 200
    assert [e["action"] for e in events] == ["schools.create"]
    status, events = send(owner, "GET", "/platform/audit-log?action=schools.create")
    assert len(events) == 2
    assert send(owner, "GET", "/platform/audit-log?limit=500")[0] == 422

    status, emails = send(owner, "GET", f"/platform/email-log?school_id={gmc}")
    assert status == 200
    assert sorted(e["type"] for e in emails) == ["activation", "school_setup"]
    assert all("template_data" not in e for e in emails)
    assert {e["status"] for e in emails} == {"queued"}

    status, payments = send(owner, "GET", "/platform/payments")
    assert (status, payments) == (200, [])


# --- the database side (migration 21) -----------------------------------------------------


def test_the_platform_functions_are_for_the_platform_only(db_session: Session) -> None:
    school = create_school(db_session, code="GMC", name="Greenfield Model College")
    calls = (
        "select * from platform_school_usage(:s)",
        "select * from platform_unpublished_classes(:s, 'primary')",
        "select platform_username_taken('someone')",
    )
    with acting_as(db_session, "app_platform"):
        for call in calls:
            db_session.execute(text(call), {"s": school})
    for role in ("app_user", "app_verifier", "app_sender"):
        with acting_as(db_session, role):
            for call in calls:
                with refused(db_session):
                    db_session.execute(text(call), {"s": school})


def test_the_platform_session_itself_refuses_everyone_but_the_super_admin(
    app: FastAPI, owner: TestClient, db_session: Session
) -> None:
    """D-051: a second wall behind each route's permission check."""

    @app.get("/api/v1/_test/platform-session")
    def platform_session(_: PlatformDb) -> dict[str, bool]:
        return {"ok": True}

    school = create_school(db_session, code="RCS", name="Royal Crest Schools")
    make_login(
        db_session, username="femi.ade", school_id=school, role="school_admin", is_primary=True
    )
    principal = logged_in(app, "femi.ade")
    status, body = send(principal, "GET", "/_test/platform-session")
    assert (status, body["code"]) == (403, "permission_denied")
    assert send(owner, "GET", "/_test/platform-session") == (200, {"ok": True})
