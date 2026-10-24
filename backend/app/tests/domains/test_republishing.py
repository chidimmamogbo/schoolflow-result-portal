"""Reopening and republishing a class (BUILD_PROMPT 9.2i; SPEC F10, F11, F23 rule 1; D-171).

Behaviour: a school admin reopens chosen sheets of a published class, or its
class sections, with a reason (optionally naming the correction request that
prompted it); each becomes a new revision in Draft or Open and goes through
the workflow again while the pupils' Valid reports stay in place. Republishing
issues a new revision only for pupils whose report changed: the database
supersedes the old one, the report ID stays, the verification code is new,
Students needing attention follows the new revision, and only those pupils,
their parents and the class's staff are told. All data is fictional.
"""

import uuid
from typing import Any

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.tests.domains.test_publication import (
    app,
    approve_all,
    as_,
    code_of,
    complete_my_class,
    fast_hashing,
    gmc,
    principal_comments,
    send,
)
from app.tests.factories import create_correction_request, move_correction

__all__ = ["app", "fast_hashing", "gmc"]


def publish_a(app: FastAPI, gmc: dict[str, Any]) -> dict[str, Any]:
    approve_all(app, gmc)
    complete_my_class(app, gmc)
    principal_comments(app, gmc)
    status, body = send(
        as_(app, "ngozi.okeke"), "POST", f"/school/publications/{gmc['arm_a']}/publish"
    )
    assert status == 200
    return {r["admission_number"]: r for r in body["reports"]}


def sheet_of(db: Session, gmc: dict[str, Any], subject: str) -> uuid.UUID:
    sheet: uuid.UUID = db.scalar(
        text("select id from result_sheets where arm_id = :a and subject_id = :s"),
        {"a": gmc["arm_a"], "s": gmc[subject]},
    )
    return sheet


def reports(db: Session, gmc: dict[str, Any]) -> list[tuple[str, int, str, str, str]]:
    return [
        (r.admission_number, r.revision, r.status, r.report_code, r.verification_code)
        for r in db.execute(
            text(
                "select p.admission_number, d.revision, d.status, d.report_code,"
                " d.verification_code from report_documents d"
                " join enrolments e on e.id = d.enrolment_id join students p on p.id = e.student_id"
                " where d.arm_id = :a order by p.admission_number, d.revision"
            ),
            {"a": gmc["arm_a"]},
        )
    ]


def reopen_url(gmc: dict[str, Any]) -> str:
    return f"/school/publications/{gmc['arm_a']}/reopen"


