"""Report templates and publishing a class (BUILD_PROMPT 9.2i part 2 and 9.2k first part).

SPEC F10, F12, F13, F17, F18, F23; AC10.3, AC12.3, AC23.1; AT-16, AT-17.1, AT-17.2.

Behaviour: each level that is on has a report template (the defaults until
the school saves one; every save is a new version) whose blocks and settings
are checked (the footer with report ID, revision, date and QR is always shown
and last; no setting can hide them; only the core styles); a class publishes
only when every subject sheet is approved and, for the blocks the template
shows, the form teacher's sections are submitted and complete and the
principal's comments written. Publishing freezes a snapshot per pupil
(results from the engine, structure, bands, template version, calculation
version), stores revision 1 Valid reports with report IDs and verification
codes, records Students needing attention, posts a notice to the class's
audience only and queues one email per recipient with an email, never with
scores. A report is revoked only with a reason. All data is fictional.
"""

import re
import uuid
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.grading.setup import ensure_defaults
from schoolflow_api.reports.publication import report_codes
from tests.auth_support import build_auth_app, csrf, logged_in, make_login, use_fast_hashing
from tests.factories import (
    add_arm_subject,
    add_reviewer_scope,
    add_student_subject,
    assign_teacher,
    create_arm,
    create_class,
    create_department,
    create_guardian,
    create_school,
    create_session,
    create_student,
    create_subject,
    create_term,
    enrol,
    link_ward,
)

