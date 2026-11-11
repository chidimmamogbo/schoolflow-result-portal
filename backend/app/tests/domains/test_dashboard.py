"""The dashboards (BUILD_PROMPT 9.2u; SPEC F16, F23 rule 6; AC19.9; D-179).

Behaviour: a school admin sees what is blocking release in the active term:
sheets awaiting submission, review and approval (a sheet no reviewer covers
waits for approval), class by class; missing and invalid scores; form teacher
sections still open; unusual score changes; open corrections; averages, pass
rate and the term trend from approved and published sheets only; the Students
needing attention card, from published results only; and the billing card. A
level that is off disappears. A feature that is off drops its part (and with
Results off the billing card still shows). Staff who teach or review see their
own sheets, class sections, review queue and attention count. Reminders post a
notice to the people who still owe work and nobody else. Parents and students
are refused. All data is fictional.
"""

import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.src.dashboard.services import UNUSUAL_PERCENT
from app.tests.auth_support import logged_in
from app.tests.domains.test_attention import publish_a
from app.tests.domains.test_publication import (
    app,
    approve_all,
    as_,
    code_of,
    complete_my_class,
    enter_and_submit,
    fast_hashing,
    gmc,
    send,
)
from app.tests.domains.test_ratings_and_workflow import rcs
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

__all__ = ["app", "fast_hashing", "gmc", "rcs"]

SCHOOL = "/dashboard/school"
STAFF = "/dashboard/staff"
REMIND = "/dashboard/reminders"
REPORTS = "/school/reports"


def school_view(app: FastAPI, username: str = "ngozi.okeke") -> dict[str, Any]:
    status, body = send(as_(app, username), "GET", SCHOOL)
    assert status == 200, body
    return body


def results_of(app: FastAPI, username: str = "ngozi.okeke") -> dict[str, Any]:
    results = school_view(app, username)["results"]
    assert results is not None
    return results


def staff_view(app: FastAPI, username: str) -> dict[str, Any]:
    status, body = send(as_(app, username), "GET", STAFF)
    assert status == 200, body
    return body


def switch_off(db: Session, school: uuid.UUID, feature: str) -> None:
    db.execute(
        text("update school_features set enabled = false where school_id = :s and feature = :f"),
        {"s": school, "f": feature},
    )


def open_maths(app: FastAPI, gmc: dict[str, Any], arm: str = "arm_a") -> tuple[TestClient, Any]:
    teacher = as_(app, "tunde.adebayo" if arm == "arm_a" else "grace.etim")
    body = {"arm_id": str(gmc[arm]), "subject_id": str(gmc["maths"])}
    status, sheet = send(teacher, "POST", "/sheets", body)
    assert status in (200, 201), sheet
    return teacher, sheet


def told_about(app: FastAPI, username: str, title_part: str) -> bool:
    status, board = send(as_(app, username), "GET", "/notices")
    assert status == 200, board
    return any(title_part in n["title"] for n in board["notices"])


def test_nothing_started_is_the_empty_state(app: FastAPI, gmc: dict[str, Any]) -> None:
    results = results_of(app)
    assert results["nothing_started"] is True
    assert results["sheets"] == {
        "awaiting_submission": 4,
        "awaiting_review": 0,
        "awaiting_approval": 0,
        "approved": 0,
        "published": 0,
        "total": 4,
    }
    assert results["attention"] is None


def test_each_sheet_is_counted_where_it_waits(app: FastAPI, gmc: dict[str, Any]) -> None:
    """Sciences has a reviewer, so Maths waits for review; English has none (D-142)."""
    enter_and_submit(app, gmc, "maths", "tunde.adebayo")
    english = enter_and_submit(app, gmc, "english", "amina.bello")
    results = results_of(app)
    assert results["nothing_started"] is False
    assert results["sheets"] == {
        "awaiting_submission": 2,
        "awaiting_review": 1,
        "awaiting_approval": 1,
        "approved": 0,
        "published": 0,
        "total": 4,
    }
    assert [(c["class_name"], c["awaiting_review"], c["awaiting_approval"], c["total"])
            for c in results["classes"]] == [("JSS 1A", 1, 1, 2), ("JSS 1B", 0, 0, 2)]  # fmt: skip

    assert send(as_(app, "ngozi.okeke"), "POST", f"/sheets/{english}/approve")[0] == 200
    sheets = results_of(app)["sheets"]
    assert (sheets["awaiting_approval"], sheets["approved"]) == (0, 1)


