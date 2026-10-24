"""Rating sheets and the sheet workflow (BUILD_PROMPT 9.2h1 and 9.2i first part).

SPEC F10, F26 rules 3 and 4, section 8; AC10.1, AC10.2, AC26.2; AT-12 to AT-14; D-052, D-142.

Behaviour: a Skill ratings level has rating sheets per learning area, opened
and filled by the arm's teachers (assistants included), pupils against the
area's active skills, one rating per skill from the school's scale and an
optional comment, all or nothing; submission needs every skill rated.
Teachers submit (never assistants); reviewers in scope return (with a
comment) or mark reviewed and see only their queue; school admins approve,
directly only when no reviewer covers the sheet; nobody reviews or approves
a sheet they submitted. All data is fictional.
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
    add_reviewer_scope,
    add_student_subject,
    assign_teacher,
    create_arm,
    create_class,
    create_department,
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
def rcs(db_session: Session) -> dict[str, Any]:
    """Royal Crest Schools: Nursery 2 on Skill ratings, JSS 1A on Scores."""
    s = db_session
    school = create_school(s, code="RCS", name="Royal Crest Schools", school_type="all_levels")
    year = create_session(s, school)
    create_term(s, school, year, 1, is_active=True)
    ensure_defaults(s, school, "school_admin")

    def person(username: str, full_name: str, role: str = "teacher", **kw: Any) -> uuid.UUID:
        return make_login(
            s, username=username, full_name=full_name, school_id=school, role=role, **kw
        )

    people = {
        "grace": person("grace.etim", "Grace Etim"),
        "bola": person("bola.ige", "Bola Ige"),
        "tunde": person("tunde.adebayo", "Tunde Adebayo"),
        "amina": person("amina.bello", "Amina Bello"),
        "emeka": person("emeka.nwosu", "Emeka Nwosu", "reviewer"),
        "femi": person("femi.ade", "Femi Ade", "school_admin", is_primary=True),
        "dayo": person("dayo.vp", "Dayo Vice", "school_admin"),
    }
    nursery2 = create_class(s, school, "nursery", "Nursery 2")
    n2 = create_arm(s, school, nursery2, "")
    areas = {
        r.name: r.id
        for r in s.execute(
            text("select id, name from learning_areas where school_id = :s"), {"s": school}
        )
    }
    for name in ("Number work", "Letter work"):
        s.execute(
            text(
                "insert into class_learning_areas (school_id, class_id, learning_area_id)"
                " values (:s, :c, :a)"
            ),
            {"s": school, "c": nursery2, "a": areas[name]},
        )
    assign_teacher(s, school, people["grace"], n2, form_teacher=True, teaches_all_subjects=True)
    add_assistant(s, school, n2, people["bola"])

    jss1 = create_class(s, school, "junior_secondary", "JSS 1")
    jss1a = create_arm(s, school, jss1, "A")
    sciences = create_department(s, school, "Sciences")
    maths = create_subject(s, school, "Mathematics", department_id=sciences)
    english = create_subject(s, school, "English Language")
    for subject in (maths, english):
        add_arm_subject(s, school, jss1a, subject)
    assign_teacher(s, school, people["tunde"], jss1a, maths)
    assign_teacher(s, school, people["dayo"], jss1a, english)  # a school admin who teaches
    add_reviewer_scope(s, school, people["emeka"], department_id=sciences)

    pupils: dict[str, uuid.UUID] = {}
    for admission, surname, first, arm, subjects in (
        ("RCS/2026/001", "Okafor", "Ada", n2, ()),
        ("RCS/2026/002", "Bello", "Kosi", n2, ()),
        ("RCS/2026/101", "Adeyemi", "Tobi", jss1a, (maths, english)),
    ):
        student = create_student(s, school, admission, surname, first)
        enrolment = enrol(s, school, student, year, arm)
        for subject in subjects:
            add_student_subject(s, school, enrolment, subject)
        pupils[first] = enrolment
    points = {
        r.code: r.id
        for r in s.execute(
            text("select code, id from rating_scale_points where school_id = :s"), {"s": school}
        )
    }
    return {
        "school": school,
        "n2": n2,
        "jss1a": jss1a,
        "maths": maths,
        "english": english,
        "areas": areas,
        "pupils": pupils,
        "points": points,
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


def open_rating(c: TestClient, rcs: dict[str, Any], area: str = "Number work") -> dict[str, Any]:
    status, body = send(
        c,
        "POST",
        "/rating-sheets",
        {"arm_id": str(rcs["n2"]), "learning_area_id": str(rcs["areas"][area])},
    )
    assert status in {200, 201}, body
    return cast(dict[str, Any], body)


def rate_all(sheet: dict[str, Any], point: uuid.UUID) -> list[dict[str, Any]]:
    return [
        {"enrolment_id": row["enrolment_id"], "skill_id": skill["id"], "point_id": str(point)}
        for row in sheet["rows"]
        for skill in sheet["skills"]
    ]


def open_maths(app: FastAPI, rcs: dict[str, Any], full: bool = True) -> dict[str, Any]:
    tunde = as_(app, "tunde.adebayo")
    status, sheet = send(
        tunde, "POST", "/sheets", {"arm_id": str(rcs["jss1a"]), "subject_id": str(rcs["maths"])}
    )
    assert status == 201, sheet
    if full:
        cells = [
            {"enrolment_id": str(rcs["pupils"]["Tobi"]), "component_id": c["id"], "value": 10}
            for c in sheet["columns"]
        ]
        assert send(tunde, "PUT", f"/sheets/{sheet['id']}/scores", {"scores": cells})[0] == 200
    return cast(dict[str, Any], sheet)


# --- rating sheets (F26 rule 3) -------------------------------------------------------------------


def test_my_rating_sheets_and_the_grid(app: FastAPI, rcs: dict[str, Any]) -> None:
    grace = as_(app, "grace.etim")
    status, mine = send(grace, "GET", "/rating-sheets")
    assert status == 200
    assert {(r["class_name"], r["learning_area_name"], r["status"]) for r in mine} == {
        ("Nursery 2", "Number work", "not_started"),
        ("Nursery 2", "Letter work", "not_started"),
    }
    assert len(send(as_(app, "bola.ige"), "GET", "/rating-sheets")[1]) == 2  # the assistant
    assert send(as_(app, "tunde.adebayo"), "GET", "/rating-sheets")[1] == []

    sheet = open_rating(grace, rcs)
    assert (sheet["status"], sheet["can_edit"]) == ("draft", True)
    assert [k["name"] for k in sheet["skills"]] == ["Counts 1 to 20", "Recognises shapes"]
    assert [p["code"] for p in sheet["scale"]] == ["E", "VG", "G", "F", "NI"]
    assert [r["first_name"] for r in sheet["rows"]] == ["Kosi", "Ada"]
    assert sheet["counts"] == {"complete": 0, "missing": 2}
    assert code_of(
        send(
            grace,
            "POST",
            "/rating-sheets",
            {"arm_id": str(rcs["n2"]), "learning_area_id": str(rcs["areas"]["Phonics"])},
        )
    ) == (404, None)
    assert (
        code_of(
            send(
                as_(app, "tunde.adebayo"),
                "POST",
                "/sheets",
                {"arm_id": str(rcs["n2"]), "subject_id": str(rcs["maths"])},
            )
        )[0]
        == 404
    )


def test_saving_ratings_and_comments(
    app: FastAPI, db_session: Session, rcs: dict[str, Any]
) -> None:
    bola = as_(app, "bola.ige")  # an assistant enters too (F06 rule 3)
    sheet = open_rating(bola, rcs)
    ada = str(rcs["pupils"]["Ada"])
    skill = sheet["skills"][0]["id"]
    url = f"/rating-sheets/{sheet['id']}/ratings"
    status, saved = send(
        bola,
        "PUT",
        url,
        {
            "ratings": [
                {"enrolment_id": ada, "skill_id": skill, "point_id": str(rcs["points"]["VG"])}
            ],
            "comments": [{"enrolment_id": ada, "comment": "Counts confidently."}],
        },
    )
    assert status == 200, saved
    row = next(r for r in saved["rows"] if r["enrolment_id"] == ada)
    assert (row["ratings"], row["comment"]) == (
        {skill: str(rcs["points"]["VG"])},
        "Counts confidently.",
    )
    assert row["missing"] == ["Recognises shapes"]
    assert db_session.scalar(text("select entered_by from skill_ratings")) == rcs["bola"]

    other_area_skill = db_session.scalar(
        text("select id from skills where learning_area_id = :a limit 1"),
        {"a": rcs["areas"]["Letter work"]},
    )
    tobi = str(rcs["pupils"]["Tobi"])
    for bad in (
        {"enrolment_id": tobi, "skill_id": skill, "point_id": str(rcs["points"]["G"])},
        {
            "enrolment_id": ada,
            "skill_id": str(other_area_skill),
            "point_id": str(rcs["points"]["G"]),
        },
        {"enrolment_id": ada, "skill_id": skill, "point_id": str(uuid.uuid4())},
    ):
        status, body = send(bola, "PUT", url, {"ratings": [bad]})
        assert (status, body["code"]) == (422, "invalid_ratings"), bad
    assert (
        send(bola, "PUT", url, {"comments": [{"enrolment_id": ada, "comment": "x" * 301}]})[0]
        == 422
    )
    assert db_session.scalar(text("select count(*) from skill_ratings")) == 1


def test_a_rating_sheet_is_submitted_only_when_every_skill_is_rated(
    app: FastAPI, rcs: dict[str, Any]
) -> None:
    """AC26.2; assistants enter but never submit (F06 rule 3, AC06.3)."""
    grace = as_(app, "grace.etim")
    sheet = open_rating(grace, rcs)
    url = f"/sheets/{sheet['id']}/submit"
    assert code_of(send(grace, "POST", url)) == (409, "result_sheets_ratings_missing")
    everything = rate_all(sheet, rcs["points"]["G"])
    assert (
        send(grace, "PUT", f"/rating-sheets/{sheet['id']}/ratings", {"ratings": everything})[0]
        == 200
    )
    assert code_of(send(as_(app, "bola.ige"), "POST", url)) == (403, "assistants_cannot_submit")
    status, moved = send(grace, "POST", url)
    assert (status, moved["status"]) == (200, "submitted")
    assert (
        code_of(
            send(
                grace,
                "PUT",
                f"/rating-sheets/{sheet['id']}/ratings",
                {"ratings": rate_all(sheet, rcs["points"]["E"])[:1]},
            )
        )[0]
        == 409
    )  # locked once submitted
    # No reviewer covers Nursery 2, so the principal approves directly (D-142).
    status, approved = send(as_(app, "femi.ade"), "POST", f"/sheets/{sheet['id']}/approve")
    assert (status, approved["status"]) == (200, "approved")


# --- score sheet workflow (AT-12 to AT-14) ------------------------------------------------------


def test_submit_locks_the_sheet_and_fills_the_reviewers_queue(
    app: FastAPI, rcs: dict[str, Any]
) -> None:
    """AT-12.1, AT-12.2, AT-13.4."""
    sheet = open_maths(app, rcs)
    tunde, emeka = as_(app, "tunde.adebayo"), as_(app, "emeka.nwosu")
    english_sheet = send(
        as_(app, "dayo.vp"),
        "POST",
        "/sheets",
        {"arm_id": str(rcs["jss1a"]), "subject_id": str(rcs["english"])},
    )[1]
    send(
        as_(app, "dayo.vp"),
        "PUT",
        f"/sheets/{english_sheet['id']}/scores",
        {
            "scores": [
                {"enrolment_id": str(rcs["pupils"]["Tobi"]), "component_id": c["id"], "value": 9}
                for c in english_sheet["columns"]
            ]
        },
    )
    assert send(as_(app, "dayo.vp"), "POST", f"/sheets/{english_sheet['id']}/submit")[0] == 200

    assert send(emeka, "GET", "/reviews")[1] == []
    status, moved = send(tunde, "POST", f"/sheets/{sheet['id']}/submit")
    assert (status, moved["status"]) == (200, "submitted")
    status, queue = send(emeka, "GET", "/reviews")
    assert [(q["class_name"], q["name"], q["status"]) for q in queue] == [
        ("JSS 1A", "Mathematics", "submitted")
    ]  # never English: not in his scope
    tobi = str(rcs["pupils"]["Tobi"])
    change = {
        "scores": [{"enrolment_id": tobi, "component_id": sheet["columns"][0]["id"], "value": 11}],
        "reason": "Late correction.",
    }
    assert code_of(send(tunde, "PUT", f"/sheets/{sheet['id']}/scores", change)) == (
        409,
        "scores_sheet_is_locked",
    )
    status, seen = send(emeka, "GET", f"/reviews/{sheet['id']}")
    assert (status, seen["can_edit"]) == (200, False)
    assert send(emeka, "GET", f"/reviews/{english_sheet['id']}")[0] == 404
    assert send(emeka, "POST", f"/sheets/{english_sheet['id']}/review")[0] == 404


def test_return_with_a_comment_resubmit_review_approve(
    app: FastAPI, db_session: Session, rcs: dict[str, Any]
) -> None:
    """AT-13.1 to AT-13.3, AT-14.1, AT-14.2."""
    sheet = open_maths(app, rcs)
    tunde, emeka, femi = (as_(app, u) for u in ("tunde.adebayo", "emeka.nwosu", "femi.ade"))
    base = f"/sheets/{sheet['id']}"
    send(tunde, "POST", f"{base}/submit")
    assert send(emeka, "POST", f"{base}/return", {"comment": "  "})[0] == 422
    assert send(emeka, "POST", f"{base}/return", {})[0] == 422
    status, moved = send(
        emeka, "POST", f"{base}/return", {"comment": "Please check Tobi Adeyemi's CA2."}
    )
    assert (status, moved["status"], moved["status_comment"]) == (
        200,
        "returned_for_correction",
        "Please check Tobi Adeyemi's CA2.",
    )
    # A reviewer never changes scores (AC10.2).
    tobi = str(rcs["pupils"]["Tobi"])
    ca2 = sheet["columns"][1]["id"]
    assert (
        send(
            emeka,
            "PUT",
            f"{base}/scores",
            {"scores": [{"enrolment_id": tobi, "component_id": ca2, "value": 14}], "reason": "Fix"},
        )[0]
        == 404
    )
    assert (
        send(
            tunde,
            "PUT",
            f"{base}/scores",
            {
                "scores": [{"enrolment_id": tobi, "component_id": ca2, "value": 14}],
                "reason": "Corrected transcription error",
            },
        )[0]
        == 200
    )
    status, moved = send(tunde, "POST", f"{base}/submit")
    assert (status, moved["status"]) == (200, "resubmitted")
    # Covered by a reviewer, so the principal cannot skip the review (D-142).
    assert code_of(send(femi, "POST", f"{base}/approve")) == (409, "result_sheets_needs_review")
    status, moved = send(emeka, "POST", f"{base}/review")
    assert (status, moved["status"]) == (200, "reviewed")
    status, moved = send(femi, "POST", f"{base}/approve")
    assert (status, moved["status"]) == (200, "approved")
    actions = list(
        db_session.scalars(
            text(
                "select to_status from approval_actions where sheet_id = :s order by created_at, id"
            ),
            {"s": sheet["id"]},
        )
    )
    assert sorted(actions) == sorted(
        ["submitted", "returned_for_correction", "resubmitted", "reviewed", "approved"]
    )


def test_who_may_make_each_move(app: FastAPI, rcs: dict[str, Any]) -> None:
    """Section 8, AC10.1, AT-14.3, D-052."""
    sheet = open_maths(app, rcs)
    base = f"/sheets/{sheet['id']}"
    tunde, emeka, femi, amina = (
        as_(app, u) for u in ("tunde.adebayo", "emeka.nwosu", "femi.ade", "amina.bello")
    )
    assert send(amina, "POST", f"{base}/submit")[0] == 404  # not her sheet
    assert code_of(send(femi, "POST", f"{base}/approve")) == (409, "wrong_status")  # a draft
    assert code_of(send(femi, "POST", f"{base}/submit")) == (403, "not_assigned")
    send(tunde, "POST", f"{base}/submit")
    assert code_of(send(tunde, "POST", f"{base}/approve")) == (403, "permission_denied")
    assert code_of(send(emeka, "POST", f"{base}/approve")) == (403, "permission_denied")
    assert code_of(send(femi, "POST", f"{base}/review")) == (403, "permission_denied")
    assert code_of(send(tunde, "POST", f"{base}/submit")) == (409, "wrong_status")

    # A school admin who teaches English submits it; she cannot approve her own sheet.
    dayo = as_(app, "dayo.vp")
    english = send(
        dayo, "POST", "/sheets", {"arm_id": str(rcs["jss1a"]), "subject_id": str(rcs["english"])}
    )[1]
    send(
        dayo,
        "PUT",
        f"/sheets/{english['id']}/scores",
        {
            "scores": [
                {"enrolment_id": str(rcs["pupils"]["Tobi"]), "component_id": c["id"], "value": 9}
                for c in english["columns"]
            ]
        },
    )
    assert send(dayo, "POST", f"/sheets/{english['id']}/submit")[0] == 200
    assert code_of(send(dayo, "POST", f"/sheets/{english['id']}/approve")) == (
        409,
        "result_sheets_separation_of_duties",
    )
    assert send(femi, "POST", f"/sheets/{english['id']}/approve")[0] == 200


def test_the_admins_overview_of_the_terms_sheets(app: FastAPI, rcs: dict[str, Any]) -> None:
    sheet = open_maths(app, rcs)
    send(as_(app, "tunde.adebayo"), "POST", f"/sheets/{sheet['id']}/submit")
    rating = open_rating(as_(app, "grace.etim"), rcs)
    status, overview = send(as_(app, "femi.ade"), "GET", "/school/sheets")
    assert status == 200
    by_name = {(o["class_name"], o["name"]): o for o in overview}
    maths = by_name[("JSS 1A", "Mathematics")]
    assert (maths["status"], maths["needs_review"], maths["kind"]) == ("submitted", True, "scores")
    number_work = by_name[("Nursery 2", "Number work")]
    assert (number_work["id"], number_work["needs_review"], number_work["kind"]) == (
        rating["id"],
        False,
        "ratings",
    )
    assert code_of(send(as_(app, "tunde.adebayo"), "GET", "/school/sheets")) == (
        403,
        "permission_denied",
    )


def test_a_class_scope_covers_its_rating_sheets(
    app: FastAPI, db_session: Session, rcs: dict[str, Any]
) -> None:
    """D-049, D-142: a reviewer scoped to a class reviews its rating sheets too."""
    nursery2 = db_session.scalar(
        text("select class_id from class_arms where id = :a"), {"a": rcs["n2"]}
    )
    add_reviewer_scope(db_session, rcs["school"], rcs["emeka"], class_id=nursery2)
    grace, emeka = as_(app, "grace.etim"), as_(app, "emeka.nwosu")
    sheet = open_rating(grace, rcs)
    send(
        grace,
        "PUT",
        f"/rating-sheets/{sheet['id']}/ratings",
        {"ratings": rate_all(sheet, rcs["points"]["G"])},
    )
    send(grace, "POST", f"/sheets/{sheet['id']}/submit")
    assert [q["name"] for q in send(emeka, "GET", "/reviews")[1]] == ["Number work"]
    status, seen = send(emeka, "GET", f"/reviews/{sheet['id']}")
    assert (status, seen["learning_area_name"], seen["can_edit"]) == (200, "Number work", False)
    assert code_of(send(as_(app, "femi.ade"), "POST", f"/sheets/{sheet['id']}/approve")) == (
        409,
        "result_sheets_needs_review",
    )
    assert send(emeka, "POST", f"/sheets/{sheet['id']}/review")[1]["status"] == "reviewed"


def test_rating_sheets_only_for_their_teachers_and_rating_levels(
    app: FastAPI, db_session: Session, rcs: dict[str, Any]
) -> None:
    grace = as_(app, "grace.etim")
    sheet = open_rating(grace, rcs)
    assert send(as_(app, "tunde.adebayo"), "GET", f"/rating-sheets/{sheet['id']}")[0] == 404
    status, seen = send(as_(app, "femi.ade"), "GET", f"/rating-sheets/{sheet['id']}")
    assert (status, seen["can_edit"]) == (200, False)
    db_session.execute(
        text("update school_levels set assessment_mode = 'scores' where level = 'nursery'")
    )
    assert code_of(
        send(
            grace,
            "POST",
            "/rating-sheets",
            {"arm_id": str(rcs["n2"]), "learning_area_id": str(rcs["areas"]["Letter work"])},
        )
    ) == (409, "use_score_sheet")
