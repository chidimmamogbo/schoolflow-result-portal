"""Students needing attention (BUILD_PROMPT 9.2j2; SPEC F23; AC23.1 to AC23.6; D-171).

Behaviour: the list is read from the entries written at publication, for
Valid reports only (approved but unpublished results never appear, and a
revoked report drops out). Each viewer sees their scope: school admins every
class (and they alone filter by teacher); a subject teacher only their own
subjects in their classes; a form teacher every subject of their form class
plus their own subjects; a reviewer the subjects their scope covers. By
student counts only what the viewer can see, and shows the average and its
flag only to viewers who see the whole class. Skill ratings levels list skills
at or below the attention rating By learning area. Parents and students are
refused. CSV export follows the same scope. All data is fictional.
"""

import csv
import io
import uuid
from typing import Any

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.tests.auth_support import logged_in, make_login
from app.tests.domains.test_publication import (
    app,
    as_,
    code_of,
    fast_hashing,
    gmc,
    send,
)
from app.tests.domains.test_ratings_and_workflow import rcs
from app.tests.factories import assign_area_teacher, assign_teacher

__all__ = ["app", "fast_hashing", "gmc", "rcs"]

ENGLISH_A = {"Chukwuemeka": (15, 15, 40), "Musa": (8, 8, 14), "Zainab": (14, 14, 32)}
MATHS_A = {"Chukwuemeka": (16, 15, 47), "Musa": (10, 10, 18), "Zainab": (16, 15, 47)}


def enter(
    app: FastAPI, gmc: dict[str, Any], arm: str, subject: str, username: str,
    scores: dict[str, tuple[int, int, int]],
) -> str:  # fmt: skip
    teacher = as_(app, username)
    body = {"arm_id": str(gmc[arm]), "subject_id": str(gmc[subject])}
    sheet = send(teacher, "POST", "/sheets", body)[1]
    cells = [
        {"enrolment_id": str(gmc["pupils"][pupil]), "component_id": column["id"], "value": value}
        for pupil, values in scores.items()
        for column, value in zip(sheet["columns"], values, strict=True)
    ]
    assert send(teacher, "PUT", f"/sheets/{sheet['id']}/scores", {"scores": cells})[0] == 200
    assert send(teacher, "POST", f"/sheets/{sheet['id']}/submit")[0] == 200
    return str(sheet["id"])


def finish_class(
    app: FastAPI, gmc: dict[str, Any], arm: str, username: str, pupils: list[str]
) -> None:
    teacher = as_(app, username)
    url = f"/form-class/{gmc[arm]}"
    send(teacher, "PUT", f"{url}/attendance-days", {"times_school_opened": 60})
    ratings = {t["id"]: 4 for t in send(teacher, "GET", url)[1]["traits"]}
    for pupil in pupils:
        body = {"comment": f"{pupil} worked well.", "times_present": 55, "ratings": ratings}
        assert send(teacher, "PUT", f"{url}/students/{gmc['pupils'][pupil]}/entry", body)[0] == 200
    assert send(teacher, "POST", f"{url}/sections/submit")[0] == 200
    comments = [{"enrolment_id": str(gmc["pupils"][p]), "comment": "Well done."} for p in pupils]
    ngozi = as_(app, "ngozi.okeke")
    url = f"/school/publications/{gmc[arm]}/principal-comments"
    assert send(ngozi, "PUT", url, {"comments": comments})[0] == 200


def approve(app: FastAPI, sheets: list[str], reviewed: list[str]) -> None:
    for sheet in reviewed:
        assert send(as_(app, "emeka.nwosu"), "POST", f"/sheets/{sheet}/review")[0] == 200
    for sheet in sheets:
        assert send(as_(app, "ngozi.okeke"), "POST", f"/sheets/{sheet}/approve")[0] == 200


def listing(app: FastAPI, username: str, query: str = "") -> list[tuple[Any, ...]]:
    status, body = send(as_(app, username), "GET", f"/attention{query}")
    assert status == 200, body
    view = body["view"]
    if view == "by_subject":
        return [
            (r["class_name"], r["student_name"], r["subject"], r["score"]) for r in body["rows"]
        ]
    if view == "by_learning_area":
        return [
            (r["student_name"], r["learning_area"], r["skill"], r["rating"]) for r in body["rows"]
        ]
    return [
        (r["student_name"], r["failed_count"], r["average"], r["average_below_pass_mark"])
        for r in body["rows"]
    ]


