"""The school's grading set-up (BUILD_PROMPT 9.2f; SPEC F08, F26 rules 1 and 2; D-141, D-145).

Behaviour: a school starts from the platform defaults (A1 to F9 for
Secondary, A to F for Nursery and Primary, pass mark 40, the default traits
and 1 to 5 key, the five-point rating scale and the default learning areas),
copied once; school admins replace a level's grading bands and remark bands
(covering 0 to 100 with no gaps or overlaps), set the pass mark (a whole
number from 1 to 99), edit traits and the key, set each term's assessment
structure (1 to 8 components adding up to 100; none for Skill ratings; saved
for next term once the term is locked), and manage learning areas, their
skills, which classes take them and the rating scale (exactly one attention
point). Levels that are off, teachers and other schools' ids are refused.
All data is fictional.
"""

import uuid
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.tests.auth_support import build_auth_app, csrf, logged_in, make_login, use_fast_hashing
from app.tests.factories import create_class, create_school, create_session, create_term


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    return build_auth_app(db_session)


@pytest.fixture
def rcs(db_session: Session) -> dict[str, uuid.UUID]:
    """Royal Crest Schools: all levels on (Nursery on Skill ratings)."""
    school = create_school(
        db_session, code="RCS", name="Royal Crest Schools", school_type="all_levels"
    )
    year = create_session(db_session, school)
    return {
        "school": school,
        "first": create_term(db_session, school, year, 1, is_active=True),
        "second": create_term(db_session, school, year, 2),
        "admin": make_login(
            db_session, username="femi.ade", school_id=school, role="school_admin", is_primary=True
        ),
        "teacher": make_login(db_session, username="grace.etim", school_id=school),
        "nursery2": create_class(db_session, school, "nursery", "Nursery 2"),
        "pry4": create_class(db_session, school, "primary", "Primary 4"),
    }


@pytest.fixture
def admin(app: FastAPI, rcs: dict[str, uuid.UUID]) -> TestClient:
    return logged_in(app, "femi.ade")


@pytest.fixture
def teacher(app: FastAPI, rcs: dict[str, uuid.UUID]) -> TestClient:
    return logged_in(app, "grace.etim")


def send(client: TestClient, method: str, url: str, body: Any = None) -> tuple[int, Any]:
    response = client.request(method, f"/api/v1{url}", json=body, headers=csrf(client))
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def code_of(result: tuple[int, Any]) -> tuple[int, str | None]:
    status, body = result
    return status, cast(dict[str, Any], body or {}).get("code")


# --- defaults, bands and pass mark ----------------------------------------------------------


def test_a_school_starts_from_the_defaults_copied_once(
    admin: TestClient, teacher: TestClient, db_session: Session
) -> None:
    """F08 rules 4 to 6, AT-07.6, D-141."""
    status, grading = send(teacher, "GET", "/school/grading")
    assert status == 200
    assert grading["pass_mark"] == 40
    secondary = grading["levels"]["senior_secondary"]["grade_bands"]
    assert (secondary[0], secondary[-1]) == (
        {"grade": "A1", "min_score": 75, "max_score": 100, "remark": "Excellent"},
        {"grade": "F9", "min_score": 0, "max_score": 39, "remark": "Fail"},
    )
    primary = {
        b["grade"]: (b["min_score"], b["max_score"], b["remark"])
        for b in grading["levels"]["primary"]["grade_bands"]
    }
    assert primary["B"] == (60, 69, "Very good")  # a total of 65 is a B
    assert grading["levels"]["primary"]["remark_bands"] == []  # no default wording yet
    counts = [
        db_session.scalar(text(f"select count(*) from {table}"))  # noqa: S608
        for table in ("grade_bands", "rating_traits", "rating_scale_points", "learning_areas")
    ]
    assert send(admin, "GET", "/school/grading")[0] == 200  # opened again: nothing copied
    assert [
        db_session.scalar(text(f"select count(*) from {table}"))  # noqa: S608
        for table in ("grade_bands", "rating_traits", "rating_scale_points", "learning_areas")
    ] == counts
    assert counts == [30, 13, 5, 10]


