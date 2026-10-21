"""Pupils and parents (BUILD_PROMPT 9.2e part 2b; SPEC F03 rules 4 and 8, F05, F07; D-138 to D-140).

Behaviour: school admins register pupils (three name fields, admission
number unique in the school whatever the capitals), enrol them in an arm of
the active session with the arm's subjects, change a pupil's subjects, move
arms with history kept, give a pupil a login slip, search and filter, and
import a CSV that is previewed and committed all or nothing. Parents: a
parent with an email is always added by a link request, and the school gets
the same answer whatever the email (new, another school's parent, a
teacher's); a slip is only for a parent without an email; wards are linked
and unlinked; the school pauses or removes only its own link. The parent
sees requests sent to their verified email and accepts or declines them;
nobody else can. All data is fictional.
"""

import uuid
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.auth_support import (
    build_auth_app,
    client_for,
    csrf,
    log_in,
    logged_in,
    make_login,
    use_fast_hashing,
)
from tests.db_support import acting_as, violates
from tests.factories import (
    add_arm_subject,
    add_membership,
    create_arm,
    create_class,
    create_guardian,
    create_link_request,
    create_school,
    create_session,
    create_student,
    create_subject,
    create_term,
)

HEADER = "surname,first_name,other_names,admission_number,gender,date_of_birth,house\n"


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    return build_auth_app(db_session)


@pytest.fixture
def gmc(db_session: Session) -> dict[str, uuid.UUID]:
    school = create_school(db_session, code="GMC", name="Greenfield Model College")
    year = create_session(db_session, school)
    term = create_term(db_session, school, year, 1, is_active=True)
    jss1 = create_class(db_session, school, "junior_secondary", "JSS 1")
    arm_a, arm_b = (
        create_arm(db_session, school, jss1, "A"),
        create_arm(db_session, school, jss1, "B"),
    )
    maths = create_subject(db_session, school, "Mathematics")
    english = create_subject(db_session, school, "English Language")
    igbo = create_subject(db_session, school, "Igbo Language")
    for subject in (maths, english):
        add_arm_subject(db_session, school, arm_a, subject)
    for subject in (english, igbo):
        add_arm_subject(db_session, school, arm_b, subject)
    return {
        "school": school,
        "year": year,
        "term": term,
        "arm_a": arm_a,
        "arm_b": arm_b,
        "maths": maths,
        "english": english,
        "igbo": igbo,
        "ngozi": make_login(
            db_session,
            username="ngozi.okeke",
            school_id=school,
            role="school_admin",
            is_primary=True,
        ),
        "tunde": make_login(
            db_session, username="tunde.adebayo", email="tunde@gmc.example", school_id=school
        ),
    }


@pytest.fixture
def principal(app: FastAPI, gmc: dict[str, uuid.UUID]) -> TestClient:
    return logged_in(app, "ngozi.okeke")


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


def pupil(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "surname": "Obi",
        "first_name": "Chukwuemeka",
        "other_names": "Kosisochukwu",
        "admission_number": "GMC/2026/014",
        "gender": "male",
    }
    body.update(changes)
    return body


def subjects_of(db_session: Session, student_id: object) -> set[uuid.UUID]:
    return set(
        db_session.scalars(
            text(
                "select ss.subject_id from student_subjects ss join enrolments e"
                " on e.id = ss.enrolment_id where e.student_id = :s and e.left_on is null"
            ),
            {"s": student_id},
        )
    )


# --- pupils (F05) --------------------------------------------------------------------


