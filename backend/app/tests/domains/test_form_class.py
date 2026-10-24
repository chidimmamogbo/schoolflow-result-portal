"""Form teacher tools: My class (BUILD_PROMPT 9.2h2; SPEC F22; AC22.1 to AC22.4; AT-15).

Behaviour: My class is available only to the arm's form (class) teacher and
its assistants, and readable by school admins; it shows the broadsheet (every
pupil against every subject with each sheet's status and the engine's
totals), times school opened, each pupil's comment (with suggestions from
the remark bands), trait ratings on the school's 1 to 5 key and times
present; entries are checked (present within opened, ratings 1 to 5 on the
school's active traits, comments up to 300 characters); a preview shows
times absent and "Preview, not published"; the form teacher submits the
sections (never an assistant), which locks them, and a school admin returns
them with a comment. All data is fictional.
"""

import uuid
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.src.grading.services import ensure_defaults
from app.tests.auth_support import build_auth_app, csrf, logged_in, make_login, use_fast_hashing
from app.tests.factories import (
    add_arm_subject,
    add_assistant,
    add_student_subject,
    assign_teacher,
    create_arm,
    create_class,
    create_school,
    create_session,
    create_student,
    create_subject,
    create_term,
    enrol,
)


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    return build_auth_app(db_session)


@pytest.fixture
def gmc(db_session: Session) -> dict[str, Any]:
    s = db_session
    school = create_school(s, code="GMC", name="Greenfield Model College")
    year = create_session(s, school)
    create_term(s, school, year, 1, is_active=True)
    ensure_defaults(s, school, "school_admin")
    jss1 = create_class(s, school, "junior_secondary", "JSS 1")
    arm_a, arm_b = create_arm(s, school, jss1, "A"), create_arm(s, school, jss1, "B")
    maths = create_subject(s, school, "Mathematics")
    english = create_subject(s, school, "English Language")
    for arm in (arm_a, arm_b):
        for subject in (maths, english):
            add_arm_subject(s, school, arm, subject)

    def person(username: str, full_name: str, role: str = "teacher", **kw: Any) -> uuid.UUID:
        return make_login(
            s, username=username, full_name=full_name, school_id=school, role=role, **kw
        )

    people = {
        "tunde": person("tunde.adebayo", "Tunde Adebayo"),
        "grace": person("grace.etim", "Grace Etim"),
        "bola": person("bola.ige", "Bola Ige"),
        "amina": person("amina.bello", "Amina Bello"),
        "ngozi": person("ngozi.okeke", "Ngozi Okeke", "school_admin", is_primary=True),
    }
    assign_teacher(s, school, people["tunde"], arm_a, form_teacher=True)
    assign_teacher(s, school, people["tunde"], arm_a, maths)
    assign_teacher(s, school, people["grace"], arm_b, form_teacher=True)
    assign_teacher(s, school, people["amina"], arm_a, english)
    add_assistant(s, school, arm_a, people["bola"])
    pupils: dict[str, uuid.UUID] = {}
    for admission, surname, first in (
        ("GMC/2026/014", "Obi", "Chukwuemeka"),
        ("GMC/2026/015", "Ibrahim", "Musa"),
    ):
        enrolment = enrol(
            s, school, create_student(s, school, admission, surname, first), year, arm_a
        )
        for subject in (maths, english):
            add_student_subject(s, school, enrolment, subject)
        pupils[first] = enrolment
    traits = {
        r.name: r.id
        for r in s.execute(
            text("select id, name from rating_traits where school_id = :s"), {"s": school}
        )
    }
    return {
        "school": school,
        "arm_a": arm_a,
        "arm_b": arm_b,
        "maths": maths,
        "english": english,
        "pupils": pupils,
        "traits": traits,
        **people,
    }


def as_(app: FastAPI, username: str) -> TestClient:
    return logged_in(app, username)


def send(c: TestClient, method: str, url: str, body: Any = None) -> tuple[int, Any]:
    response = c.request(method, f"/api/v1{url}", json=body, headers=csrf(c))
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def code_of(result: tuple[int, Any]) -> tuple[int, str | None]:
    status, body = result
    return status, cast(dict[str, Any], body or {}).get("code")