def test_a_reviewed_sheet_waits_for_approval(app: FastAPI, gmc: dict[str, Any]) -> None:
    maths = enter_and_submit(app, gmc, "maths", "tunde.adebayo")
    assert send(as_(app, "emeka.nwosu"), "POST", f"/sheets/{maths}/review")[0] == 200
    sheets = results_of(app)["sheets"]
    assert (sheets["awaiting_review"], sheets["awaiting_approval"]) == (0, 1)


def test_published_sheets_are_counted(app: FastAPI, gmc: dict[str, Any]) -> None:
    publish_a(app, gmc)
    sheets = results_of(app)["sheets"]
    assert (sheets["published"], sheets["approved"], sheets["total"]) == (2, 0, 4)


def test_missing_scores_count_started_sheets_only(app: FastAPI, gmc: dict[str, Any]) -> None:
    """Three pupils x three columns, one pupil entered: six missing. Not started: none."""
    teacher, sheet = open_maths(app, gmc)
    cells = [
        {"enrolment_id": str(gmc["pupils"]["Chukwuemeka"]), "component_id": c["id"], "value": 10}
        for c in sheet["columns"]
    ]
    assert send(teacher, "PUT", f"/sheets/{sheet['id']}/scores", {"scores": cells})[0] == 200
    missing = results_of(app)["missing_scores"]
    assert missing == {
        "count": 6,
        "sheets": [
            {"sheet_id": sheet["id"], "class_name": "JSS 1A", "name": "Mathematics", "count": 6}
        ],
    }


