"""Four small reads for the school admin pages (CHANGE 2026-11-12 B).

Behaviour: a school admin reads the subjects an arm takes and the subjects a
pupil takes; each pupil in the list carries their account id when they have a
login, so login support can reach it; and the school's email statuses list
type, address, status, tries and times, never content or error text. Another
school's arm or pupil answers 404; teachers and parents are refused; a
school never sees another school's emails. All data is fictional.
"""

from typing import Any

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform.email.queue import queue_email
from app.tests.domains.test_publication import app, as_, fast_hashing, gmc, send
from app.tests.factories import (
    add_arm_subject,
    add_student_subject,
    create_arm,
    create_class,
    create_school,
    create_session,
    create_student,
    create_subject,
    create_term,
    enrol,
)

__all__ = ["app", "fast_hashing", "gmc"]


def other_school(db: Session) -> dict[str, Any]:
    school = create_school(db, code="BSA", name="Bright Stars Academy")
    year = create_session(db, school)
    create_term(db, school, year, 1, is_active=True)
    klass = create_class(db, school, "junior_secondary", "JSS 9")
    arm = create_arm(db, school, klass, "A")
    subject = create_subject(db, school, "Hidden Subject")
    add_arm_subject(db, school, arm, subject)
    pupil = create_student(db, school, "2026/014", "Okafor", "Kamsi")
    add_student_subject(db, school, enrol(db, school, pupil, year, arm), subject)
    queue_email(
        db, school, "school_setup", "office@bsa.example", {"school_name": "Bright Stars Academy"}
    )
    return {"school": school, "arm": arm, "pupil": pupil}


def test_an_admin_reads_an_arms_subjects(app: FastAPI, gmc: dict[str, Any]) -> None:
    status, body = send(as_(app, "ngozi.okeke"), "GET", f"/school/arms/{gmc['arm_a']}/subjects")
    assert status == 200, body
    assert [s["name"] for s in body] == ["English Language", "Mathematics"]


def test_an_admin_reads_a_pupils_subjects(app: FastAPI, gmc: dict[str, Any]) -> None:
    pupil = gmc["students"]["Chukwuemeka"]
    status, body = send(as_(app, "ngozi.okeke"), "GET", f"/school/students/{pupil}/subjects")
    assert status == 200, body
    assert [s["name"] for s in body] == ["English Language", "Mathematics"]


def test_another_schools_arm_or_pupil_is_not_found(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    other = other_school(db_session)
    ngozi = as_(app, "ngozi.okeke")
    assert send(ngozi, "GET", f"/school/arms/{other['arm']}/subjects")[0] == 404
    assert send(ngozi, "GET", f"/school/students/{other['pupil']}/subjects")[0] == 404


def test_teachers_and_parents_are_refused(app: FastAPI, gmc: dict[str, Any]) -> None:
    pupil = gmc["students"]["Chukwuemeka"]
    for username in ("tunde.adebayo", "ikenna.obi"):
        who = as_(app, username)
        assert send(who, "GET", f"/school/arms/{gmc['arm_a']}/subjects")[0] == 403, username
        assert send(who, "GET", f"/school/students/{pupil}/subjects")[0] == 403, username
        assert send(who, "GET", "/school/emails")[0] == 403, username


def test_each_pupil_carries_their_account_id(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    status, rows = send(as_(app, "ngozi.okeke"), "GET", "/school/students")
    assert status == 200, rows
    account = db_session.scalar(text("select id from users where username = 'chukwuemeka.obi'"))
    ids = {r["first_name"]: r["user_id"] for r in rows}
    assert ids["Chukwuemeka"] == str(account)
    assert ids["Musa"] is None


def test_the_school_sees_only_its_own_email_statuses(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    other_school(db_session)
    queue_email(
        db_session,
        gmc["school"],
        "results_published",
        "ikenna@home.example",
        {"secret": "never shown"},
    )
    status, rows = send(as_(app, "ngozi.okeke"), "GET", "/school/emails")
    assert status == 200, rows
    assert [r["to_address"] for r in rows] == ["ikenna@home.example"]
    assert set(rows[0]) == {
        "id",
        "type",
        "to_address",
        "status",
        "attempts",
        "created_at",
        "sent_at",
    }
    assert "never shown" not in str(rows)