def entry(gmc: dict[str, Any], pupil: str) -> str:
    return f"/form-class/{gmc['arm_a']}/students/{gmc['pupils'][pupil]}"


# --- who may open My class (AC22.1, AC22.2, AT-15.2) ----------------------------------------


def test_my_class_is_for_the_form_teacher_and_assistants(app: FastAPI, gmc: dict[str, Any]) -> None:
    assert code_of(send(as_(app, "amina.bello"), "GET", "/form-class")) == (403, "not_form_teacher")
    for username in ("tunde.adebayo", "bola.ige"):
        status, classes = send(as_(app, username), "GET", "/form-class")
        assert status == 200
        assert [(c["class_name"], c["status"], c["can_submit"]) for c in classes] == [
            ("JSS 1A", "open", username == "tunde.adebayo")
        ]
    status, seen = send(as_(app, "bola.ige"), "GET", f"/form-class/{gmc['arm_a']}")
    assert (status, seen["can_edit"], seen["can_submit"]) == (200, True, False)
    tunde = as_(app, "tunde.adebayo")
    assert send(tunde, "GET", f"/form-class/{gmc['arm_b']}")[0] == 404
    assert send(tunde, "GET", f"/form-class/{gmc['arm_b']}/broadsheet")[0] == 404
    status, seen = send(as_(app, "ngozi.okeke"), "GET", f"/form-class/{gmc['arm_b']}")
    assert (status, seen["can_edit"]) == (200, False)
    assert send(as_(app, "amina.bello"), "GET", f"/form-class/{gmc['arm_a']}")[0] == 404


def test_the_broadsheet(app: FastAPI, gmc: dict[str, Any]) -> None:
    """AT-15.1, F22 rule 2: every pupil against every subject with each sheet's status."""
    tunde = as_(app, "tunde.adebayo")
    status, sheet = send(
        tunde, "POST", "/sheets", {"arm_id": str(gmc["arm_a"]), "subject_id": str(gmc["maths"])}
    )
    cells = [
        {"enrolment_id": str(gmc["pupils"]["Chukwuemeka"]), "component_id": c["id"], "value": v}
        for c, v in zip(sheet["columns"], (16, 15, 47), strict=True)
    ]
    send(tunde, "PUT", f"/sheets/{sheet['id']}/scores", {"scores": cells})
    status, board = send(tunde, "GET", f"/form-class/{gmc['arm_a']}/broadsheet")
    assert status == 200, board
    assert [(s["name"], s["status"]) for s in board["subjects"]] == [
        ("English Language", "not_started"),
        ("Mathematics", "draft"),
    ]
    rows = {r["first_name"]: r for r in board["rows"]}
    maths = str(gmc["maths"])
    assert rows["Chukwuemeka"]["totals"][maths] == 78
    assert rows["Musa"]["totals"][maths] is None
    assert rows["Chukwuemeka"]["average"] is None  # English has no total yet


# --- entries (AT-15.3, AT-15.4) ---------------------------------------------------------------