def test_pupils_who_left_owe_no_scores(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    open_maths(app, gmc)
    db_session.execute(
        text("update enrolments set left_on = current_date where id = :e"),
        {"e": gmc["pupils"]["Musa"]},
    )
    assert results_of(app)["missing_scores"]["count"] == 6


def test_an_approved_sheet_owes_nothing(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    """Even when a pupil joins the class after it was approved."""
    approve_all(app, gmc)
    assert results_of(app)["missing_scores"] == {"count": 0, "sheets": []}
    s = db_session
    year = s.scalar(text("select session_id from terms where id = :t"), {"t": gmc["term"]})
    assert year is not None
    late = create_student(s, gmc["school"], "GMC/2026/099", "Danjuma", "Halima")
    enrolment = enrol(s, gmc["school"], late, year, gmc["arm_a"])
    add_student_subject(s, gmc["school"], enrolment, gmc["maths"])
    assert results_of(app)["missing_scores"] == {"count": 0, "sheets": []}


def test_invalid_scores_are_found_if_one_ever_gets_past_the_database(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    """The database refuses a score above its column, so normally this stays at nought."""
    assert results_of(app)["invalid_scores"] == {"count": 0, "sheets": []}
    maths = enter_and_submit(app, gmc, "maths", "tunde.adebayo")
    db_session.execute(text("alter table scores disable trigger user"))
    db_session.execute(
        text(
            "update scores set value = 99 where sheet_id = :s and enrolment_id = :e"
            " and component_id = (select id from assessment_components ac"
            "   where ac.structure_id = (select structure_id from result_sheets where id = :s)"
            "   and ac.max_score < 60 order by ac.position limit 1)"
        ),
        {"s": maths, "e": gmc["pupils"]["Musa"]},
    )
    assert results_of(app)["invalid_scores"] == {
        "count": 1,
        "sheets": [{"sheet_id": maths, "class_name": "JSS 1A", "name": "Mathematics", "count": 1}],
    }


def test_open_form_teacher_sections_are_listed(app: FastAPI, gmc: dict[str, Any]) -> None:
    assert results_of(app)["open_sections"] == ["JSS 1A", "JSS 1B"]
    complete_my_class(app, gmc)
    assert results_of(app)["open_sections"] == ["JSS 1B"]


def test_a_big_change_after_submission_is_unusual(app: FastAPI, gmc: dict[str, Any]) -> None:
    """A reasoned change of a quarter of the column or more; a small one is not."""
    maths = enter_and_submit(app, gmc, "maths", "tunde.adebayo")
    assert results_of(app)["unusual_changes"] == []
    emeka, tunde = as_(app, "emeka.nwosu"), as_(app, "tunde.adebayo")
    body = {"comment": "Please check the marks."}
    assert send(emeka, "POST", f"/sheets/{maths}/return", body)[0] == 200
    sheet = send(tunde, "GET", f"/sheets/{maths}")[1]
    ca1, ca2 = sheet["columns"][0], sheet["columns"][1]
    assert ca2["max_score"] == 20
    musa = str(gmc["pupils"]["Musa"])
    just_enough = 10 + (ca2["max_score"] * UNUSUAL_PERCENT) // 100  # 10 to 15, 5 of 20
    changes = [
        {"enrolment_id": musa, "component_id": ca1["id"], "value": 11},  # up by 1: not unusual
        {"enrolment_id": musa, "component_id": ca2["id"], "value": just_enough},
    ]
    body = {"scores": changes, "reason": "Script remarked."}
    assert send(tunde, "PUT", f"/sheets/{maths}/scores", body)[0] == 200
    assert results_of(app)["unusual_changes"] == [
        {
            "sheet_id": maths,
            "student_name": "Musa Ibrahim",
            "class_name": "JSS 1A",
            "subject": "Mathematics",
            "column": ca2["label"],
            "old": 10,
            "new": just_enough,
            "reason": "Script remarked.",
        }
    ]


def test_a_change_in_a_draft_is_not_unusual(app: FastAPI, gmc: dict[str, Any]) -> None:
    """Before submission a teacher is still working: no reason, nothing to flag."""
    teacher, sheet = open_maths(app, gmc)
    ca2 = sheet["columns"][1]
    musa = str(gmc["pupils"]["Musa"])
    for value in (2, 18):
        cell = {"enrolment_id": musa, "component_id": ca2["id"], "value": value}
        assert send(teacher, "PUT", f"/sheets/{sheet['id']}/scores", {"scores": [cell]})[0] == 200
    assert results_of(app)["unusual_changes"] == []


def test_just_under_a_quarter_is_not_unusual(app: FastAPI, gmc: dict[str, Any]) -> None:
    maths = enter_and_submit(app, gmc, "maths", "tunde.adebayo")
    emeka, tunde = as_(app, "emeka.nwosu"), as_(app, "tunde.adebayo")
    send(emeka, "POST", f"/sheets/{maths}/return", {"comment": "Please check the marks."})
    ca2 = send(tunde, "GET", f"/sheets/{maths}")[1]["columns"][1]
    cell = {"enrolment_id": str(gmc["pupils"]["Musa"]), "component_id": ca2["id"], "value": 14}
    body = {"scores": [cell], "reason": "Added wrongly."}
    assert send(tunde, "PUT", f"/sheets/{maths}/scores", body)[0] == 200  # 10 to 14: 4 of 20
    assert results_of(app)["unusual_changes"] == []


def test_averages_and_pass_rate_use_approved_sheets_only(app: FastAPI, gmc: dict[str, Any]) -> None:
    """Totals 78, 38, 78 and 70, 54, 60: average 63.0; five of six at 40 or more."""
    stats = results_of(app)["stats"]
    assert (stats["average"], stats["pass_rate"], stats["sheets_counted"]) == (None, None, 0)
    maths = enter_and_submit(app, gmc, "maths", "tunde.adebayo")
    assert results_of(app)["stats"]["average"] is None  # submitted is not approved

    ngozi = as_(app, "ngozi.okeke")
    assert send(as_(app, "emeka.nwosu"), "POST", f"/sheets/{maths}/review")[0] == 200
    assert send(ngozi, "POST", f"/sheets/{maths}/approve")[0] == 200
    english = enter_and_submit(app, gmc, "english", "amina.bello")
    assert send(ngozi, "POST", f"/sheets/{english}/approve")[0] == 200

    stats = results_of(app)["stats"]
    assert stats["sheets_counted"] == 2
    assert (stats["average"], stats["pass_rate"]) == ("63.0", "83")
    assert stats["by_subject"] == [
        {"name": "English Language", "average": "61.3", "pass_rate": "100"},
        {"name": "Mathematics", "average": "64.7", "pass_rate": "67"},
    ]
    assert stats["by_class"] == [{"name": "JSS 1A", "average": "63.0", "pass_rate": "83"}]


def test_the_term_trend_runs_oldest_to_newest(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    approve_all(app, gmc)
    db_session.execute(text("update terms set is_active = false where id = :t"), {"t": gmc["term"]})
    year = db_session.scalar(text("select session_id from terms where id = :t"), {"t": gmc["term"]})
    assert year is not None
    create_term(db_session, gmc["school"], year, 2, is_active=True)
    results = results_of(app)
    assert results["stats"]["average"] is None  # the new term has nothing yet
    assert [t["average"] for t in results["stats"]["trend"]] == ["63.0"]
    assert results["stats"]["trend"][0]["term"].startswith("First Term ")

    approve_all(app, gmc)
    trend = results_of(app)["stats"]["trend"]
    assert [t["term"].split(" 2")[0] for t in trend] == ["First Term", "Second Term"]


def test_the_attention_card_comes_only_from_published_results(
    app: FastAPI, gmc: dict[str, Any]
) -> None:
    """AC23.1, F23 rule 7: approved is not enough, even with results below the pass mark."""
    assert results_of(app)["attention"] is None
    approve_all(app, gmc)
    assert results_of(app)["stats"]["sheets_counted"] == 2
    assert results_of(app)["attention"] is None
    assert staff_view(app, "tunde.adebayo")["attention"] is None


def test_the_attention_card_counts_by_role(app: FastAPI, gmc: dict[str, Any]) -> None:
    """AC23.2, AC23.3, F23 rule 6: the principal sees all; each teacher their own."""
    publish_a(app, gmc)
    card = results_of(app)["attention"]
    assert card["subject_results"] == 2
    assert card["students"] == 1
    assert card["pass_mark"] == 40
    assert card["term"].startswith("First Term ")
    assert staff_view(app, "tunde.adebayo")["attention"]["subject_results"] == 2  # form teacher
    assert staff_view(app, "amina.bello")["attention"]["subject_results"] == 1  # English only
    assert staff_view(app, "grace.etim")["attention"]["subject_results"] == 0  # JSS 1B Maths


def test_skill_ratings_levels_compute_nothing(
    app: FastAPI, db_session: Session, rcs: dict[str, Any]
) -> None:
    """Non-negotiable: ratings have no averages. They owe ratings, not scores."""
    grace = as_(app, "grace.etim")
    body = {"arm_id": str(rcs["n2"]), "learning_area_id": str(rcs["areas"]["Number work"])}
    view = send(grace, "POST", "/rating-sheets", body)[1]
    results = results_of(app, "femi.ade")
    assert results["missing_scores"]["count"] == 0
    assert results["missing_ratings"]["count"] == 2 * len(view["skills"])
    assert results["missing_ratings"]["sheets"][0]["name"] == "Number work"
    assert results["stats"]["average"] is None
    assert results["stats"]["by_class"] == []


def test_a_rating_for_a_pupil_who_left_does_not_hide_a_missing_one(
    app: FastAPI, db_session: Session, rcs: dict[str, Any]
) -> None:
    grace = as_(app, "grace.etim")
    body = {"arm_id": str(rcs["n2"]), "learning_area_id": str(rcs["areas"]["Number work"])}
    view = send(grace, "POST", "/rating-sheets", body)[1]
    ratings = [
        {
            "enrolment_id": str(rcs["pupils"]["Ada"]),
            "skill_id": skill["id"],
            "point_id": str(rcs["points"]["G"]),
        }
        for skill in view["skills"]
    ]
    assert (
        send(grace, "PUT", f"/rating-sheets/{view['id']}/ratings", {"ratings": ratings})[0] == 200
    )
    db_session.execute(
        text("update enrolments set left_on = current_date where id = :e"),
        {"e": rcs["pupils"]["Ada"]},
    )
    assert results_of(app, "femi.ade")["missing_ratings"]["count"] == len(view["skills"])


def test_a_level_that_is_off_disappears(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    """F25 rule 4."""
    publish_a(app, gmc)
    db_session.execute(
        text(
            "update school_levels set enabled = false where school_id = :s"
            " and level in ('junior_secondary', 'senior_secondary')"
        ),
        {"s": gmc["school"]},
    )
    results = results_of(app)
    assert results["classes"] == []
    assert results["sheets"]["total"] == 0
    assert results["open_sections"] == []
    assert results["stats"]["average"] is None
    assert results["stats"]["trend"] == []
    assert results["attention"]["subject_results"] == 0
    assert staff_view(app, "tunde.adebayo")["my_class"] == []
    assert staff_view(app, "tunde.adebayo")["sheets"]["total"] == 0


def test_the_billing_card_is_the_school_billing_answer(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    ngozi = as_(app, "ngozi.okeke")
    assert school_view(app)["billing"] == send(ngozi, "GET", "/school/billing")[1]
    db_session.execute(
        text("update school_subscriptions set billing_enabled = false where school_id = :s"),
        {"s": gmc["school"]},
    )
    card = school_view(app)["billing"]
    assert card["billing_enabled"] is False  # AC19.9, AT-36.5
    assert card["amount_due_kobo"] is None
    assert card["current_invoice"] is None


def test_open_corrections_are_counted_and_switch_off(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    db_session.execute(
        text(
            "update school_features set enabled = true"
            " where school_id = :s and feature = 'correction_queue'"
        ),
        {"s": gmc["school"]},
    )
    publish_a(app, gmc)
    assert school_view(app)["corrections_open"] == 0
    reports = send(as_(app, "ngozi.okeke"), "GET", REPORTS)[1]
    chuk = next(r for r in reports if r["enrolment_id"] == str(gmc["pupils"]["Chukwuemeka"]))
    body = {"report_id": chuk["id"], "issue_type": "score", "explanation": "My CA2 looks wrong."}
    status, request = send(as_(app, "ikenna.obi"), "POST", "/corrections", body)
    assert status == 201, request
    assert school_view(app)["corrections_open"] == 1
    ngozi, url = as_(app, "ngozi.okeke"), f"/corrections/{request['id']}/move"
    assert send(ngozi, "POST", url, {"status": "investigating"})[0] == 200
    assert school_view(app)["corrections_open"] == 1
    body = {"status": "rejected", "message": "The mark is correct."}
    assert send(ngozi, "POST", url, body)[0] == 200
    assert school_view(app)["corrections_open"] == 0
    switch_off(db_session, gmc["school"], "correction_queue")
    assert school_view(app)["corrections_open"] is None


def test_with_results_off_only_billing_is_left(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    """A feature that is off rejects requests; the billing card is not part of it."""
    switch_off(db_session, gmc["school"], "results")
    view = school_view(app)
    assert view["results"] is None
    assert "billing_enabled" in view["billing"]
    tunde = as_(app, "tunde.adebayo")
    assert code_of(send(tunde, "GET", STAFF)) == (404, "feature_disabled")
    body = {"audience": "teachers"}
    assert code_of(send(as_(app, "ngozi.okeke"), "POST", REMIND, body)) == (
        404,
        "feature_disabled",
    )


def test_no_active_term_gives_an_empty_dashboard(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    db_session.execute(text("update terms set is_active = false where id = :t"), {"t": gmc["term"]})
    view = school_view(app)
    assert (view["term"], view["results"]) == (None, None)
    assert "billing_enabled" in view["billing"]
    mine = staff_view(app, "tunde.adebayo")
    assert (mine["term"], mine["attention"], mine["my_class"]) == (None, None, [])
    assert mine["sheets"]["total"] == 0
    body = {"audience": "teachers"}
    assert code_of(send(as_(app, "ngozi.okeke"), "POST", REMIND, body)) == (409, "no_active_term")


def test_only_school_admins_open_the_school_dashboard(app: FastAPI, gmc: dict[str, Any]) -> None:
    for client in (
        as_(app, "tunde.adebayo"),
        as_(app, "emeka.nwosu"),
        as_(app, "ikenna.obi"),
        logged_in(app, "chukwuemeka.obi", school_code="GMC"),
    ):
        assert send(client, "GET", SCHOOL)[0] == 403


def test_parents_and_students_get_no_staff_dashboard(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    # With no active term too: the refusal must not depend on there being work to show.
    db_session.execute(text("update terms set is_active = false where id = :t"), {"t": gmc["term"]})
    for client in (as_(app, "ikenna.obi"), logged_in(app, "chukwuemeka.obi", school_code="GMC")):
        assert send(client, "GET", STAFF)[0] == 403


def test_it_needs_a_session(app: FastAPI) -> None:
    client = TestClient(app)
    for url in (SCHOOL, STAFF):
        assert client.get(f"/api/v1{url}").status_code == 401
    assert client.post(f"/api/v1{REMIND}", json={"audience": "teachers"}).status_code in (401, 403)


def test_another_schools_classes_never_show(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    s = db_session
    other = create_school(s, code="BSA", name="Bright Stars Academy")
    year = create_session(s, other)
    create_term(s, other, year, 1, is_active=True)
    primary = create_class(s, other, "junior_secondary", "JSS 9")
    arm = create_arm(s, other, primary, "Z")
    subject = create_subject(s, other, "Hidden Subject")
    add_arm_subject(s, other, arm, subject)
    enrolment = enrol(s, other, create_student(s, other, "BSA/2026/001", "Eze", "Uche"), year, arm)
    add_student_subject(s, other, enrolment, subject)
    results = results_of(app)
    assert [c["class_name"] for c in results["classes"]] == ["JSS 1A", "JSS 1B"]
    assert "JSS 9" not in str(results) and "Hidden Subject" not in str(results)


def test_staff_see_their_own_sheets(app: FastAPI, gmc: dict[str, Any]) -> None:
    maths = enter_and_submit(app, gmc, "maths", "tunde.adebayo")
    assert staff_view(app, "tunde.adebayo")["sheets"] == {
        "to_do": 0,
        "returned": 0,
        "waiting": 1,
        "done": 0,
        "total": 1,
    }
    assert staff_view(app, "amina.bello")["sheets"]["to_do"] == 1
    assert staff_view(app, "amina.bello")["review_waiting"] is None

    emeka = staff_view(app, "emeka.nwosu")
    assert emeka["review_waiting"] == 1
    assert emeka["sheets"]["total"] == 0

    send(as_(app, "emeka.nwosu"), "POST", f"/sheets/{maths}/return", {"comment": "Please check."})
    assert staff_view(app, "tunde.adebayo")["sheets"]["returned"] == 1
    assert staff_view(app, "emeka.nwosu")["review_waiting"] == 0


def test_form_teachers_see_their_own_class(app: FastAPI, gmc: dict[str, Any]) -> None:
    assert staff_view(app, "amina.bello")["my_class"] == []
    mine = staff_view(app, "tunde.adebayo")["my_class"]
    assert mine == [{"arm_id": str(gmc["arm_a"]), "class_name": "JSS 1A", "status": "open"}]
    complete_my_class(app, gmc)
    assert staff_view(app, "tunde.adebayo")["my_class"][0]["status"] == "submitted"


def test_a_school_admin_who_teaches_has_a_staff_dashboard(
    app: FastAPI, rcs: dict[str, Any]
) -> None:
    """D-144: teaching comes from assignments, not the role."""
    assert staff_view(app, "dayo.vp")["sheets"]["total"] == 1


def test_a_reminder_reaches_only_form_teachers_with_open_sections(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    ngozi = as_(app, "ngozi.okeke")
    status, body = send(ngozi, "POST", REMIND, {"audience": "form_teachers"})
    assert (status, body) == (200, {"reminded": 1})
    assert told_about(app, "tunde.adebayo", "form class")
    for username in ("amina.bello", "grace.etim", "emeka.nwosu", "ikenna.obi"):
        assert not told_about(app, username, "form class"), username
    event = db_session.execute(
        text(
            "select new_values from audit_events where action = 'dashboard.remind'"
            " and school_id = :s"
        ),
        {"s": gmc["school"]},
    ).scalar_one()
    assert event["audience"] == "form_teachers" and event["recipients"] == 1
    # A notice, not an email.
    assert (
        db_session.scalar(
            text("select count(*) from email_outbox where school_id = :s"), {"s": gmc["school"]}
        )
        == 0
    )


def test_nobody_is_reminded_once_the_sections_are_in(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    complete_my_class(app, gmc)
    ngozi = as_(app, "ngozi.okeke")
    assert send(ngozi, "POST", REMIND, {"audience": "form_teachers"})[1] == {"reminded": 0}
    assert not told_about(app, "tunde.adebayo", "form class")
    # No notice at all: one with no readers would still show on the school's list.
    assert (
        db_session.scalar(
            text("select count(*) from notices where school_id = :s and title like '%form class%'"),
            {"s": gmc["school"]},
        )
        == 0
    )


def test_a_reminder_skips_teachers_who_have_submitted(app: FastAPI, gmc: dict[str, Any]) -> None:
    enter_and_submit(app, gmc, "maths", "tunde.adebayo")
    ngozi = as_(app, "ngozi.okeke")
    assert send(ngozi, "POST", REMIND, {"audience": "teachers"})[1] == {"reminded": 2}
    assert told_about(app, "amina.bello", "result sheets")
    assert told_about(app, "grace.etim", "result sheets")
    for username in ("tunde.adebayo", "emeka.nwosu", "ngozi.okeke", "ikenna.obi"):
        assert not told_about(app, username, "result sheets"), username


def test_a_reminder_skips_people_no_longer_active(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    db_session.execute(
        text(
            "update school_memberships set status = 'paused'"
            " where user_id = (select id from users where username = 'grace.etim')"
        )
    )
    ngozi = as_(app, "ngozi.okeke")
    assert send(ngozi, "POST", REMIND, {"audience": "teachers"})[1] == {"reminded": 2}


def test_reminders_are_for_school_admins_and_need_the_notice_board(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    body = {"audience": "teachers"}
    for client in (
        as_(app, "tunde.adebayo"),
        as_(app, "emeka.nwosu"),
        as_(app, "ikenna.obi"),
        logged_in(app, "chukwuemeka.obi", school_code="GMC"),
    ):
        assert send(client, "POST", REMIND, body)[0] == 403
    ngozi = as_(app, "ngozi.okeke")
    assert send(ngozi, "POST", REMIND, {"audience": "everyone"})[0] == 422
    assert send(ngozi, "POST", REMIND, {"audience": "teachers", "extra": 1})[0] == 422
    switch_off(db_session, gmc["school"], "notice_board")
    assert code_of(send(ngozi, "POST", REMIND, body)) == (404, "feature_disabled")