def test_each_person_sees_their_scope(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    s, school = db_session, gmc["school"]
    assign_teacher(s, school, gmc["amina"], gmc["arm_b"], gmc["english"])
    bola = make_login(
        s, username="bola.ige", full_name="Bola Ige", school_id=school, role="teacher"
    )
    assign_teacher(s, school, bola, gmc["arm_b"], form_teacher=True)

    maths_a = enter(app, gmc, "arm_a", "maths", "tunde.adebayo", MATHS_A)
    english_a = enter(app, gmc, "arm_a", "english", "amina.bello", ENGLISH_A)
    approve(app, [maths_a, english_a], [maths_a])
    finish_class(app, gmc, "arm_a", "tunde.adebayo", ["Chukwuemeka", "Musa", "Zainab"])
    ngozi = as_(app, "ngozi.okeke")
    assert send(ngozi, "GET", "/attention")[1]["rows"] == []  # nothing published yet
    assert send(ngozi, "POST", f"/school/publications/{gmc['arm_a']}/publish")[0] == 200

    maths_b = enter(app, gmc, "arm_b", "maths", "grace.etim", {"Kosi": (10, 10, 15)})
    english_b = enter(app, gmc, "arm_b", "english", "amina.bello", {"Kosi": (15, 15, 20)})
    approve(app, [maths_b, english_b], [maths_b])
    finish_class(app, gmc, "arm_b", "bola.ige", ["Kosi"])
    musa_maths = ("JSS 1A", "Musa Ibrahim", "Mathematics", 38)
    musa_english = ("JSS 1A", "Musa Ibrahim", "English Language", 30)
    kosi_maths = ("JSS 1B", "Kosi Eze", "Mathematics", 35)
    # AC23.5: JSS 1B is approved but not published, so it is not listed.
    assert listing(app, "ngozi.okeke") == [musa_english, musa_maths]  # AC23.1
    assert send(ngozi, "POST", f"/school/publications/{gmc['arm_b']}/publish")[0] == 200

    assert listing(app, "ngozi.okeke") == [musa_english, musa_maths, kosi_maths]
    assert listing(app, "grace.etim") == [kosi_maths]  # AC23.2: her subject in her class only
    assert listing(app, "amina.bello") == [musa_english]  # English in both of her classes
    assert listing(app, "tunde.adebayo") == [musa_english, musa_maths]  # AC23.3: his form class
    assert listing(app, "bola.ige") == [kosi_maths]  # form teacher of JSS 1B
    assert listing(app, "emeka.nwosu") == [musa_maths, kosi_maths]  # reviewer: Sciences

    by_student = "?view=by_student"
    assert listing(app, "ngozi.okeke", by_student) == [
        ("Musa Ibrahim", 2, "34.00", True),
        ("Kosi Eze", 1, "42.50", False),
    ]
    assert listing(app, "tunde.adebayo", by_student) == [("Musa Ibrahim", 2, "34.00", True)]
    assert listing(app, "grace.etim", by_student) == [("Kosi Eze", 1, None, None)]
    assert listing(app, "emeka.nwosu", by_student) == [
        ("Musa Ibrahim", 1, None, None),
        ("Kosi Eze", 1, None, None),
    ]

    assert listing(app, "ngozi.okeke", f"?arm_id={gmc['arm_b']}") == [kosi_maths]
    assert listing(app, "ngozi.okeke", f"?subject_id={gmc['maths']}") == [musa_maths, kosi_maths]
    assert listing(app, "ngozi.okeke", f"?teacher_id={gmc['grace']}") == [kosi_maths]
    assert listing(app, "ngozi.okeke", f"?term_id={uuid.uuid4()}") == []
    assert code_of(
        send(as_(app, "tunde.adebayo"), "GET", f"/attention?teacher_id={gmc['grace']}")
    ) == (
        403,
        "admins_only",
    )
    _, body = send(ngozi, "GET", "/attention")
    assert (body["pass_mark"], body["count"], body["term_id"]) == (40, 3, str(gmc["term"]))

    # A revoked report drops out of the list.
    musa_report = db_session.scalar(
        text("select id from report_documents where enrolment_id = :e"),
        {"e": gmc["pupils"]["Musa"]},
    )
    revoke = {"reason": "Issued in error."}
    assert send(ngozi, "POST", f"/school/reports/{musa_report}/revoke", revoke)[0] == 200
    assert listing(app, "ngozi.okeke") == [kosi_maths]


def test_parents_and_students_are_refused(app: FastAPI, gmc: dict[str, Any]) -> None:
    for client in (as_(app, "ikenna.obi"), logged_in(app, "chukwuemeka.obi", school_code="GMC")):
        assert code_of(send(client, "GET", "/attention")) == (403, "permission_denied")
        assert send(client, "GET", "/attention/export.csv")[0] == 403  # AC23.4
    assert send(as_(app, "ngozi.okeke"), "GET", "/attention?view=by_class")[0] == 422


def publish_a(app: FastAPI, gmc: dict[str, Any]) -> None:
    maths_a = enter(app, gmc, "arm_a", "maths", "tunde.adebayo", MATHS_A)
    english_a = enter(app, gmc, "arm_a", "english", "amina.bello", ENGLISH_A)
    approve(app, [maths_a, english_a], [maths_a])
    finish_class(app, gmc, "arm_a", "tunde.adebayo", ["Chukwuemeka", "Musa", "Zainab"])
    status, _ = send(
        as_(app, "ngozi.okeke"), "POST", f"/school/publications/{gmc['arm_a']}/publish"
    )
    assert status == 200


def test_the_csv_export_follows_the_scope(app: FastAPI, gmc: dict[str, Any]) -> None:
    publish_a(app, gmc)
    ngozi = as_(app, "ngozi.okeke")

    response = ngozi.get("/api/v1/attention/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert list(csv.reader(io.StringIO(response.text))) == [
        ["Student", "Admission number", "Class", "Subject", "Score", "Grade", "Teacher"],
        ["Musa Ibrahim", "GMC/2026/015", "JSS 1A", "English Language", "30", "F9", "Amina Bello"],
        ["Musa Ibrahim", "GMC/2026/015", "JSS 1A", "Mathematics", "38", "F9", "Tunde Adebayo"],
    ]
    amina = as_(app, "amina.bello").get("/api/v1/attention/export.csv?view=by_student")
    assert list(csv.reader(io.StringIO(amina.text))) == [
        [
            "Student", "Admission number", "Class", "Failed subjects or skills", "Average",
            "Average below pass mark",
        ],
        ["Musa Ibrahim", "GMC/2026/015", "JSS 1A", "1", "", ""],
    ]  # fmt: skip


def test_names_that_look_like_formulas_are_made_safe(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    db_session.execute(
        text("update students set first_name = '=HYPERLINK(1)' where id = :s"),
        {"s": gmc["students"]["Musa"]},
    )
    publish_a(app, gmc)
    ngozi = as_(app, "ngozi.okeke")
    rows = list(csv.reader(io.StringIO(ngozi.get("/api/v1/attention/export.csv").text)))
    assert rows[1][0] == "'=HYPERLINK(1) Ibrahim"


def test_skill_ratings_list_skills_needing_attention(
    app: FastAPI, db_session: Session, rcs: dict[str, Any]
) -> None:
    # Amina teaches Number work in Nursery 2 as a specialist (not the class teacher).
    assign_area_teacher(
        db_session, rcs["school"], rcs["amina"], rcs["n2"], rcs["areas"]["Number work"]
    )
    grace, femi = as_(app, "grace.etim"), as_(app, "femi.ade")
    sheets: list[str] = []
    for area, rater in (("Number work", as_(app, "amina.bello")), ("Letter work", grace)):
        body = {"arm_id": str(rcs["n2"]), "learning_area_id": str(rcs["areas"][area])}
        view = send(rater, "POST", "/rating-sheets", body)[1]
        ratings = [
            {
                "enrolment_id": str(rcs["pupils"][pupil]),
                "skill_id": skill["id"],
                "point_id": str(
                    rcs["points"][
                        "NI" if (pupil, skill["name"]) == ("Ada", "Counts 1 to 20") else "G"
                    ]
                ),
            }
            for pupil in ("Ada", "Kosi")
            for skill in view["skills"]
        ]
        assert (
            send(rater, "PUT", f"/rating-sheets/{view['id']}/ratings", {"ratings": ratings})[0]
            == 200
        )
        assert send(rater, "POST", f"/sheets/{view['id']}/submit")[0] == 200
        assert send(femi, "POST", f"/sheets/{view['id']}/approve")[0] == 200
        sheets.append(view["id"])
    url = f"/form-class/{rcs['n2']}"
    send(grace, "PUT", f"{url}/attendance-days", {"times_school_opened": 60})
    for pupil in ("Ada", "Kosi"):
        body = {"comment": f"{pupil} is a joy to teach.", "times_present": 58}
        assert send(grace, "PUT", f"{url}/students/{rcs['pupils'][pupil]}/entry", body)[0] == 200
    assert send(grace, "POST", f"{url}/sections/submit")[0] == 200
    comments = [
        {"enrolment_id": str(rcs["pupils"][p]), "comment": "Well done."} for p in ("Ada", "Kosi")
    ]
    publication = f"/school/publications/{rcs['n2']}"
    assert send(femi, "PUT", f"{publication}/principal-comments", {"comments": comments})[0] == 200
    status, body = send(femi, "POST", f"{publication}/publish")
    assert (status, body["published"]) == (200, 2), body

    ada = ("Ada Okafor", "Number work", "Counts 1 to 20", "Needs improvement")
    assert listing(app, "femi.ade", "?view=by_learning_area") == [ada]  # AC23.6
    assert listing(app, "grace.etim", "?view=by_learning_area") == [ada]  # class teacher
    assert listing(app, "amina.bello", "?view=by_learning_area") == [ada]  # her learning area
    assert listing(app, "tunde.adebayo", "?view=by_learning_area") == []  # JSS 1 Mathematics only
    assert listing(app, "femi.ade", "?view=by_student") == [("Ada Okafor", 1, None, None)]
    assert listing(app, "femi.ade") == []  # no scores below the pass mark