def test_replacing_a_levels_grading_bands(
    admin: TestClient, teacher: TestClient, db_session: Session
) -> None:
    url = "/school/grading/primary/bands"
    bands = [
        {"grade": "A", "min_score": 75, "max_score": 100, "remark": "Distinction"},
        {"grade": "B", "min_score": 50, "max_score": 74, "remark": "Merit"},
        {"grade": "F", "min_score": 0, "max_score": 49, "remark": "Fail"},
    ]
    status, body = send(admin, "PUT", url, {"bands": bands})
    assert status == 200, body
    assert [b["grade"] for b in body["grade_bands"]] == ["A", "B", "F"]
    gap = [{**bands[0]}, {**bands[1], "min_score": 51}, bands[2]]
    overlap = [{**bands[0]}, {**bands[1], "max_score": 80}, bands[2]]
    short = bands[:2]
    for bad in (gap, overlap, short):
        assert code_of(send(admin, "PUT", url, {"bands": bad})) == (422, "bands_must_cover")
    assert send(admin, "PUT", url, {"bands": [{**bands[0], "grade": "a+"}, *bands[1:]]})[0] == 422
    assert code_of(send(teacher, "PUT", url, {"bands": bands})) == (403, "permission_denied")
    assert "grade_bands.update" in set(db_session.scalars(text("select action from audit_events")))


def test_remark_bands_and_the_pass_mark(admin: TestClient) -> None:
    """D-141, AT-07.5."""
    url = "/school/grading/primary/remark-bands"
    bands = [
        {"min_score": 70, "max_score": 100, "comments": ["An excellent term.", "Keep it up."]},
        {"min_score": 0, "max_score": 69, "comments": ["Work harder next term."]},
    ]
    status, body = send(admin, "PUT", url, {"bands": bands})
    assert (status, len(body["remark_bands"])) == (200, 2)
    four = [{**bands[0], "comments": ["a", "b", "c", "d"]}, bands[1]]
    assert send(admin, "PUT", url, {"bands": four})[0] == 422
    assert code_of(send(admin, "PUT", url, {"bands": bands[:1]})) == (422, "bands_must_cover")
    assert send(admin, "PUT", url, {"bands": []})[0] == 200  # no suggestions at all is fine

    assert send(admin, "PUT", "/school/grading/pass-mark", {"pass_mark": 45}) == (
        200,
        {"pass_mark": 45},
    )
    for bad in (0, 100, 40.5, "forty"):
        status, body = send(admin, "PUT", "/school/grading/pass-mark", {"pass_mark": bad})
        assert status == 422, bad


def test_levels_that_are_off_are_refused(
    admin: TestClient, db_session: Session, rcs: dict[str, uuid.UUID]
) -> None:
    db_session.execute(
        text("update school_levels set enabled = false where school_id = :s and level = 'primary'"),
        {"s": rcs["school"]},
    )
    assert code_of(
        send(
            admin,
            "PUT",
            "/school/grading/primary/bands",
            {"bands": [{"grade": "A", "min_score": 0, "max_score": 100, "remark": "All"}]},
        )
    ) == (
        404,
        "level_disabled",
    )
    assert code_of(send(admin, "GET", "/school/assessment-structures/primary")) == (
        404,
        "level_disabled",
    )
    _status, grading = send(admin, "GET", "/school/grading")
    assert "primary" not in grading["levels"]


# --- traits and their key (F08 rule 6) ---------------------------------------------------


def test_traits_and_the_rating_key(admin: TestClient, teacher: TestClient) -> None:
    status, traits = send(teacher, "GET", "/school/traits")
    assert status == 200
    assert [t["name"] for t in traits["affective"]][:2] == ["Punctuality", "Neatness"]
    assert len(traits["psychomotor"]) == 6
    assert traits["key"] == {
        "5": "Excellent",
        "4": "Good",
        "3": "Average",
        "2": "Below average",
        "1": "Unsatisfactory",
    }
    status, added = send(
        admin, "POST", "/school/traits", {"domain": "affective", "name": "Teamwork"}
    )
    assert (status, added["position"]) == (201, 8)
    assert (
        send(admin, "POST", "/school/traits", {"domain": "affective", "name": "teamwork"})[0] == 409
    )
    status, edited = send(
        admin, "PATCH", f"/school/traits/{added['id']}", {"name": "Team work", "is_active": False}
    )
    assert (status, edited["is_active"]) == (200, False)
    key = {"5": "Outstanding", "4": "Good", "3": "Fair", "2": "Weak", "1": "Poor"}
    assert send(admin, "PUT", "/school/traits/key", {"key": key}) == (200, {"key": key})
    assert send(admin, "PUT", "/school/traits/key", {"key": {"5": "Only one"}})[0] == 422
    assert code_of(
        send(teacher, "POST", "/school/traits", {"domain": "affective", "name": "X"})
    ) == (403, "permission_denied")


# --- assessment structures (F08 rules 1 to 3; AT-07.1 to AT-07.4) ----------------------------