SCORES = {  # CA1, CA2, Exam
    "maths": {"Chukwuemeka": (16, 15, 47), "Musa": (10, 10, 18), "Zainab": (16, 15, 47)},
    "english": {"Chukwuemeka": (15, 15, 40), "Musa": (12, 12, 30), "Zainab": (14, 14, 32)},
}


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
    term = create_term(s, school, year, 1, is_active=True)
    ensure_defaults(s, school, "school_admin")
    jss1 = create_class(s, school, "junior_secondary", "JSS 1")
    arm_a, arm_b = create_arm(s, school, jss1, "A"), create_arm(s, school, jss1, "B")
    sciences = create_department(s, school, "Sciences")
    maths = create_subject(s, school, "Mathematics", department_id=sciences)
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
        "amina": person("amina.bello", "Amina Bello"),
        "emeka": person("emeka.nwosu", "Emeka Nwosu", "reviewer"),
        "ngozi": person("ngozi.okeke", "Ngozi Okeke", "school_admin", is_primary=True),
        "grace": person("grace.etim", "Grace Etim"),
    }
    assign_teacher(s, school, people["tunde"], arm_a, maths)
    assign_teacher(s, school, people["tunde"], arm_a, form_teacher=True)
    assign_teacher(s, school, people["amina"], arm_a, english)
    assign_teacher(s, school, people["grace"], arm_b, maths)
    add_reviewer_scope(s, school, people["emeka"], department_id=sciences)

    pupils: dict[str, uuid.UUID] = {}
    students: dict[str, uuid.UUID] = {}
    for admission, surname, first, arm in (
        ("GMC/2026/014", "Obi", "Chukwuemeka", arm_a),
        ("GMC/2026/015", "Ibrahim", "Musa", arm_a),
        ("GMC/2026/016", "Yusuf", "Zainab", arm_a),
        ("GMC/2026/030", "Eze", "Kosi", arm_b),
    ):
        login = None
        if first == "Chukwuemeka":
            login = make_login(
                s,
                username="chukwuemeka.obi",
                email="chukwuemeka@pupil.example",
                school_id=school,
                student=True,
            )
        student = create_student(s, school, admission, surname, first, user_id=login)
        enrolment = enrol(s, school, student, year, arm)
        for subject in (maths, english):
            add_student_subject(s, school, enrolment, subject)
        pupils[first], students[first] = enrolment, student
    ikenna = person("ikenna.obi", "Ikenna Obi", "parent", email="ikenna@home.example")
    link_ward(
        s, school, create_guardian(s, school, "Ikenna Obi", user_id=ikenna), students["Chukwuemeka"]
    )
    ada = person("ada.eze", "Ada Eze", "parent", email="ada@home.example")
    link_ward(s, school, create_guardian(s, school, "Ada Eze", user_id=ada), students["Kosi"])
    return {
        "school": school,
        "term": term,
        "arm_a": arm_a,
        "arm_b": arm_b,
        "maths": maths,
        "english": english,
        "pupils": pupils,
        "students": students,
        "ikenna": ikenna,
        "ada": ada,
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


def enter_and_submit(app: FastAPI, gmc: dict[str, Any], subject: str, username: str) -> str:
    teacher = as_(app, username)
    sheet = send(
        teacher, "POST", "/sheets", {"arm_id": str(gmc["arm_a"]), "subject_id": str(gmc[subject])}
    )[1]
    cells = [
        {"enrolment_id": str(gmc["pupils"][pupil]), "component_id": column["id"], "value": value}
        for pupil, values in SCORES[subject].items()
        for column, value in zip(sheet["columns"], values, strict=True)
    ]
    assert send(teacher, "PUT", f"/sheets/{sheet['id']}/scores", {"scores": cells})[0] == 200
    assert send(teacher, "POST", f"/sheets/{sheet['id']}/submit")[0] == 200
    return str(sheet["id"])


def approve_all(app: FastAPI, gmc: dict[str, Any]) -> None:
    maths = enter_and_submit(app, gmc, "maths", "tunde.adebayo")
    english = enter_and_submit(app, gmc, "english", "amina.bello")
    assert send(as_(app, "emeka.nwosu"), "POST", f"/sheets/{maths}/review")[0] == 200
    ngozi = as_(app, "ngozi.okeke")
    for sheet in (maths, english):
        assert send(ngozi, "POST", f"/sheets/{sheet}/approve")[0] == 200


def complete_my_class(app: FastAPI, gmc: dict[str, Any], *, submit: bool = True) -> None:
    tunde = as_(app, "tunde.adebayo")
    url = f"/form-class/{gmc['arm_a']}"
    send(tunde, "PUT", f"{url}/attendance-days", {"times_school_opened": 60})
    _, view = send(tunde, "GET", url)
    ratings = {t["id"]: 4 for t in view["traits"]}
    for pupil, present in (("Chukwuemeka", 57), ("Musa", 50), ("Zainab", 60)):
        assert (
            send(
                tunde,
                "PUT",
                f"{url}/students/{gmc['pupils'][pupil]}/entry",
                {
                    "comment": f"{pupil} worked well this term.",
                    "times_present": present,
                    "ratings": ratings,
                },
            )[0]
            == 200
        )
    if submit:
        assert send(tunde, "POST", f"{url}/sections/submit")[0] == 200


def principal_comments(app: FastAPI, gmc: dict[str, Any]) -> None:
    status, _ = send(
        as_(app, "ngozi.okeke"),
        "PUT",
        f"/school/publications/{gmc['arm_a']}/principal-comments",
        {
            "comments": [
                {"enrolment_id": str(e), "comment": "Well done."}
                for e in gmc["pupils"].values()
                if e != gmc["pupils"]["Kosi"]
            ]
        },
    )
    assert status == 200


# --- report templates (F12; AC12.3) --------------------------------------------------------------


def test_templates_start_from_the_defaults_and_save_versions(
    app: FastAPI, gmc: dict[str, Any]
) -> None:
    ngozi = as_(app, "ngozi.okeke")
    status, templates = send(ngozi, "GET", "/school/report-templates")
    assert status == 200
    by_level = {t["level"]: t for t in templates}
    assert set(by_level) == {"junior_secondary", "senior_secondary"}
    jss = by_level["junior_secondary"]
    assert (jss["card"], jss["style"], jss["version"]) == ("scores", "modern", None)
    assert jss["settings"]["blocks"][-1] == "footer"

    settings = jss["settings"]
    settings["hidden"] = ["affective_psychomotor"]
    settings["summary"]["overall_position"] = False
    status, saved = send(
        ngozi,
        "PUT",
        "/school/report-templates/junior_secondary",
        {"style": "compact", "settings": settings},
    )
    assert (status, saved["version"], saved["style"]) == (200, 1, "compact")
    status, again = send(
        ngozi,
        "PUT",
        "/school/report-templates/junior_secondary",
        {"style": "classic", "settings": settings},
    )
    assert again["version"] == 2
    assert send(ngozi, "GET", "/school/report-templates")[1][0]["version"] == 2


def test_the_footer_and_its_report_id_and_qr_cannot_be_hidden(
    app: FastAPI, gmc: dict[str, Any]
) -> None:
    """AC12.3."""
    ngozi = as_(app, "ngozi.okeke")
    base = send(ngozi, "GET", "/school/report-templates")[1][0]["settings"]
    url = "/school/report-templates/junior_secondary"
    blocks = base["blocks"]
    moved = [*blocks[-1:], *blocks[:-1]]
    for bad in (
        {**base, "hidden": ["footer"]},
        {**base, "blocks": moved},
        {**base, "blocks": blocks[1:]},
        {**base, "footer": {**base["footer"], "show_report_id": False}},
        {**base, "footer": {**base["footer"], "qr_code": False}},
        {**base, "subject_table": {**base["subject_table"], "unknown": True}},
    ):
        assert send(ngozi, "PUT", url, {"style": "modern", "settings": bad})[0] == 422, bad
    assert send(ngozi, "PUT", url, {"style": "bold_banner", "settings": base})[0] == 422
    assert send(ngozi, "PUT", url, {"style": "early_years", "settings": base})[0] == 200
    assert code_of(
        send(as_(app, "tunde.adebayo"), "PUT", url, {"style": "modern", "settings": base})
    ) == (403, "permission_denied")
    assert code_of(
        send(
            ngozi, "PUT", "/school/report-templates/nursery", {"style": "modern", "settings": base}
        )
    ) == (404, "level_disabled")


# --- readiness and principal's comments (AT-16.1, AC10.3) ----------------------------------------


def test_publishing_waits_for_every_sheet_and_the_class_sections(
    app: FastAPI, gmc: dict[str, Any]
) -> None:
    ngozi = as_(app, "ngozi.okeke")
    url = f"/school/publications/{gmc['arm_a']}"
    status, ready = send(ngozi, "GET", url)
    assert (status, ready["ready"]) == (200, False)
    assert "English Language: not started" in ready["problems"]
    assert "Form teacher comments are not submitted" in ready["problems"]

    approve_all(app, gmc)
    complete_my_class(app, gmc, submit=False)
    ready = send(ngozi, "GET", url)[1]
    assert ready["problems"] == [
        "Form teacher comments are not submitted",
        "Principal's comments are missing for 3 students",
    ]
    status, body = send(ngozi, "POST", f"{url}/publish")
    assert (status, body["code"]) == (409, "not_ready")
    assert "Form teacher comments are not submitted" in body["detail"]

    send(as_(app, "tunde.adebayo"), "POST", f"/form-class/{gmc['arm_a']}/sections/submit")
    principal_comments(app, gmc)
    assert send(ngozi, "GET", url)[1] == {
        "ready": True,
        "problems": [],
        "class_name": "JSS 1A",
        "status": "approved",
    }


def test_principals_comments(app: FastAPI, db_session: Session, gmc: dict[str, Any]) -> None:
    url = f"/school/publications/{gmc['arm_a']}/principal-comments"
    one = [{"enrolment_id": str(gmc["pupils"]["Musa"]), "comment": "A good effort."}]
    assert send(as_(app, "ngozi.okeke"), "PUT", url, {"comments": one})[0] == 200
    assert db_session.scalar(text("select head_comment from student_term_entries")) == (
        "A good effort."
    )
    too_long = [{"enrolment_id": str(gmc["pupils"]["Musa"]), "comment": "x" * 301}]
    assert send(as_(app, "ngozi.okeke"), "PUT", url, {"comments": too_long})[0] == 422
    other = [{"enrolment_id": str(gmc["pupils"]["Kosi"]), "comment": "Not this class."}]
    assert send(as_(app, "ngozi.okeke"), "PUT", url, {"comments": other})[0] == 404
    assert code_of(send(as_(app, "tunde.adebayo"), "PUT", url, {"comments": one})) == (
        403,
        "permission_denied",
    )


# --- publishing (AT-16.2, AT-16.4, AC23.1, AT-17) ------------------------------------------------


def test_publishing_freezes_reports_with_codes(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    approve_all(app, gmc)
    complete_my_class(app, gmc)
    principal_comments(app, gmc)
    ngozi = as_(app, "ngozi.okeke")
    status, done = send(ngozi, "POST", f"/school/publications/{gmc['arm_a']}/publish")
    assert status == 200, done
    assert done["published"] == 3
    codes = {r["admission_number"]: r for r in done["reports"]}
    assert codes["GMC/2026/014"]["report_code"] == "GMC-2627-T1-JSS1A-014"
    assert re.fullmatch(
        r"[0-9A-HJKMNP-TV-Z]{4}(-[0-9A-HJKMNP-TV-Z]{4}){2}",
        codes["GMC/2026/014"]["verification_code"],
    )
    reports = db_session.execute(
        text(
            "select revision, status, snapshot, calculation_version from report_documents"
            " where enrolment_id = :e"
        ),
        {"e": gmc["pupils"]["Chukwuemeka"]},
    ).all()
    assert [(r.revision, r.status, r.calculation_version) for r in reports] == [(1, "valid", "1.0")]
    snapshot = reports[0].snapshot
    maths = next(s for s in snapshot["subjects"] if s["name"] == "Mathematics")
    assert (maths["total"], maths["grade"], maths["position"], maths["highest"]) == (
        78,
        "A1",
        1,
        78,
    )
    assert maths["scores"] == {"CA1": 16, "CA2": 15, "Exam": 47}
    musa = db_session.scalar(
        text("select snapshot from report_documents where enrolment_id = :e"),
        {"e": gmc["pupils"]["Musa"]},
    )
    musa_maths = next(s for s in musa["subjects"] if s["name"] == "Mathematics")
    assert musa_maths["position"] == 3  # 1st, 1st, 3rd (AT-16.4)
    assert snapshot["template"]["version"] == 1
    assert snapshot["structure"] == [
        {"label": "CA1", "max_score": 20},
        {"label": "CA2", "max_score": 20},
        {"label": "Exam", "max_score": 60},
    ]
    assert snapshot["attendance"] == {
        "times_school_opened": 60,
        "times_present": 57,
        "times_absent": 3,
    }
    assert snapshot["comments"]["head"] == "Well done."
    assert snapshot["comments"]["head_title"] == "Principal"
    assert snapshot["summary"]["number_in_class"] == 3
    statuses = set(db_session.scalars(text("select status from result_sheets")))
    assert statuses == {"published"}
    assert db_session.scalar(text("select status from class_report_sections")) == "published"
    # Publishing twice is refused: nothing is approved any more.
    assert code_of(send(ngozi, "POST", f"/school/publications/{gmc['arm_a']}/publish")) == (
        409,
        "not_ready",
    )


def test_students_needing_attention_are_recorded_at_publication(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    """AC23.1: Musa's Mathematics 38 is below the pass mark of 40."""
    approve_all(app, gmc)
    complete_my_class(app, gmc)
    principal_comments(app, gmc)
    send(as_(app, "ngozi.okeke"), "POST", f"/school/publications/{gmc['arm_a']}/publish")
    entries = db_session.execute(
        text(
            "select a.kind, a.score, a.grade, a.pass_mark, a.failed_count, a.average,"
            " a.teacher_id, d.enrolment_id from attention_entries a"
            " join report_documents d on d.id = a.report_document_id order by a.kind"
        )
    ).all()
    assert [
        (e.kind, e.score, e.grade, e.pass_mark, e.teacher_id)
        for e in entries
        if e.kind == "subject"
    ] == [("subject", 38, "F9", 40, gmc["tunde"])]
    student = next(e for e in entries if e.kind == "student")
    assert (student.enrolment_id, student.failed_count, str(student.average)) == (
        gmc["pupils"]["Musa"],
        1,
        "46.00",
    )


def test_publication_tells_the_right_people_and_never_emails_scores(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    """AT-17.1, AT-17.2, AC18.1."""
    approve_all(app, gmc)
    complete_my_class(app, gmc)
    principal_comments(app, gmc)
    send(as_(app, "ngozi.okeke"), "POST", f"/school/publications/{gmc['arm_a']}/publish")
    notice = db_session.execute(text("select id, title, kind from notices")).one()
    assert (notice.title, notice.kind) == (
        "First Term results for JSS 1 are now available",
        "system",
    )
    recipients = set(
        db_session.scalars(
            text("select user_id from notice_recipients where notice_id = :n"), {"n": notice.id}
        )
    )
    pupil_login = db_session.scalar(text("select user_id from students where user_id is not null"))
    assert recipients == {pupil_login, gmc["ikenna"], gmc["tunde"], gmc["amina"], gmc["emeka"]}
    assert gmc["ada"] not in recipients  # a JSS 1B parent
    emails = db_session.execute(
        text(
            "select to_address, template, template_data from email_outbox"
            " where template = 'results_published' order by to_address"
        )
    ).all()
    assert [e.to_address for e in emails] == ["chukwuemeka@pupil.example", "ikenna@home.example"]
    for email in emails:
        text_of = str(email.template_data).lower()
        assert not any(word in text_of for word in ("78", "score", "grade", "position"))
        assert email.template_data["login_path"] == "/login"


def test_revoking_a_report_needs_a_reason(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    approve_all(app, gmc)
    complete_my_class(app, gmc)
    principal_comments(app, gmc)
    ngozi = as_(app, "ngozi.okeke")
    send(ngozi, "POST", f"/school/publications/{gmc['arm_a']}/publish")
    status, reports = send(ngozi, "GET", f"/school/reports?arm_id={gmc['arm_a']}")
    assert (status, len(reports)) == (200, 3)
    report = reports[0]
    url = f"/school/reports/{report['id']}/revoke"
    assert send(ngozi, "POST", url, {"reason": " "})[0] == 422
    assert code_of(send(as_(app, "tunde.adebayo"), "POST", url, {"reason": "Wrong pupil."})) == (
        403,
        "permission_denied",
    )
    status, revoked = send(ngozi, "POST", url, {"reason": "Issued to the wrong pupil."})
    assert (status, revoked["status"]) == (200, "revoked")
    assert code_of(send(ngozi, "POST", url, {"reason": "Again."})) == (409, "wrong_status")
    assert (
        db_session.scalar(
            text("select revoke_reason from report_documents where id = :r"), {"r": report["id"]}
        )
        == "Issued to the wrong pupil."
    )


# --- report IDs are different for every pupil (D-170) -------------------------------------------


def test_report_ids_never_repeat_in_a_class() -> None:
    def ids(admissions: list[str], **more: Any) -> dict[str, str]:
        return report_codes("GMC", "2026/2027", 1, "JSS 1A", admissions, **more)

    assert ids(["GMC/2026/014", "GMC/2026/015"]) == {
        "GMC/2026/014": "GMC-2627-T1-JSS1A-014",
        "GMC/2026/015": "GMC-2627-T1-JSS1A-015",
    }
    # The same last part: both use the full admission number.
    assert sorted(ids(["GMC/2026/014", "GMC/2025/014"]).values()) == [
        "GMC-2627-T1-JSS1A-GMC-2025-014",
        "GMC-2627-T1-JSS1A-GMC-2026-014",
    ]
    # Full numbers that read the same once tidied: a number is added.
    assert sorted(ids(["GMC/2026/014", "GMC-2026-014", "gmc 2026 014"]).values()) == [
        "GMC-2627-T1-JSS1A-GMC-2026-014",
        "GMC-2627-T1-JSS1A-GMC-2026-014-2",
        "GMC-2627-T1-JSS1A-GMC-2026-014-3",
    ]
    # Long numbers cut at 64 characters still differ.
    # (the second pair is cut just after a dash, which is dropped)
    long = ["A" * 70 + "/1", "A" * 70 + "-1", "A" * 70 + " 1", "B" * 45 + "/7/1", "B" * 45 + "/8/1"]
    codes = list(ids(long).values())
    assert len(set(codes)) == 5 and all(len(c) <= 64 for c in codes)
    assert all(re.fullmatch(r"[A-Z0-9]+(-[A-Z0-9]+)*", c) for c in codes)
    # An ID another pupil of the school holds this term is never reused.
    taken = {"GMC-2627-T1-JSS1A-014"}
    assert ids(["GMC/2026/014"], taken=taken) == {"GMC/2026/014": "GMC-2627-T1-JSS1A-014-2"}
    # A pupil keeps the ID of earlier revisions, and a newcomer never takes it.
    kept = {"GMC/2025/014": "GMC-2627-T1-JSS1A-014"}
    assert ids(["GMC/2025/014", "GMC/2026/014"], kept=kept) == {
        "GMC/2025/014": "GMC-2627-T1-JSS1A-014",
        "GMC/2026/014": "GMC-2627-T1-JSS1A-GMC-2026-014",
    }
