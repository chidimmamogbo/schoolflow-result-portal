"""Score entry and CSV import (BUILD_PROMPT 9.2h; SPEC F06 rule 3, F09; D-047, D-143, D-144).

Behaviour: a teacher's sheets are exactly their assignments in the active
term (subjects they teach, every subject of an arm they assist), shown even
before a draft exists; opening one makes the draft (and the term's
structure if none was saved). A sheet shows the structure's columns and only
the pupils who take the subject, with totals, grades and the missing and
out-of-range flags from the results engine. Only the assigned teacher or an
assistant saves scores: whole numbers within each column's maximum, for
pupils on the sheet, all or nothing; after a submission a change needs a
reason. CSV: a template from the structure, an import previewed and
committed all or nothing, an error file, an export. Anyone else, another
school, a level that is off or Results switched off are refused. All data
is fictional.
"""

import csv
import io
import uuid
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.db import use_context
from tests.auth_support import build_auth_app, csrf, logged_in, make_login, use_fast_hashing
from tests.factories import (
    add_arm_subject,
    add_assistant,
    add_student_subject,
    assign_teacher,
    create_arm,
    create_class,
    create_school,
    create_session,
    create_structure,
    create_student,
    create_subject,
    create_term,
    enrol,
    move_sheet,
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
    term = create_term(s, school, year, 1, is_active=True)
    jss1 = create_class(s, school, "junior_secondary", "JSS 1")
    arm_a, arm_b = create_arm(s, school, jss1, "A"), create_arm(s, school, jss1, "B")
    maths = create_subject(s, school, "Mathematics")
    english = create_subject(s, school, "English Language")
    for arm in (arm_a, arm_b):
        for subject in (maths, english):
            add_arm_subject(s, school, arm, subject)

    def staff(username: str, full_name: str, role: str = "teacher", **kw: Any) -> uuid.UUID:
        return make_login(
            s, username=username, full_name=full_name, school_id=school, role=role, **kw
        )

    people = {
        "tunde": staff("tunde.adebayo", "Tunde Adebayo"),
        "grace": staff("grace.etim", "Grace Etim"),
        "bola": staff("bola.ige", "Bola Ige"),
        "ngozi": staff("ngozi.okeke", "Ngozi Okeke", "school_admin", is_primary=True),
        "parent": staff("ikenna.obi", "Ikenna Obi", "parent"),
    }
    for arm in (arm_a, arm_b):
        assign_teacher(s, school, people["tunde"], arm, maths)
    assign_teacher(s, school, people["grace"], arm_a, english)
    add_assistant(s, school, arm_a, people["bola"])

    pupils: dict[str, uuid.UUID] = {}
    for admission, surname, first, arm, subjects in (
        ("GMC/2026/014", "Obi", "Chukwuemeka", arm_a, (maths, english)),
        ("GMC/2026/015", "Ibrahim", "Musa", arm_a, (maths,)),
        ("GMC/2026/016", "Yusuf", "Zainab", arm_a, (maths, english)),
        ("GMC/2026/017", "Eze", "Kosi", arm_b, (maths, english)),
    ):
        student = create_student(s, school, admission, surname, first)
        enrolment = enrol(s, school, student, year, arm)
        for subject in subjects:
            add_student_subject(s, school, enrolment, subject)
        pupils[first] = enrolment
    return {
        "school": school,
        "year": year,
        "term": term,
        "arm_a": arm_a,
        "arm_b": arm_b,
        "maths": maths,
        "english": english,
        "pupils": pupils,
        **people,
    }


def client(app: FastAPI, username: str) -> TestClient:
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


def open_sheet(c: TestClient, arm: uuid.UUID, subject: uuid.UUID) -> dict[str, Any]:
    status, body = send(c, "POST", "/sheets", {"arm_id": str(arm), "subject_id": str(subject)})
    assert status in {200, 201}, body
    return cast(dict[str, Any], body)


def columns(sheet: dict[str, Any]) -> dict[str, str]:
    return {col["label"]: col["id"] for col in sheet["columns"]}


def cells(sheet: dict[str, Any], pupil: uuid.UUID, **values: int | None) -> list[dict[str, Any]]:
    cols = columns(sheet)
    return [
        {"enrolment_id": str(pupil), "component_id": cols[label], "value": value}
        for label, value in values.items()
    ]


def row_of(sheet: dict[str, Any], pupil: uuid.UUID) -> dict[str, Any]:
    return next(r for r in sheet["rows"] if r["enrolment_id"] == str(pupil))


# --- which sheets (AT-10.1, AT-10.2) ----------------------------------------------------


def test_each_teacher_sees_exactly_their_assignments(app: FastAPI, gmc: dict[str, Any]) -> None:
    def mine(username: str) -> set[tuple[str, str, str]]:
        status, rows = send(client(app, username), "GET", "/sheets")
        assert status == 200, rows
        return {(r["class_name"], r["subject_name"], r["status"]) for r in rows}

    assert mine("tunde.adebayo") == {
        ("JSS 1A", "Mathematics", "not_started"),
        ("JSS 1B", "Mathematics", "not_started"),
    }
    assert mine("grace.etim") == {("JSS 1A", "English Language", "not_started")}
    # An assistant sees every subject sheet of their arm (F06 rule 3).
    assert mine("bola.ige") == {
        ("JSS 1A", "Mathematics", "not_started"),
        ("JSS 1A", "English Language", "not_started"),
    }
    assert mine("ngozi.okeke") == set()  # no teaching assignment
    assert code_of(send(client(app, "ikenna.obi"), "GET", "/sheets")) == (403, "permission_denied")


def test_opening_a_sheet_makes_the_draft_and_the_terms_structure(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    tunde = client(app, "tunde.adebayo")
    status, sheet = send(
        tunde, "POST", "/sheets", {"arm_id": str(gmc["arm_a"]), "subject_id": str(gmc["maths"])}
    )
    assert status == 201, sheet
    assert (sheet["status"], sheet["revision"], sheet["can_edit"]) == ("draft", 1, True)
    assert [(c["label"], c["max_score"]) for c in sheet["columns"]] == [
        ("CA1", 20),
        ("CA2", 20),
        ("Exam", 60),
    ]
    assert db_session.scalar(text("select count(*) from assessment_structures")) == 1
    status, again = send(
        tunde, "POST", "/sheets", {"arm_id": str(gmc["arm_a"]), "subject_id": str(gmc["maths"])}
    )
    assert (status, again["id"]) == (200, sheet["id"])
    assert send(tunde, "GET", "/sheets")[1][0]["status"] in {"draft", "not_started"}
    # Not his subject: refused like a sheet that does not exist.
    assert (
        send(
            tunde,
            "POST",
            "/sheets",
            {"arm_id": str(gmc["arm_a"]), "subject_id": str(gmc["english"])},
        )[0]
        == 404
    )
    # The principal reads sheets but does not open one for a subject she does not teach.
    principal = client(app, "ngozi.okeke")
    english_b = {"arm_id": str(gmc["arm_b"]), "subject_id": str(gmc["english"])}
    assert send(principal, "POST", "/sheets", english_b)[0] == 404
    assert db_session.scalar(text("select count(*) from result_sheets")) == 1


def test_a_sheet_uses_an_existing_structure(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    from schoolflow_api.grading.defaults import Component

    create_structure(
        db_session,
        gmc["school"],
        "junior_secondary",
        gmc["term"],
        (Component("Test", "Test", 40), Component("Examination", "Exam", 60)),
    )
    sheet = open_sheet(client(app, "tunde.adebayo"), gmc["arm_a"], gmc["maths"])
    assert [c["label"] for c in sheet["columns"]] == ["Test", "Exam"]


def test_only_pupils_taking_the_subject_are_listed(app: FastAPI, gmc: dict[str, Any]) -> None:
    """AC05.2, AT-08.6, AT-10.3 (search is client-side over these rows)."""
    english = open_sheet(client(app, "grace.etim"), gmc["arm_a"], gmc["english"])
    assert [(r["surname"], r["first_name"], r["admission_number"]) for r in english["rows"]] == [
        ("Obi", "Chukwuemeka", "GMC/2026/014"),
        ("Yusuf", "Zainab", "GMC/2026/016"),
    ]


def test_other_peoples_sheets_are_not_found(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    """AT-10.2, AC06.1, D-047."""
    english = open_sheet(client(app, "grace.etim"), gmc["arm_a"], gmc["english"])
    tunde = client(app, "tunde.adebayo")
    assert send(tunde, "GET", f"/sheets/{english['id']}")[0] == 404
    assert send(tunde, "PUT", f"/sheets/{english['id']}/scores", {"scores": []})[0] == 404
    # The principal may read any sheet of the school but enters nothing she does not teach.
    ngozi = client(app, "ngozi.okeke")
    status, seen = send(ngozi, "GET", f"/sheets/{english['id']}")
    assert (status, seen["can_edit"]) == (200, False)
    assert code_of(send(ngozi, "PUT", f"/sheets/{english['id']}/scores", {"scores": []})) == (
        403,
        "not_assigned",
    )
    # Another school's teacher never finds it.
    bsa = create_school(db_session, code="BSA", name="Bright Stars Academy")
    make_login(db_session, username="bsa.teacher", school_id=bsa)
    assert send(client(app, "bsa.teacher"), "GET", f"/sheets/{english['id']}")[0] == 404


def test_results_switched_off_rejects_every_sheet_route(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    """AT-27.2."""
    tunde = client(app, "tunde.adebayo")
    sheet = open_sheet(tunde, gmc["arm_a"], gmc["maths"])
    db_session.execute(text("update school_features set enabled = false where feature = 'results'"))
    for method, url in (
        ("GET", "/sheets"),
        ("GET", f"/sheets/{sheet['id']}"),
        ("PUT", f"/sheets/{sheet['id']}/scores"),
    ):
        assert code_of(send(tunde, method, url, {"scores": []})) == (404, "feature_disabled")


# --- saving scores (AT-10.4, AT-11.2) -------------------------------------------------------


def test_entering_marks_shows_the_total_and_records_the_author(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    tunde = client(app, "tunde.adebayo")
    sheet = open_sheet(tunde, gmc["arm_a"], gmc["maths"])
    chukwuemeka = gmc["pupils"]["Chukwuemeka"]
    status, sheet = send(
        tunde,
        "PUT",
        f"/sheets/{sheet['id']}/scores",
        {"scores": cells(sheet, chukwuemeka, CA1=16, CA2=15, Exam=47)},
    )
    assert status == 200, sheet
    row = row_of(sheet, chukwuemeka)
    assert (row["total"], row["grade"], row["missing"]) == (78, "A1", [])
    assert sheet["counts"] == {"complete": 1, "missing": 2, "errors": 0}
    assert row_of(sheet, gmc["pupils"]["Musa"])["missing"] == ["CA1", "CA2", "Exam"]
    authors = set(db_session.scalars(text("select entered_by from scores")))
    assert authors == {gmc["tunde"]}
    audit = db_session.execute(
        text("select actor_id, new_values from audit_events where action = 'scores.save'")
    ).one()
    assert audit.actor_id == gmc["tunde"]
    assert len(audit.new_values["cells"]) == 3


def test_bad_scores_are_refused_and_nothing_is_saved(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    """AT-11.2: -1, 61 for an Exam out of 60, 15.5; pupils and columns not on the sheet."""
    tunde = client(app, "tunde.adebayo")
    sheet = open_sheet(tunde, gmc["arm_a"], gmc["maths"])
    url = f"/sheets/{sheet['id']}/scores"
    zainab, kosi = gmc["pupils"]["Zainab"], gmc["pupils"]["Kosi"]
    good = cells(sheet, zainab, CA1=10)
    for bad in (
        cells(sheet, zainab, CA2=-1),
        cells(sheet, zainab, Exam=61),
        cells(sheet, kosi, CA1=10),
        [{**good[0], "component_id": str(uuid.uuid4())}],
    ):
        status, body = send(tunde, "PUT", url, {"scores": good + bad})
        assert (status, body["code"]) == (422, "invalid_scores"), bad
        assert len(body["errors"]) == 1
    assert send(tunde, "PUT", url, {"scores": [{**good[0], "value": 15.5}]})[0] == 422
    assert send(tunde, "PUT", url, {"scores": [{**good[0], "value": "15"}]})[0] == 422
    assert db_session.scalar(text("select count(*) from scores")) == 0


def test_an_assistant_enters_marks_on_their_own_arm_only(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    """F06 rule 3: every entry records who made it."""
    maths_a = open_sheet(client(app, "tunde.adebayo"), gmc["arm_a"], gmc["maths"])
    maths_b = open_sheet(client(app, "tunde.adebayo"), gmc["arm_b"], gmc["maths"])
    bola = client(app, "bola.ige")
    status, _ = send(
        bola,
        "PUT",
        f"/sheets/{maths_a['id']}/scores",
        {"scores": cells(maths_a, gmc["pupils"]["Musa"], CA1=12)},
    )
    assert status == 200
    assert db_session.scalar(text("select entered_by from scores")) == gmc["bola"]
    assert send(bola, "GET", f"/sheets/{maths_b['id']}")[0] == 404


def test_after_a_submission_changes_need_a_reason(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    """D-143."""
    tunde = client(app, "tunde.adebayo")
    sheet = open_sheet(tunde, gmc["arm_a"], gmc["maths"])
    url = f"/sheets/{sheet['id']}/scores"
    musa = gmc["pupils"]["Musa"]
    send(tunde, "PUT", url, {"scores": cells(sheet, musa, CA1=12)})
    send(tunde, "PUT", url, {"scores": cells(sheet, musa, CA1=13)})  # first draft: free
    every = [
        cell
        for pupil in ("Chukwuemeka", "Musa", "Zainab")
        for cell in cells(sheet, gmc["pupils"][pupil], CA1=13, CA2=14, Exam=40)
    ]
    assert send(tunde, "PUT", url, {"scores": every})[0] == 200  # complete, so it can be submitted
    use_context(db_session, school_id=gmc["school"], user_id=gmc["tunde"])
    db_session.execute(
        text("update result_sheets set status = 'submitted' where id = :id"), {"id": sheet["id"]}
    )
    use_context(db_session, school_id=gmc["school"], user_id=gmc["ngozi"])
    move_sheet(
        db_session, uuid.UUID(sheet["id"]), "returned_for_correction", comment="Check CA1 for Musa."
    )
    use_context(db_session)

    assert code_of(send(tunde, "PUT", url, {"scores": cells(sheet, musa, CA1=14)})) == (
        409,
        "scores_change_needs_reason",
    )
    status, saved = send(
        tunde,
        "PUT",
        url,
        {"scores": cells(sheet, musa, CA1=14), "reason": "Copied from the wrong column."},
    )
    assert status == 200, saved
    assert db_session.scalar(
        text("select string_agg(change_reason, '|') from scores where change_reason is not null")
    ) == ("Copied from the wrong column.")
    assert code_of(
        send(tunde, "PUT", url, {"scores": cells(sheet, musa, CA1=None), "reason": "Remove it."})
    ) == (409, "scores_removed_only_in_first_draft")


# --- CSV (F09 rule 5, AC09.2) -------------------------------------------------------------------


def upload(c: TestClient, url: str, content: str) -> Any:
    return c.post(
        f"/api/v1{url}",
        files={"file": ("maths.csv", content.encode(), "text/csv")},
        headers=csrf(c),
    )


def test_csv_template_import_errors_and_export(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    tunde = client(app, "tunde.adebayo")
    sheet = open_sheet(tunde, gmc["arm_a"], gmc["maths"])
    base = f"/api/v1/sheets/{sheet['id']}"
    template = tunde.get(f"{base}/template.csv")
    assert template.status_code == 200
    rows = list(csv.reader(io.StringIO(template.text)))
    assert rows[0] == ["admission_number", "surname", "first_name", "CA1", "CA2", "Exam"]
    assert [r[0] for r in rows[1:]] == ["GMC/2026/015", "GMC/2026/014", "GMC/2026/016"]

    good = (
        "admission_number,surname,first_name,CA1,CA2,Exam\n"
        "GMC/2026/015,Ibrahim,Musa,12,14,40\n"
        "GMC/2026/014,Obi,Chukwuemeka,16,15,47\n"
    )
    response = upload(tunde, f"/sheets/{sheet['id']}/import?commit=false", good)
    assert response.status_code == 200, response.text
    assert (response.json()["valid"], response.json()["invalid"]) == (2, 0)
    assert db_session.scalar(text("select count(*) from scores")) == 0
    response = upload(tunde, f"/sheets/{sheet['id']}/import?commit=true", good)
    assert (response.status_code, response.json()["counts"]["complete"]) == (200, 2)

    bad = good + (
        "GMC/2026/016,Yusuf,Zainab,10,10,72\n"  # over the maximum
        "GMC/2026/017,Eze,Kosi,10,10,10\n"  # not on this sheet
        "GMC/2026/014,Obi,Chukwuemeka,1,1,1\n"  # twice in the file
        "GMC/2026/015,Ibrahim,Musa,ten,,\n"
    )  # not a whole number
    response = upload(tunde, f"/sheets/{sheet['id']}/import?commit=true", bad)
    assert (response.status_code, response.json()["code"]) == (422, "import_has_errors")
    assert db_session.scalar(text("select sum(value) from scores")) == 12 + 14 + 40 + 16 + 15 + 47
    errors = upload(tunde, f"/sheets/{sheet['id']}/import/errors.csv", bad)
    assert errors.status_code == 200
    error_rows = list(csv.DictReader(io.StringIO(errors.text)))
    assert [r["admission_number"] for r in error_rows] == [
        "GMC/2026/015",
        "GMC/2026/014",
        "GMC/2026/016",
        "GMC/2026/017",
        "GMC/2026/014",
        "GMC/2026/015",
    ]
    assert all(r["errors"] for r in error_rows)

    export = tunde.get(f"{base}/export.csv")
    exported = {r["admission_number"]: r for r in csv.DictReader(io.StringIO(export.text))}
    assert (exported["GMC/2026/014"]["total"], exported["GMC/2026/014"]["grade"]) == ("78", "A1")
    assert exported["GMC/2026/016"]["total"] == ""
    assert send(client(app, "grace.etim"), "GET", f"/sheets/{sheet['id']}/export.csv")[0] == 404


def test_a_blank_csv_cell_leaves_the_score_and_the_last_value_wins(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    tunde = client(app, "tunde.adebayo")
    sheet = open_sheet(tunde, gmc["arm_a"], gmc["maths"])
    musa = gmc["pupils"]["Musa"]
    first, second = cells(sheet, musa, CA1=11), cells(sheet, musa, CA1=12)
    status, saved = send(tunde, "PUT", f"/sheets/{sheet['id']}/scores", {"scores": first + second})
    assert status == 200
    assert row_of(saved, musa)["scores"] == {columns(sheet)["CA1"]: 12}
    blanks = "admission_number,surname,first_name,CA1,CA2,Exam\nGMC/2026/015,Ibrahim,Musa,,14,41\n"
    response = upload(tunde, f"/sheets/{sheet['id']}/import?commit=true", blanks)
    assert response.status_code == 200, response.text
    assert row_of(response.json(), musa)["total"] == 12 + 14 + 41


def test_rating_levels_moved_pupils_and_levels_switched_off(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    tunde = client(app, "tunde.adebayo")
    sheet = open_sheet(tunde, gmc["arm_a"], gmc["maths"])
    # A pupil who moved to another arm leaves this sheet (their history stays).
    db_session.execute(
        text("update enrolments set left_on = current_date where id = :e"),
        {"e": gmc["pupils"]["Musa"]},
    )
    names = [r["first_name"] for r in send(tunde, "GET", f"/sheets/{sheet['id']}")[1]["rows"]]
    assert names == ["Chukwuemeka", "Zainab"]
    # A level that is off: its sheets are refused.
    db_session.execute(text("update school_levels set enabled = (level = 'primary')"))
    assert code_of(send(tunde, "GET", f"/sheets/{sheet['id']}")) == (404, "level_disabled")
    # A level on Skill ratings uses rating sheets, not score sheets.
    db_session.execute(
        text(
            "update school_levels set enabled = true,"
            " assessment_mode = 'skill_ratings' where level = 'junior_secondary'"
        )
    )
    assert send(tunde, "GET", "/sheets")[1] == []
    assert code_of(
        send(
            tunde, "POST", "/sheets", {"arm_id": str(gmc["arm_b"]), "subject_id": str(gmc["maths"])}
        )
    ) == (409, "use_rating_sheet")