SSS = [
    {"name": "First test", "label": "CA1", "max_score": 10},
    {"name": "Second test", "label": "CA2", "max_score": 10},
    {"name": "Third test", "label": "CA3", "max_score": 10},
    {"name": "Project", "label": "Project", "max_score": 10},
    {"name": "Examination", "label": "Exam", "max_score": 60},
]


def test_structures_start_from_the_default_and_must_add_up(
    admin: TestClient, teacher: TestClient, rcs: dict[str, uuid.UUID]
) -> None:
    status, structure = send(teacher, "GET", "/school/assessment-structures/junior_secondary")
    assert status == 200
    assert (structure["term_id"], structure["saved"], structure["locked"]) == (
        str(rcs["first"]),
        False,
        False,
    )
    assert [(c["label"], c["max_score"]) for c in structure["components"]] == [
        ("CA1", 20),
        ("CA2", 20),
        ("Exam", 60),
    ]

    url = "/school/assessment-structures/senior_secondary"
    status, saved = send(admin, "PUT", url, {"components": SSS})
    assert status == 200, saved
    assert ([c["label"] for c in saved["components"]], saved["saved"]) == (
        ["CA1", "CA2", "CA3", "Project", "Exam"],
        True,
    )
    assert send(teacher, "GET", url)[1]["components"] == saved["components"]

    status, body = send(admin, "PUT", url, {"components": [*SSS[:4], {**SSS[4], "max_score": 55}]})
    assert (status, body["code"]) == (422, "structure_total")
    assert body["detail"] == "The maximums add up to 95. They must add up to 100 (5 more)."
    nine = [{"name": f"Test {n}", "label": f"T{n}", "max_score": 10} for n in range(9)]
    assert send(admin, "PUT", url, {"components": nine})[0] == 422
    assert send(admin, "PUT", url, {"components": []})[0] == 422
    twice = [SSS[0], {**SSS[1], "label": "ca1"}, *SSS[2:]]
    assert code_of(send(admin, "PUT", url, {"components": twice})) == (422, "labels_repeat")
    assert code_of(send(teacher, "PUT", url, {"components": SSS})) == (403, "permission_denied")


def test_a_locked_structure_is_changed_for_next_term(
    admin: TestClient, db_session: Session, rcs: dict[str, uuid.UUID]
) -> None:
    """AC08.3, AT-07.4."""
    url = "/school/assessment-structures/junior_secondary"
    send(admin, "PUT", url, {"components": SSS})
    db_session.execute(
        text(
            "update assessment_structures set locked_at = now()"
            " where term_id = :t and level = 'junior_secondary'"
        ),
        {"t": rcs["first"]},
    )
    status, body = send(
        admin,
        "PUT",
        url,
        {"components": [*SSS[:2], {"name": "Examination", "label": "Exam", "max_score": 80}]},
    )
    assert status == 200, body
    assert (body["term_id"], body["saved"]) == (str(rcs["second"]), True)
    first = send(admin, "GET", f"{url}?term_id={rcs['first']}")[1]
    assert (len(first["components"]), first["locked"]) == (5, True)
    assert len(send(admin, "GET", f"{url}?term_id={rcs['second']}")[1]["components"]) == 3

    db_session.execute(text("update assessment_structures set locked_at = now()"))
    assert code_of(send(admin, "PUT", f"{url}?term_id={rcs['second']}", {"components": SSS})) == (
        409,
        "no_next_term",
    )


def test_a_skill_ratings_structure_has_no_components(admin: TestClient) -> None:
    url = "/school/assessment-structures/nursery"
    status, body = send(admin, "GET", url)
    assert (status, body["assessment_mode"], body["components"]) == (200, "skill_ratings", [])
    assert code_of(send(admin, "PUT", url, {"components": SSS})) == (422, "ratings_have_no_columns")


# --- learning areas, skills and the rating scale (F26 rules 1 and 2) ---------------------------