def test_reopening_needs_a_reason_and_a_published_class(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    ngozi = as_(app, "ngozi.okeke")
    approve_all(app, gmc)
    maths = str(sheet_of(db_session, gmc, "maths"))
    why = "Musa's exam script shows 22, not 18."
    assert code_of(send(ngozi, "POST", reopen_url(gmc), {"reason": why, "sheet_ids": [maths]})) == (
        409,
        "not_published",
    )
    complete_my_class(app, gmc)
    principal_comments(app, gmc)
    send(ngozi, "POST", f"/school/publications/{gmc['arm_a']}/publish")
    before = reports(db_session, gmc)

    assert send(ngozi, "POST", reopen_url(gmc), {"reason": " ", "sheet_ids": [maths]})[0] == 422
    assert code_of(send(ngozi, "POST", reopen_url(gmc), {"reason": why})) == (
        422,
        "nothing_to_reopen",
    )
    assert code_of(
        send(
            as_(app, "tunde.adebayo"),
            "POST",
            reopen_url(gmc),
            {"reason": why, "sheet_ids": [maths]},
        )
    ) == (403, "permission_denied")
    other_arm = f"/school/publications/{gmc['arm_b']}/reopen"
    assert code_of(send(ngozi, "POST", other_arm, {"reason": why, "sheet_ids": [maths]})) == (
        409,
        "not_published",
    )
    unknown = {"reason": why, "sheet_ids": [str(uuid.uuid4())]}
    assert send(ngozi, "POST", reopen_url(gmc), unknown)[0] == 404
    no_ticket = {"reason": why, "sheet_ids": [maths], "correction_request_id": str(uuid.uuid4())}
    assert send(ngozi, "POST", reopen_url(gmc), no_ticket)[0] == 404
    assert reports(db_session, gmc) == before  # nothing moved

    status, ready = send(ngozi, "POST", reopen_url(gmc), {"reason": why, "sheet_ids": [maths]})
    assert (status, ready) == (
        200,
        {
            "ready": False,
            "problems": ["Mathematics: draft"],
            "class_name": "JSS 1A",
            "status": "in_progress",
        },
    )
    sheets = {
        r.name: (r.status, r.revision)
        for r in db_session.execute(
            text(
                "select s.name, r.status, r.revision from result_sheets r"
                " join subjects s on s.id = r.subject_id where r.arm_id = :a"
            ),
            {"a": gmc["arm_a"]},
        )
    }
    assert sheets == {"Mathematics": ("draft", 2), "English Language": ("published", 1)}
    assert reports(db_session, gmc) == before  # the Valid reports stay until republished
    assert code_of(send(ngozi, "POST", reopen_url(gmc), {"reason": why, "sheet_ids": [maths]})) == (
        409,
        "wrong_status",
    )
    event = db_session.execute(
        text("select reason, new_values from audit_events where action = 'results.reopen'")
    ).one()
    assert event.reason == why
    assert (event.new_values["sheet_ids"], event.new_values["sections"]) == ([maths], False)


def test_a_reopen_can_name_the_correction_request(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    codes = publish_a(app, gmc)
    report_id = db_session.scalar(
        text("select id from report_documents where report_code = :c"),
        {"c": codes["GMC/2026/014"]["report_code"]},
    )
    db_session.execute(
        text(
            "update school_features set enabled = true"
            " where school_id = :s and feature = 'correction_queue'"
        ),
        {"s": gmc["school"]},
    )
    db_session.execute(
        text("select set_config('app.user_id', :u, true)"), {"u": str(gmc["ikenna"])}
    )
    closed = create_correction_request(
        db_session, gmc["school"], report_id, subject_id=gmc["maths"]
    )
    ticket = create_correction_request(
        db_session, gmc["school"], report_id, subject_id=gmc["maths"]
    )
    db_session.execute(text("select set_config('app.user_id', :u, true)"), {"u": str(gmc["ngozi"])})
    move_correction(db_session, closed, "investigating")
    move_correction(db_session, closed, "rejected", message="The script shows 47.")
    ngozi = as_(app, "ngozi.okeke")
    body = {
        "reason": "Correction request: Chukwuemeka's Mathematics exam.",
        "sheet_ids": [str(sheet_of(db_session, gmc, "maths"))],
        "correction_request_id": str(closed),
    }
    assert code_of(send(ngozi, "POST", reopen_url(gmc), body)) == (409, "wrong_status")
    body["correction_request_id"] = str(ticket)
    assert send(ngozi, "POST", reopen_url(gmc), body)[0] == 200
    logged = db_session.scalar(
        text(
            "select new_values ->> 'correction_request_id' from audit_events"
            " where action = 'results.reopen'"
        )
    )
    assert logged == str(ticket)


def edit_musa_maths(app: FastAPI, db: Session, gmc: dict[str, Any], exam: int) -> None:
    tunde = as_(app, "tunde.adebayo")
    sheet = sheet_of(db, gmc, "maths")
    _, view = send(tunde, "GET", f"/sheets/{sheet}")
    exam_column = view["columns"][-1]["id"]
    cell = {"enrolment_id": str(gmc["pupils"]["Musa"]), "component_id": exam_column, "value": exam}
    body = {"scores": [cell], "reason": "Exam script re-marked."}
    assert send(tunde, "PUT", f"/sheets/{sheet}/scores", body)[0] == 200
    assert send(tunde, "POST", f"/sheets/{sheet}/submit")[0] == 200
    assert send(as_(app, "emeka.nwosu"), "POST", f"/sheets/{sheet}/review")[0] == 200
    assert send(as_(app, "ngozi.okeke"), "POST", f"/sheets/{sheet}/approve")[0] == 200


def test_republishing_issues_new_revisions_only_for_changed_reports(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    first = publish_a(app, gmc)
    ngozi = as_(app, "ngozi.okeke")
    publication = f"/school/publications/{gmc['arm_a']}"
    maths = str(sheet_of(db_session, gmc, "maths"))
    reason = {"reason": "Musa's exam script shows 22, not 18."}
    send(ngozi, "POST", reopen_url(gmc), {**reason, "sheet_ids": [maths]})
    assert code_of(send(ngozi, "POST", f"{publication}/publish")) == (409, "not_ready")
    edit_musa_maths(app, db_session, gmc, 22)
    assert send(ngozi, "GET", publication)[1]["ready"] is True

    status, body = send(ngozi, "POST", f"{publication}/publish")
    assert (status, body["published"]) == (200, 3)  # the class average moved for everyone
    rows = reports(db_session, gmc)
    for admission, report in first.items():
        assert [(r[1], r[2], r[3]) for r in rows if r[0] == admission] == [
            (1, "superseded", report["report_code"]),
            (2, "valid", report["report_code"]),
        ]
    new_codes = {r["admission_number"]: r["verification_code"] for r in body["reports"]}
    assert all(new_codes[a] != first[a]["verification_code"] for a in first)
    musa = db_session.scalar(
        text(
            "select snapshot from report_documents d join enrolments e on e.id = d.enrolment_id"
            " where e.id = :e and d.status = 'valid'"
        ),
        {"e": gmc["pupils"]["Musa"]},
    )
    assert {s["name"]: s["total"] for s in musa["subjects"]}["Mathematics"] == 42
    # Students needing attention follows the Valid revision: 42 is not below 40 any more.
    assert send(ngozi, "GET", "/attention")[1]["rows"] == []
    titles = list(db_session.scalars(text("select title from notices order by created_at, title")))
    assert "Updated First Term results for JSS 1 are now available" in titles
    assert (
        db_session.scalar(
            text("select count(*) from audit_events where action = 'results.republish'")
        )
        == 1
    )

    # Reopen English and approve it unchanged: nothing on any report changes.
    english = str(sheet_of(db_session, gmc, "english"))
    send(ngozi, "POST", reopen_url(gmc), {"reason": "Checking a total.", "sheet_ids": [english]})
    assert send(as_(app, "amina.bello"), "POST", f"/sheets/{english}/submit")[0] == 200
    assert send(ngozi, "POST", f"/sheets/{english}/approve")[0] == 200
    notices = db_session.scalar(text("select count(*) from notices"))
    status, body = send(ngozi, "POST", f"{publication}/publish")
    assert (status, body["published"], body["reports"]) == (200, 0, [])
    assert reports(db_session, gmc) == rows
    assert db_session.scalar(text("select count(*) from notices")) == notices
    assert send(ngozi, "GET", publication)[1]["problems"] == ["Already published"]


def test_reopened_sections_tell_only_the_changed_pupils(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    publish_a(app, gmc)
    ngozi = as_(app, "ngozi.okeke")
    status, ready = send(
        ngozi,
        "POST",
        reopen_url(gmc),
        {"reason": "Musa's comment names the wrong term.", "sections": True},
    )
    assert (status, ready["problems"]) == (200, ["Form teacher comments are not submitted"])
    section = db_session.execute(
        text("select status, revision from class_report_sections where arm_id = :a"),
        {"a": gmc["arm_a"]},
    ).one()
    assert (section.status, section.revision) == ("open", 2)
    assert code_of(
        send(ngozi, "POST", reopen_url(gmc), {"reason": "Again.", "sections": True})
    ) == (
        409,
        "wrong_status",
    )
    tunde = as_(app, "tunde.adebayo")
    url = f"/form-class/{gmc['arm_a']}"
    body = {"comment": "Musa improved steadily this First Term."}
    assert send(tunde, "PUT", f"{url}/students/{gmc['pupils']['Musa']}/entry", body)[0] == 200
    assert send(tunde, "POST", f"{url}/sections/submit")[0] == 200
    emails = db_session.scalar(text("select count(*) from email_outbox"))

    status, published = send(ngozi, "POST", f"/school/publications/{gmc['arm_a']}/publish")
    assert (status, [r["admission_number"] for r in published["reports"]]) == (
        200,
        ["GMC/2026/015"],
    )
    assert [(r[0], r[1], r[2]) for r in reports(db_session, gmc)] == [
        ("GMC/2026/014", 1, "valid"),
        ("GMC/2026/015", 1, "superseded"),
        ("GMC/2026/015", 2, "valid"),
        ("GMC/2026/016", 1, "valid"),
    ]
    recipients = set(
        db_session.scalars(
            text(
                "select r.user_id from notice_recipients r join notices n on n.id = r.notice_id"
                " where n.title like 'Updated%'"
            )
        )
    )
    assert recipients == {gmc["tunde"], gmc["amina"], gmc["emeka"]}  # Musa has no login or parent
    assert db_session.scalar(text("select count(*) from email_outbox")) == emails