def test_registering_a_pupil_enrols_them_with_the_arms_subjects(
    principal: TestClient, teacher: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    status, body = send(principal, "POST", "/school/students", pupil(arm_id=str(gmc["arm_a"])))
    assert status == 201, body
    assert (body["admission_number"], body["arm_id"]) == ("GMC/2026/014", str(gmc["arm_a"]))
    assert subjects_of(db_session, body["id"]) == {gmc["maths"], gmc["english"]}
    assert code_of(
        send(principal, "POST", "/school/students", pupil(admission_number="gmc/2026/014"))
    ) == (409, "admission_number_taken")
    for bad in (
        pupil(admission_number="GMC 2026"),
        pupil(gender="other"),
        pupil(surname=" "),
        pupil(school_id=str(gmc["school"])),
    ):
        assert send(principal, "POST", "/school/students", bad)[0] == 422, bad
    assert code_of(
        send(teacher, "POST", "/school/students", pupil(admission_number="GMC/2026/099"))
    ) == (403, "permission_denied")


def test_enrolling_needs_an_active_term(
    principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    db_session.execute(text("update terms set is_active = false"))
    assert code_of(
        send(principal, "POST", "/school/students", pupil(arm_id=str(gmc["arm_a"])))
    ) == (409, "no_active_term")
    status, body = send(principal, "POST", "/school/students", pupil())  # not enrolled yet
    assert (status, body["arm_id"]) == (201, None)


def test_searching_editing_and_withdrawing(
    principal: TestClient, teacher: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    send(principal, "POST", "/school/students", pupil(arm_id=str(gmc["arm_a"])))
    status, musa = send(
        principal,
        "POST",
        "/school/students",
        pupil(
            surname="Ibrahim",
            first_name="Musa",
            other_names=None,
            admission_number="GMC/2026/015",
            arm_id=str(gmc["arm_b"]),
        ),
    )
    assert status == 201
    assert [s["surname"] for s in send(teacher, "GET", "/school/students")[1]] == ["Ibrahim", "Obi"]
    assert [s["first_name"] for s in send(principal, "GET", "/school/students?q=musa")[1]] == [
        "Musa"
    ]
    assert [s["first_name"] for s in send(principal, "GET", "/school/students?q=2026/014")[1]] == [
        "Chukwuemeka"
    ]
    assert [
        s["first_name"]
        for s in send(principal, "GET", f"/school/students?arm_id={gmc['arm_b']}")[1]
    ] == ["Musa"]
    status, edited = send(
        principal,
        "PATCH",
        f"/school/students/{musa['id']}",
        {"other_names": "Abubakar", "house": "Blue", "status": "withdrawn"},
    )
    assert status == 200, edited
    assert (edited["other_names"], edited["house"], edited["status"]) == (
        "Abubakar",
        "Blue",
        "withdrawn",
    )
    assert [
        s["first_name"] for s in send(principal, "GET", "/school/students?status=active")[1]
    ] == ["Chukwuemeka"]
    assert "students.update" in set(db_session.scalars(text("select action from audit_events")))


def test_a_pupils_subjects_and_moving_arms(
    principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    """AC05.2, AT-08.6; F05 "moving arms keeps history"."""
    _, body = send(principal, "POST", "/school/students", pupil(arm_id=str(gmc["arm_a"])))
    url = f"/school/students/{body['id']}"
    status, subjects = send(
        principal, "PUT", f"{url}/subjects", {"subject_ids": [str(gmc["maths"])]}
    )
    assert (status, [s["name"] for s in subjects]) == (200, ["Mathematics"])
    assert code_of(
        send(principal, "PUT", f"{url}/subjects", {"subject_ids": [str(gmc["igbo"])]})
    ) == (409, "student_subjects_subject_in_arm")
    status, moved = send(principal, "POST", f"{url}/move", {"arm_id": str(gmc["arm_b"])})
    assert (status, moved["arm_id"]) == (200, str(gmc["arm_b"]))
    history = db_session.execute(
        text(
            "select arm_id, left_on is not null as ended from enrolments where student_id = :s"
            " order by created_at, ended desc"
        ),
        {"s": body["id"]},
    ).all()
    assert sorted((r.arm_id, r.ended) for r in history) == sorted(
        [(gmc["arm_a"], True), (gmc["arm_b"], False)]
    )
    assert subjects_of(db_session, body["id"]) == {gmc["english"], gmc["igbo"]}


def test_a_pupil_login_slip(
    app: FastAPI, principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    """F02 rule 1, D-040: pupils log in with the school code; usernames are per school."""
    _, body = send(principal, "POST", "/school/students", pupil(arm_id=str(gmc["arm_a"])))
    url = f"/school/students/{body['id']}/login"
    status, slip = send(principal, "POST", url, {"username": "chukwuemeka.obi"})
    assert status == 201, slip
    client = client_for(app)
    assert log_in(client, "GMC/2026/014", slip["temporary_password"], school_code="GMC") == 200
    assert client.get("/api/v1/auth/me").json()["role"] == "student"
    assert code_of(send(principal, "POST", url, {"username": "another.name"})) == (
        409,
        "already_has_login",
    )
    _, other = send(
        principal,
        "POST",
        "/school/students",
        pupil(first_name="Ada", admission_number="GMC/2026/016"),
    )
    assert code_of(
        send(
            principal,
            "POST",
            f"/school/students/{other['id']}/login",
            {"username": "chukwuemeka.obi"},
        )
    ) == (409, "username_taken")
    # Another school's pupil may use the same username (D-033).
    bsa = create_school(db_session, code="BSA", name="Bright Stars Academy")
    make_login(db_session, username="ada.pupil", school_id=bsa, student=True)
    assert (
        send(principal, "POST", f"/school/students/{other['id']}/login", {"username": "ada.pupil"})[
            0
        ]
        == 201
    )


def test_another_schools_pupils_are_not_found(
    principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    bsa = create_school(db_session, code="BSA", name="Bright Stars Academy")
    theirs = create_student(db_session, bsa, "BSA/2026/001", "Eze", "Kosi")
    base = f"/school/students/{theirs}"
    attempts: list[tuple[str, str, dict[str, Any]]] = [
        ("PATCH", base, {"house": "Red"}),
        ("POST", f"{base}/move", {"arm_id": str(gmc["arm_a"])}),
        ("PUT", f"{base}/subjects", {"subject_ids": []}),
        ("POST", f"{base}/login", {"username": "kosi.eze"}),
    ]
    for method, url, body in attempts:
        assert send(principal, method, url, body)[0] == 404, url


# --- CSV import (F05, AT-08.4, AT-08.5) ----------------------------------------------


def import_csv(client: TestClient, arm: uuid.UUID, csv: str, commit: bool) -> tuple[int, Any]:
    response = client.post(
        f"/api/v1/school/students/import?arm_id={arm}&commit={str(commit).lower()}",
        files={"file": ("jss1a.csv", csv.encode(), "text/csv")},
        headers=csrf(client),
    )
    return response.status_code, response.json()


def test_a_good_csv_is_previewed_then_committed(
    principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    csv = HEADER + "".join(
        f"Okafor,Pupil{n},,GMC/2026/1{n:02d},{'female' if n % 2 else 'male'},2014-05-0{1 + n % 9},"
        "Green\n"
        for n in range(12)
    )
    status, preview = import_csv(principal, gmc["arm_a"], csv, commit=False)
    assert status == 200, preview
    assert (preview["valid"], preview["invalid"]) == (12, 0)
    assert db_session.scalar(text("select count(*) from students")) == 0
    status, done = import_csv(principal, gmc["arm_a"], csv, commit=True)
    assert (status, done) == (201, {"created": 12})
    assert (
        db_session.scalar(
            text("select count(*) from enrolments where arm_id = :a"), {"a": gmc["arm_a"]}
        )
        == 12
    )
    assert db_session.scalar(text("select count(*) from student_subjects")) == 24


def test_one_bad_row_commits_nothing(
    principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    send(principal, "POST", "/school/students", pupil())
    csv = HEADER + (
        "Okafor,Ada,,GMC/2026/101,female,2014-05-01,\n"
        "Okafor,Ben,,gmc/2026/014,male,,\n"  # already in the school
        "Okafor,Chi,,GMC/2026/101,female,,\n"  # twice in this file
        "Okafor,Dan,,GMC/2026/104,boy,not-a-date,\n"
    )
    status, preview = import_csv(principal, gmc["arm_a"], csv, commit=False)
    assert (status, preview["valid"], preview["invalid"]) == (200, 1, 3)
    errors = {row["row"]: row["errors"] for row in preview["rows"] if row["errors"]}
    assert set(errors) == {3, 4, 5}
    assert any("already" in message for message in errors[3])
    assert any("twice" in message for message in errors[4])
    assert len(errors[5]) == 2
    status, body = import_csv(principal, gmc["arm_a"], csv, commit=True)
    assert (status, body["code"]) == (422, "import_has_errors")
    assert db_session.scalar(text("select count(*) from students")) == 1
    bad_header = "name,admission\nAda,1\n"
    assert code_of(import_csv(principal, gmc["arm_a"], bad_header, commit=False)) == (
        422,
        "csv_columns",
    )
    response = principal.get("/api/v1/school/students/import/template")
    assert response.status_code == 200
    assert response.text == HEADER


# --- parents (F07, D-138, D-140) ---------------------------------------------------------


@pytest.fixture
def ward(principal: TestClient, gmc: dict[str, uuid.UUID]) -> str:
    _, body = send(principal, "POST", "/school/students", pupil(arm_id=str(gmc["arm_a"])))
    return str(body["id"])


def guardian(email: str | None, ward: str, **changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "full_name": "Ikenna Obi",
        "phone": "0803 000 1122",
        "email": email,
        "wards": [{"student_id": ward, "relationship": "Father"}],
        "login": "link_request" if email else "none",
    }
    body.update(changes)
    return body


def test_every_email_gets_the_same_answer(
    principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID], ward: str
) -> None:
    """AC03.7, AC03.10, AT-31.4, AT-31.7 (option 2A): the school never learns who uses it."""
    bsa = create_school(db_session, code="BSA", name="Bright Stars Academy")
    make_login(
        db_session, username="ikenna.obi", email="ikenna@home.example", school_id=bsa, role="parent"
    )
    users_before = db_session.scalar(text("select count(*) from users"))
    answers: list[dict[str, Any]] = []
    for email in ("new.parent@home.example", "ikenna@home.example", "tunde@gmc.example"):
        status, body = send(principal, "POST", "/school/guardians", guardian(email, ward))
        assert status == 201, body
        body.pop("id")
        answers.append(body)
    assert (
        answers[0]
        == answers[1]
        == answers[2]
        == {"login_status": "waiting", "temporary_password": None}
    )
    assert db_session.scalar(text("select count(*) from users")) == users_before
    emails = db_session.execute(
        text(
            "select to_address, template, template_data from email_outbox"
            " where template = 'parent_link_request' order by to_address"
        )
    ).all()
    assert [e.to_address for e in emails] == [
        "ikenna@home.example",
        "new.parent@home.example",
        "tunde@gmc.example",
    ]
    assert set(emails[0].template_data) == {"link_request_id", "school_name", "guardian_name"}
    status, listing = send(principal, "GET", "/school/guardians")
    assert {g["login_status"] for g in listing} == {"waiting"}
    assert all(g["wards"][0]["relationship"] == "Father" for g in listing)


def test_a_slip_is_only_for_a_parent_without_an_email(
    app: FastAPI, principal: TestClient, db_session: Session, ward: str
) -> None:
    """D-140."""
    assert (
        send(
            principal,
            "POST",
            "/school/guardians",
            guardian("x@home.example", ward, login="temporary_password", username="x.parent"),
        )[0]
        == 422
    )
    status, body = send(
        principal,
        "POST",
        "/school/guardians",
        guardian(None, ward, login="temporary_password", username="ikenna.obi"),
    )
    assert (status, body["login_status"]) == (201, "linked")
    assert log_in(client_for(app), "ikenna.obi", body["temporary_password"]) == 200
    assert (
        send(
            principal, "POST", "/school/guardians", guardian(None, ward, login="temporary_password")
        )[0]
        == 422
    )  # needs a username
    assert send(principal, "POST", "/school/guardians", guardian(None, ward, wards=[]))[0] == 422


def test_wards_are_linked_and_unlinked_in_the_school_only(
    principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID], ward: str
) -> None:
    """F07, AC07.2."""
    _, body = send(principal, "POST", "/school/guardians", guardian(None, ward))
    _, sister = send(
        principal,
        "POST",
        "/school/students",
        pupil(first_name="Adaeze", gender="female", admission_number="GMC/2026/020"),
    )
    url = f"/school/guardians/{body['id']}/wards"
    assert (
        send(principal, "POST", url, {"student_id": sister["id"], "relationship": "Father"})[0]
        == 201
    )
    assert (
        send(principal, "POST", url, {"student_id": sister["id"], "relationship": "Father"})[0]
        == 409
    )
    assert send(principal, "DELETE", f"{url}/{ward}")[0] == 204
    assert db_session.scalar(text("select count(*) from guardian_students")) == 1
    other = create_student(
        db_session, create_school(db_session, code="BSA", name="BSA"), "BSA/1", "Eze", "Kosi"
    )
    assert (
        send(principal, "POST", url, {"student_id": str(other), "relationship": "Uncle"})[0] == 404
    )


def test_the_parent_accepts_or_declines_and_nobody_else_can(
    app: FastAPI,
    principal: TestClient,
    db_session: Session,
    gmc: dict[str, uuid.UUID],
    ward: str,
) -> None:
    """AT-31.4, AT-31.5, AC03.8, D-138."""
    bsa = create_school(db_session, code="BSA", name="Bright Stars Academy")
    ikenna = make_login(
        db_session, username="ikenna.obi", email="ikenna@home.example", school_id=bsa, role="parent"
    )
    make_login(
        db_session, username="ada.parent", email="ada@home.example", school_id=bsa, role="parent"
    )
    _, body = send(principal, "POST", "/school/guardians", guardian("ikenna@home.example", ward))
    guardian_id = body["id"]

    stranger = logged_in(app, "ada.parent")
    assert send(stranger, "GET", "/me/link-requests") == (200, [])
    parent = logged_in(app, "ikenna.obi")
    status, requests = send(parent, "GET", "/me/link-requests")
    assert status == 200
    assert [(r["school_name"], r["school_code"]) for r in requests] == [
        ("Greenfield Model College", "GMC")
    ]
    request_id = requests[0]["id"]
    assert send(stranger, "POST", f"/me/link-requests/{request_id}/accept")[0] == 404
    assert (
        send(logged_in(app, "tunde.adebayo"), "POST", f"/me/link-requests/{request_id}/accept")[0]
        == 404
    )

    status, accepted = send(parent, "POST", f"/me/link-requests/{request_id}/accept")
    assert (status, accepted) == (200, {"school_id": str(gmc["school"])})
    assert (
        db_session.scalar(
            text("select role from school_memberships where user_id = :u and school_id = :s"),
            {"u": ikenna, "s": gmc["school"]},
        )
        == "parent"
    )
    assert (
        db_session.scalar(text("select user_id from guardians where id = :g"), {"g": guardian_id})
        == ikenna
    )
    assert send(parent, "POST", f"/me/link-requests/{request_id}/accept")[0] == 404  # used
    status, listing = send(principal, "GET", "/school/guardians")
    assert [g["login_status"] for g in listing] == ["linked"]
    chosen = parent.get("/api/v1/auth/me", headers={"X-School-Id": str(gmc["school"])}).json()
    assert chosen["school"]["code"] == "GMC"


def test_declined_expired_and_unverified_requests(
    app: FastAPI, principal: TestClient, db_session: Session, ward: str
) -> None:
    bsa = create_school(db_session, code="BSA", name="Bright Stars Academy")
    ikenna = make_login(
        db_session, username="ikenna.obi", email="ikenna@home.example", school_id=bsa, role="parent"
    )
    send(principal, "POST", "/school/guardians", guardian("ikenna@home.example", ward))
    parent = logged_in(app, "ikenna.obi")
    request_id = send(parent, "GET", "/me/link-requests")[1][0]["id"]
    assert send(parent, "POST", f"/me/link-requests/{request_id}/decline")[0] == 204
    assert send(parent, "GET", "/me/link-requests")[1] == []
    _, listing = send(principal, "GET", "/school/guardians")
    assert [g["login_status"] for g in listing] == ["none"]

    send(principal, "POST", "/school/guardians", guardian("ikenna@home.example", ward))
    db_session.execute(
        text(
            "update parent_link_requests set created_at = now() - interval '15 days',"
            " expires_at = now() - interval '1 day'"
            " where declined_at is null"
        )
    )
    assert send(parent, "GET", "/me/link-requests")[1] == []
    send(principal, "POST", "/school/guardians", guardian("ikenna@home.example", ward))
    db_session.execute(
        text("update users set email_verified_at = null where id = :u"), {"u": ikenna}
    )
    assert send(parent, "GET", "/me/link-requests")[1] == []


def test_the_school_cannot_make_the_link_itself(
    db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    """AT-31.5: not even as the app role straight in the database."""
    bsa = create_school(db_session, code="BSA", name="Bright Stars Academy")
    ikenna = make_login(
        db_session, username="ikenna.obi", email="ikenna@home.example", school_id=bsa, role="parent"
    )
    guardian_id = create_guardian(
        db_session, gmc["school"], "Ikenna Obi", email="ikenna@home.example"
    )
    create_link_request(db_session, gmc["school"], guardian_id, "ikenna@home.example")
    with (
        acting_as(db_session, "app_user", school_id=gmc["school"], user_id=gmc["ngozi"]),
        violates(db_session, "school_memberships_link_needs_consent"),
    ):
        add_membership(db_session, ikenna, gmc["school"], "parent")


def test_pausing_removing_and_resending(
    app: FastAPI,
    principal: TestClient,
    db_session: Session,
    gmc: dict[str, uuid.UUID],
    ward: str,
) -> None:
    """F03 rule 9: each school pauses or removes only its own link."""
    _, body = send(
        principal,
        "POST",
        "/school/guardians",
        guardian(None, ward, login="temporary_password", username="ikenna.obi"),
    )
    url = f"/school/guardians/{body['id']}"
    assert send(principal, "POST", f"{url}/pause")[0] == 204
    assert log_in(client_for(app), "ikenna.obi", body["temporary_password"]) == 403
    assert send(principal, "POST", f"{url}/resume")[0] == 204
    assert log_in(client_for(app), "ikenna.obi", body["temporary_password"]) == 200
    assert send(principal, "DELETE", f"{url}/login")[0] == 204
    assert (
        db_session.scalar(text("select user_id from guardians where id = :g"), {"g": body["id"]})
        is None
    )
    assert log_in(client_for(app), "ikenna.obi", body["temporary_password"]) == 403

    _, waiting = send(principal, "POST", "/school/guardians", guardian("p@home.example", ward))
    wurl = f"/school/guardians/{waiting['id']}/link-request"
    assert send(principal, "POST", f"{wurl}/resend")[0] == 202
    assert (
        db_session.scalar(
            text("select count(*) from parent_link_requests where cancelled_at is not null")
        )
        == 1
    )
    assert send(principal, "DELETE", wurl)[0] == 204
    assert (
        db_session.scalar(
            text(
                "select count(*) from parent_link_requests where cancelled_at is null"
                " and accepted_at is null and declined_at is null"
            )
        )
        == 0
    )


def test_staff_cannot_answer_a_request_sent_to_their_email(
    app: FastAPI, principal: TestClient, teacher: TestClient, db_session: Session, ward: str
) -> None:
    """AT-31.7, D-138 3A: a staff email never becomes a parent link."""
    send(principal, "POST", "/school/guardians", guardian("tunde@gmc.example", ward))
    assert send(teacher, "GET", "/me/link-requests") == (200, [])
    request_id = db_session.scalar(text("select id from parent_link_requests"))
    assert send(teacher, "POST", f"/me/link-requests/{request_id}/accept")[0] == 404
    assert send(teacher, "POST", f"/me/link-requests/{request_id}/decline")[0] == 404
    assert db_session.scalar(
        text("select accepted_at is null and declined_at is null from parent_link_requests")
    )