def test_entries_attendance_and_preview(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    """AT-15.3, AC22.3."""
    tunde = as_(app, "tunde.adebayo")
    url = f"/form-class/{gmc['arm_a']}"
    assert send(tunde, "PUT", f"{url}/attendance-days", {"times_school_opened": 60})[0] == 200
    traits = gmc["traits"]
    status, saved = send(
        tunde,
        "PUT",
        f"{entry(gmc, 'Chukwuemeka')}/entry",
        {
            "comment": "A focused and respectful student. Keep it up in Mathematics.",
            "times_present": 57,
            "ratings": {
                str(traits["Punctuality"]): 5,
                str(traits["Neatness"]): 4,
                str(traits["Politeness"]): 5,
                str(traits["Handwriting"]): 4,
                str(traits["Games and sports"]): 3,
            },
        },
    )
    assert status == 200, saved
    assert (saved["times_present"], saved["times_absent"], len(saved["ratings"])) == (57, 3, 5)
    # The assistant enters too, and each entry records who made it.
    bola = as_(app, "bola.ige")
    assert send(bola, "PUT", f"{entry(gmc, 'Musa')}/entry", {"times_present": 60})[0] == 200
    assert (
        db_session.scalar(
            text("select entered_by from student_term_entries where enrolment_id = :e"),
            {"e": gmc["pupils"]["Musa"]},
        )
        == gmc["bola"]
    )

    status, preview = send(tunde, "GET", f"{entry(gmc, 'Chukwuemeka')}/preview")
    assert status == 200
    assert preview["label"] == "Preview, not published"
    assert preview["attendance"] == {
        "times_school_opened": 60,
        "times_present": 57,
        "times_absent": 3,
    }
    assert preview["comment"].startswith("A focused")
    assert {r["name"]: r["value"] for r in preview["traits"]}["Punctuality"] == 5
    status, board = send(tunde, "GET", url)
    assert board["times_school_opened"] == 60
    assert board["counts"] == {"pupils": 2, "with_comment": 1, "with_attendance": 2}


def test_bad_entries_are_refused(app: FastAPI, db_session: Session, gmc: dict[str, Any]) -> None:
    """AT-15.4, AC22.4."""
    tunde = as_(app, "tunde.adebayo")
    send(tunde, "PUT", f"/form-class/{gmc['arm_a']}/attendance-days", {"times_school_opened": 60})
    url = f"{entry(gmc, 'Chukwuemeka')}/entry"
    over = send(tunde, "PUT", url, {"times_present": 61})
    assert code_of(over) == (422, "present_over_opened")
    trait = str(gmc["traits"]["Punctuality"])
    assert send(tunde, "PUT", url, {"ratings": {trait: 6}})[0] == 422
    assert send(tunde, "PUT", url, {"ratings": {trait: 0}})[0] == 422
    assert send(tunde, "PUT", url, {"comment": "x" * 301})[0] == 422
    assert code_of(send(tunde, "PUT", url, {"ratings": {str(uuid.uuid4()): 3}})) == (
        422,
        "unknown_trait",
    )
    assert (
        send(
            tunde,
            "PUT",
            f"/form-class/{gmc['arm_a']}/students/{uuid.uuid4()}/entry",
            {"times_present": 3},
        )[0]
        == 404
    )
    send(tunde, "PUT", url, {"times_present": 58})
    assert code_of(
        send(
            tunde, "PUT", f"/form-class/{gmc['arm_a']}/attendance-days", {"times_school_opened": 50}
        )
    ) == (422, "opened_below_present")
    db_session.execute(
        text("update rating_traits set is_active = false where id = :t"),
        {"t": gmc["traits"]["Leadership"]},
    )
    assert code_of(send(tunde, "PUT", url, {"ratings": {str(gmc["traits"]["Leadership"]): 3}})) == (
        422,
        "unknown_trait",
    )
    assert db_session.scalar(text("select count(*) from student_trait_ratings")) == 0


def test_suggested_comments_follow_the_remark_bands(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    """F22 rule 3: suggestions from the remark band of the pupil's average."""
    ngozi = as_(app, "ngozi.okeke")
    assert (
        send(
            ngozi,
            "PUT",
            "/school/grading/junior_secondary/remark-bands",
            {
                "bands": [
                    {"min_score": 70, "max_score": 100, "comments": ["An excellent term."]},
                    {"min_score": 0, "max_score": 69, "comments": ["Work harder next term."]},
                ]
            },
        )[0]
        == 200
    )
    tunde = as_(app, "tunde.adebayo")
    for subject, owner, values in (
        (gmc["maths"], "tunde.adebayo", (16, 15, 47)),
        (gmc["english"], "amina.bello", (15, 15, 40)),
    ):
        teacher = as_(app, owner)
        sheet = send(
            teacher, "POST", "/sheets", {"arm_id": str(gmc["arm_a"]), "subject_id": str(subject)}
        )[1]
        send(
            teacher,
            "PUT",
            f"/sheets/{sheet['id']}/scores",
            {
                "scores": [
                    {
                        "enrolment_id": str(gmc["pupils"]["Chukwuemeka"]),
                        "component_id": c["id"],
                        "value": v,
                    }
                    for c, v in zip(sheet["columns"], values, strict=True)
                ]
            },
        )
    _, board = send(tunde, "GET", f"/form-class/{gmc['arm_a']}")
    rows = {r["first_name"]: r for r in board["pupils"]}
    assert rows["Chukwuemeka"]["average"] == "74.00"  # (78 + 70) / 2
    assert rows["Chukwuemeka"]["suggested_comments"] == ["An excellent term."]
    assert rows["Musa"]["suggested_comments"] == []


# --- submit and return (AT-15.5, F22 rule 9) --------------------------------------------------


def test_submit_locks_and_an_admin_returns_with_a_comment(
    app: FastAPI, gmc: dict[str, Any]
) -> None:
    tunde, bola, ngozi = (as_(app, u) for u in ("tunde.adebayo", "bola.ige", "ngozi.okeke"))
    url = f"/form-class/{gmc['arm_a']}"
    send(tunde, "PUT", f"{url}/attendance-days", {"times_school_opened": 60})
    send(tunde, "PUT", f"{entry(gmc, 'Musa')}/entry", {"times_present": 55})
    assert code_of(send(bola, "POST", f"{url}/sections/submit")) == (
        403,
        "assistants_cannot_submit",
    )
    status, moved = send(tunde, "POST", f"{url}/sections/submit")
    assert (status, moved["status"]) == (200, "submitted")
    assert code_of(send(tunde, "PUT", f"{entry(gmc, 'Musa')}/entry", {"times_present": 50})) == (
        409,
        "student_term_entries_section_is_locked",
    )
    assert code_of(send(tunde, "POST", f"{url}/sections/submit")) == (409, "wrong_status")

    back = f"/school/classes/{gmc['arm_a']}/sections/return"
    assert code_of(send(tunde, "POST", back, {"comment": "Fix Musa."})) == (
        403,
        "permission_denied",
    )
    assert send(ngozi, "POST", back, {"comment": " "})[0] == 422
    status, moved = send(ngozi, "POST", back, {"comment": "Please check Musa's attendance."})
    assert (status, moved["status"], moved["status_comment"]) == (
        200,
        "returned",
        "Please check Musa's attendance.",
    )
    assert send(tunde, "PUT", f"{entry(gmc, 'Musa')}/entry", {"times_present": 50})[0] == 200
    assert send(tunde, "POST", f"{url}/sections/submit")[1]["status"] == "submitted"


def test_admins_read_only_and_a_ratings_broadsheet(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    ngozi = as_(app, "ngozi.okeke")
    url = f"/form-class/{gmc['arm_a']}"
    assert code_of(send(ngozi, "PUT", f"{entry(gmc, 'Musa')}/entry", {"comment": "Hi"})) == (
        403,
        "not_assigned",
    )
    assert code_of(send(ngozi, "PUT", f"{url}/attendance-days", {"times_school_opened": 60})) == (
        403,
        "not_assigned",
    )
    assert code_of(send(ngozi, "POST", f"{url}/sections/submit")) == (403, "not_assigned")
    assert (
        send(
            ngozi,
            "POST",
            f"/school/classes/{gmc['arm_a']}/sections/return",
            {"comment": "Nothing to return."},
        )[0]
        == 404
    )  # never opened
    send(as_(app, "tunde.adebayo"), "PUT", f"{url}/attendance-days", {"times_school_opened": 60})
    assert code_of(
        send(
            ngozi,
            "POST",
            f"/school/classes/{gmc['arm_a']}/sections/return",
            {"comment": "Not submitted yet."},
        )
    ) == (409, "wrong_status")

    # A Skill ratings level: the broadsheet lists each learning area's rating sheet status.
    db_session.execute(
        text(
            "update school_levels set assessment_mode = 'skill_ratings'"
            " where level = 'junior_secondary'"
        )
    )
    area = db_session.scalar(
        text(
            "insert into learning_areas (school_id, level, name, position)"
            " values (:s, 'junior_secondary', 'Social habits', 1) returning id"
        ),
        {"s": gmc["school"]},
    )
    db_session.execute(
        text(
            "insert into class_learning_areas (school_id, class_id, learning_area_id)"
            " select :s, class_id, :a from class_arms where id = :arm"
        ),
        {"s": gmc["school"], "a": area, "arm": gmc["arm_a"]},
    )
    status, board = send(ngozi, "GET", f"{url}/broadsheet")
    assert status == 200
    assert (board["kind"], [(s["name"], s["status"]) for s in board["subjects"]]) == (
        "ratings",
        [("Social habits", "not_started")],
    )
    assert [r["first_name"] for r in board["rows"]] == ["Musa", "Chukwuemeka"]
