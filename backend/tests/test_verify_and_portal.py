"""Public verification and the parent and student portal (BUILD_PROMPT 9.2l, 9.2m; D-171, D-172).

SPEC F13 and F14; AC13.1, AC14.1, AC14.2, AC25.4; D-072 to D-077.

Behaviour: anyone can check a report's verification code without logging in
and sees only the school, the masked name, session, term, status, revision,
report ID and date (never scores or the full name); input is forgiving; a
corrected report's old code shows SUPERSEDED and a revoked one REVOKED (never
the reason); unknown codes are refused and rate limited; reports verify even
when their level is off or the school is suspended; answers are never cached
or indexed. Parents see their linked children in every school where their
link is active and the portal is on, grouped by school; students see only
themselves; only published reports appear; nobody opens a report that is not
theirs; staff use the school's own pages. All data is fictional.
"""

import re
from collections.abc import Iterator
from typing import Any, cast

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.reports.verify import get_verifier_db
from tests.auth_support import client_for, logged_in
from tests.factories import (
    create_arm,
    create_class,
    create_guardian,
    create_school,
    create_session,
    create_student,
    create_term,
    enrol,
    link_ward,
    parent_accepts_link,
)
from tests.test_publication import (
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
from tests.test_republishing import edit_musa_maths, publish_a, sheet_of

__all__ = ["app", "fast_hashing", "gmc"]


class VerifierAsRole:
    """The verifier's session in tests: each statement runs as app_verifier.

    In production it is its own login (DATABASE_URL_VERIFIER); here the role
    is switched around each statement on the rolled-back test transaction.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(self, statement: Any, params: Any = None) -> Rows:
        before = self._session.scalar(text("select current_user"))
        self._session.execute(text("set local role app_verifier"))
        rows: list[Any] = list(cast(Any, self._session.execute(statement, params)))
        self._session.execute(text(f'set local role "{before}"'))
        return Rows(rows)


class Rows:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def first(self) -> Any:
        return self._rows[0] if self._rows else None


@pytest.fixture
def verifying(app: FastAPI, db_session: Session) -> Iterator[None]:
    def verifier() -> Iterator[VerifierAsRole]:
        yield VerifierAsRole(db_session)

    app.dependency_overrides[get_verifier_db] = verifier
    yield
    app.dependency_overrides.pop(get_verifier_db, None)


def check(app: FastAPI, code: str) -> tuple[int, Any, Any]:
    response = client_for(app).get(f"/api/v1/verify/{code}")
    return response.status_code, response.json(), response.headers


# --- public verification (F13) ----------------------------------------------------------------


def test_anyone_can_verify_a_published_report(
    app: FastAPI, verifying: None, db_session: Session, gmc: dict[str, Any]
) -> None:
    codes = publish_a(app, gmc)
    report = codes["GMC/2026/014"]
    status, body, headers = check(app, report["verification_code"])
    assert status == 200
    assert {k: v for k, v in body.items() if k != "published_at"} == {
        "status": "valid",
        "school": "Greenfield Model College",
        "student": "Chuk*** O.",
        "session": "2026/2027",
        "term": "First Term",
        "report_id": "GMC-2627-T1-JSS1A-014",
        "revision": 1,
        "has_newer_revision": False,
        "newer_revision": None,
        "newer_published_at": None,
    }
    assert body["published_at"]
    assert (headers["cache-control"], headers["referrer-policy"]) == ("no-store", "no-referrer")
    assert "noindex" in headers["x-robots-tag"]
    assert "Chukwuemeka" not in str(body) and "78" not in str(body)

    # Forgiving input (D-072): small letters, no dashes, spaces.
    sloppy = report["verification_code"].lower().replace("-", " ")
    assert check(app, sloppy)[1]["report_id"] == "GMC-2627-T1-JSS1A-014"

    # AC25.4 and D-075: still verifies with the level off and the school suspended.
    db_session.execute(
        text(
            "update school_levels set enabled = false"
            " where school_id = :s and level like '%secondary'"
        ),
        {"s": gmc["school"]},
    )
    db_session.execute(
        text("update schools set status = 'suspended' where id = :s"), {"s": gmc["school"]}
    )
    assert check(app, report["verification_code"])[1]["status"] == "valid"


def test_superseded_and_revoked_reports(
    app: FastAPI, verifying: None, db_session: Session, gmc: dict[str, Any]
) -> None:
    first = publish_a(app, gmc)
    ngozi = as_(app, "ngozi.okeke")
    maths = str(sheet_of(db_session, gmc, "maths"))
    reopen = {"reason": "Musa's exam script shows 22, not 18.", "sheet_ids": [maths]}
    send(ngozi, "POST", f"/school/publications/{gmc['arm_a']}/reopen", reopen)
    edit_musa_maths(app, db_session, gmc, 22)
    _, second = send(ngozi, "POST", f"/school/publications/{gmc['arm_a']}/publish")
    old = check(app, first["GMC/2026/015"]["verification_code"])[1]
    new_code = next(r for r in second["reports"] if r["admission_number"] == "GMC/2026/015")
    new = check(app, new_code["verification_code"])[1]
    assert (old["status"], old["revision"], old["has_newer_revision"]) == ("superseded", 1, True)
    assert (new["status"], new["revision"], new["has_newer_revision"]) == ("valid", 2, False)
    # VerifyAfter: "A newer version exists (revision 2, <date>)", never its code.
    assert (old["newer_revision"], old["newer_published_at"]) == (2, new["published_at"])
    assert (new["newer_revision"], new["newer_published_at"]) == (None, None)
    assert new_code["verification_code"] not in str(old)

    report_id = db_session.scalar(
        text("select id from report_documents where verification_code = :c"),
        {"c": new_code["verification_code"]},
    )
    why = {"reason": "Issued to the wrong pupil by mistake."}
    assert send(ngozi, "POST", f"/school/reports/{report_id}/revoke", why)[0] == 200
    revoked = check(app, new_code["verification_code"])[1]
    assert revoked["status"] == "revoked"
    assert "wrong pupil" not in str(revoked)


def test_unknown_codes_are_refused_and_limited(
    app: FastAPI, verifying: None, gmc: dict[str, Any]
) -> None:
    status, body, headers = check(app, "ZZZZ-ZZZZ-ZZZZ")
    assert (status, body["code"]) == (404, "not_found")
    assert headers["cache-control"] == "no-store" and "noindex" in headers["x-robots-tag"]
    assert check(app, "SHORT")[0] == 404
    for _ in range(8):
        assert check(app, "ZZZZ-ZZZZ-ZZZY")[0] == 404
    status, _, headers = check(app, "ZZZZ-ZZZZ-ZZZX")
    assert status == 429 and int(headers["retry-after"]) > 0


def test_lookups_are_limited_per_ip(app: FastAPI, verifying: None, gmc: dict[str, Any]) -> None:
    codes = publish_a(app, gmc)
    code = codes["GMC/2026/014"]["verification_code"]
    for _ in range(30):
        assert check(app, code)[0] == 200
    assert check(app, code)[0] == 429


# --- the portal (F14) -------------------------------------------------------------------------


def group_names(body: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    return [(g["school_code"], [c["name"] for c in g["children"]]) for g in body]


def test_parents_see_only_published_reports(app: FastAPI, gmc: dict[str, Any]) -> None:
    approve_all(app, gmc)
    complete_my_class(app, gmc)
    principal_comments(app, gmc)
    ikenna = as_(app, "ikenna.obi")
    status, body = send(ikenna, "GET", "/me/children")
    assert (status, group_names(body)) == (200, [("GMC", ["Chukwuemeka Obi"])])
    child = body[0]["children"][0]
    assert (child["class_name"], child["latest"]) == ("JSS 1A", None)  # AC14.1: approved only
    reports_url = f"/me/students/{child['student_id']}/reports"
    assert send(ikenna, "GET", reports_url) == (200, [])

    send(as_(app, "ngozi.okeke"), "POST", f"/school/publications/{gmc['arm_a']}/publish")
    latest = send(ikenna, "GET", "/me/children")[1][0]["children"][0]["latest"]
    assert (latest["status"], latest["revision"], latest["term"], latest["card"]) == (
        "valid",
        1,
        "First Term",
        "scores",
    )
    assert (latest["average"], latest["position"], latest["number_in_class"]) == ("74.00", 1, 3)
    rows = send(ikenna, "GET", reports_url)[1]
    assert [(r["report_code"], r["status"]) for r in rows] == [("GMC-2627-T1-JSS1A-014", "valid")]

    status, view = send(ikenna, "GET", f"/me/reports/{rows[0]['report_id']}")
    assert status == 200
    assert (view["pupil"]["first_name"], view["class_info"]["name"], view["status"]) == (
        "Chukwuemeka",
        "JSS 1A",
        "valid",
    )
    assert {s["name"]: s["total"] for s in view["subjects"]} == {
        "English Language": 70,
        "Mathematics": 78,
    }
    assert "logo_file_id" not in view["school"]
    assert re.fullmatch(
        r"[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}",
        view["verification_code"],
    )

    card = ikenna.get(f"/api/v1/me/reports/{rows[0]['report_id']}/card.html")
    assert card.status_code == 200 and card.headers["content-type"].startswith("text/html")
    assert "GMC-2627-T1-JSS1A-014" in card.text and "<svg" in card.text
    assert card.headers["cache-control"] == "private, no-store"


def test_nobody_opens_a_report_that_is_not_theirs(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    publish_a(app, gmc)

    def report(admission: str) -> Any:
        return db_session.scalar(
            text(
                "select d.id from report_documents d join enrolments e on e.id = d.enrolment_id"
                " join students st on st.id = e.student_id where st.admission_number = :a"
            ),
            {"a": admission},
        )

    mine, musas = report("GMC/2026/014"), report("GMC/2026/015")
    pupil = logged_in(app, "chukwuemeka.obi", school_code="GMC")
    assert send(pupil, "GET", f"/me/reports/{mine}")[0] == 200  # a student sees themselves
    assert send(pupil, "GET", f"/me/reports/{musas}")[0] == 404
    assert send(pupil, "GET", f"/me/students/{gmc['students']['Musa']}/reports")[0] == 404
    assert group_names(send(pupil, "GET", "/me/children")[1]) == [("GMC", ["Chukwuemeka Obi"])]
    ada = as_(app, "ada.eze")  # Kosi's parent
    assert send(ada, "GET", f"/me/reports/{mine}")[0] == 404
    assert pupil.get(f"/api/v1/me/reports/{musas}/card.html").status_code == 404
    for staff in ("tunde.adebayo", "ngozi.okeke"):
        assert code_of(send(as_(app, staff), "GET", "/me/children")) == (403, "permission_denied")

    # A revoked report is withdrawn from the portal.
    why = {"reason": "Issued in error."}
    assert send(as_(app, "ngozi.okeke"), "POST", f"/school/reports/{mine}/revoke", why)[0] == 200
    assert send(pupil, "GET", f"/me/reports/{mine}")[0] == 404
    assert send(pupil, "GET", "/me/children")[1][0]["children"][0]["latest"] is None
    own_reports = f"/me/students/{gmc['students']['Chukwuemeka']}/reports"
    assert send(pupil, "GET", own_reports) == (200, [])

    # The Parent portal switch off: its pages answer 404.
    db_session.execute(
        text(
            "update school_features set enabled = false"
            " where school_id = :s and feature = 'parent_portal'"
        ),
        {"s": gmc["school"]},
    )
    assert code_of(
        send(pupil, "GET", f"/me/students/{gmc['students']['Chukwuemeka']}/reports")
    ) == (
        404,
        "feature_disabled",
    )
    assert send(pupil, "GET", "/me/children")[1] == []


def test_a_parent_sees_children_in_every_linked_school(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    s = db_session
    bsa = create_school(s, code="BSA", name="Bright Star Academy")
    year = create_session(s, bsa)
    create_term(s, bsa, year, 1, is_active=True)
    arm = create_arm(s, bsa, create_class(s, bsa, "junior_secondary", "JSS 2"), "B")
    tobi = create_student(s, bsa, "BSA/2025/031", "Obi", "Tobenna")
    enrol(s, bsa, tobi, year, arm)
    parent_accepts_link(s, gmc["ikenna"], bsa)
    link_ward(s, bsa, create_guardian(s, bsa, "Ikenna Obi", user_id=gmc["ikenna"]), tobi)

    ikenna = as_(app, "ikenna.obi")
    status, body = send(ikenna, "GET", "/me/children")
    assert (status, group_names(body)) == (
        200,
        [("BSA", ["Tobenna Obi"]), ("GMC", ["Chukwuemeka Obi"])],
    )  # AC14.2, schools by name
    assert body[0]["children"][0]["class_name"] == "JSS 2B"
    # Each child's reports come from that child's school only.
    url = f"/me/students/{tobi}/reports"
    in_gmc = ikenna.get(f"/api/v1{url}", headers={"X-School-Id": str(gmc["school"])})
    assert in_gmc.status_code == 404
    in_bsa = ikenna.get(f"/api/v1{url}", headers={"X-School-Id": str(bsa)})
    assert (in_bsa.status_code, in_bsa.json()) == (200, [])

    # A school with the portal off is left out.
    s.execute(
        text(
            "update school_features set enabled = false"
            " where school_id = :s and feature = 'parent_portal'"
        ),
        {"s": bsa},
    )
    assert group_names(send(ikenna, "GET", "/me/children")[1]) == [("GMC", ["Chukwuemeka Obi"])]

    # A paused link is left out too, even with the portal back on.
    s.execute(
        text(
            "update school_features set enabled = true"
            " where school_id = :s and feature = 'parent_portal'"
        ),
        {"s": bsa},
    )
    s.execute(
        text(
            "update school_memberships set status = 'paused' where user_id = :u and school_id = :s"
        ),
        {"u": gmc["ikenna"], "s": bsa},
    )
    assert group_names(send(ikenna, "GET", "/me/children")[1]) == [("GMC", ["Chukwuemeka Obi"])]