def test_learning_areas_skills_and_classes(
    admin: TestClient, teacher: TestClient, db_session: Session, rcs: dict[str, uuid.UUID]
) -> None:
    status, areas = send(teacher, "GET", "/school/learning-areas?level=nursery")
    assert status == 200
    assert [a["name"] for a in areas][:3] == ["Number work", "Letter work", "Phonics"]
    number_work = areas[0]
    assert [s["name"] for s in number_work["skills"]] == ["Counts 1 to 20", "Recognises shapes"]

    status, area = send(
        admin, "POST", "/school/learning-areas", {"level": "nursery", "name": "French"}
    )
    assert (status, area["position"]) == (201, 11)
    assert (
        send(admin, "POST", "/school/learning-areas", {"level": "nursery", "name": "french"})[0]
        == 409
    )
    status, skill = send(
        admin,
        "POST",
        f"/school/learning-areas/{area['id']}/skills",
        {"name": "Says bonjour", "description": "Greets in French"},
    )
    assert status == 201, skill
    status, skill = send(admin, "PATCH", f"/school/skills/{skill['id']}", {"is_active": False})
    assert (status, skill["is_active"]) == (200, False)
    assert send(admin, "DELETE", f"/school/skills/{skill['id']}")[0] == 204

    url = f"/school/classes/{rcs['nursery2']}/learning-areas"
    status, taken = send(admin, "PUT", url, {"learning_area_ids": [number_work["id"], area["id"]]})
    assert (status, sorted(a["name"] for a in taken)) == (200, ["French", "Number work"])
    assert code_of(
        send(
            admin,
            "PUT",
            f"/school/classes/{rcs['pry4']}/learning-areas",
            {"learning_area_ids": [number_work["id"]]},
        )
    ) == (409, "class_learning_areas_same_level")
    assert code_of(
        send(teacher, "POST", "/school/learning-areas", {"level": "nursery", "name": "Y"})
    ) == (403, "permission_denied")
    other = create_school(
        db_session, code="BSA", name="Bright Stars", school_type="nursery_primary"
    )
    theirs = create_class(db_session, other, "nursery", "Nursery 1")
    assert (
        send(admin, "PUT", f"/school/classes/{theirs}/learning-areas", {"learning_area_ids": []})[0]
        == 404
    )


def test_the_rating_scale_has_one_attention_point(
    admin: TestClient, teacher: TestClient, db_session: Session
) -> None:
    status, scale = send(teacher, "GET", "/school/rating-scale")
    assert status == 200
    assert [(p["code"], p["is_attention"]) for p in scale["points"]] == [
        ("E", False),
        ("VG", False),
        ("G", False),
        ("F", False),
        ("NI", True),
    ]
    points = [
        {"name": "Secure", "code": "S", "description": "Does it alone", "is_attention": False},
        {"name": "Developing", "code": "D", "is_attention": False},
        {"name": "Beginning", "code": "B", "is_attention": True},
    ]
    ids_before = list(
        db_session.scalars(text("select id from rating_scale_points order by position"))
    )
    status, scale = send(admin, "PUT", "/school/rating-scale", {"points": points})
    ids_after = list(
        db_session.scalars(text("select id from rating_scale_points order by position"))
    )
    assert ids_after == ids_before[:3]  # kept, so ratings already given still point at them
    assert status == 200, scale
    assert [p["code"] for p in scale["points"]] == ["S", "D", "B"]
    none_flagged = [{**p, "is_attention": False} for p in points]
    two_flagged = [{**p, "is_attention": True} for p in points]
    for bad in (none_flagged, two_flagged):
        assert code_of(send(admin, "PUT", "/school/rating-scale", {"points": bad})) == (
            422,
            "one_attention_point",
        )
    assert (
        send(
            admin,
            "PUT",
            "/school/rating-scale",
            {"points": [points[0], {**points[1], "code": "S"}, points[2]]},
        )[0]
        == 422
    )
    assert code_of(send(teacher, "PUT", "/school/rating-scale", {"points": points})) == (
        403,
        "permission_denied",
    )


def test_next_term_starts_from_this_terms_structure(
    admin: TestClient, rcs: dict[str, uuid.UUID]
) -> None:
    """F08 rule 3: a term without its own structure is offered the latest earlier one."""
    url = "/school/assessment-structures/senior_secondary"
    send(admin, "PUT", url, {"components": SSS})
    status, suggested = send(admin, "GET", f"{url}?term_id={rcs['second']}")
    assert status == 200
    assert (suggested["saved"], [c["label"] for c in suggested["components"]]) == (
        False,
        ["CA1", "CA2", "CA3", "Project", "Exam"],
    )


def test_a_school_without_nursery_gets_no_learning_areas(app: FastAPI, db_session: Session) -> None:
    gmc = create_school(db_session, code="GMC", name="Greenfield Model College")
    make_login(
        db_session, username="ngozi.okeke", school_id=gmc, role="school_admin", is_primary=True
    )
    client = logged_in(app, "ngozi.okeke")
    status, grading = send(client, "GET", "/school/grading")
    assert (status, sorted(grading["levels"])) == (200, ["junior_secondary", "senior_secondary"])
    assert send(client, "GET", "/school/learning-areas")[1] == []
