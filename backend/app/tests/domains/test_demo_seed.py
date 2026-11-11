"""The demo seed (BUILD_PROMPT 9.2v; ACCEPTANCE_TESTS fixtures; D-180).

Behaviour, round 1: the seed signs in as the super admin and, through the
app's own routes, saves the default price list as version 1 and creates GMC
(Secondary only, every feature on, billing on), BSA (Nursery and Primary,
Correction queue off, free pilot) and RCS (all levels), each with a principal
who signs in once with a temporary password and then uses the demo password.
It refuses to run twice.

Round 2: each school gets session 2026/2027 with three terms (the first
active), its departments, subjects, classes and arms, the subjects each arm
takes, and assessment structures (SS: CA1, CA2, CA3, Project, Exam). Staff
in every role are made by the school's own admin with a temporary password
and then use the demo password: a vice principal, a reviewer over Sciences,
subject and form teachers so every demo class can be published, BSA's
Primary 4A class teacher who teaches all subjects with an assistant, and
Nursery teachers over the class's learning areas. No staff email is sent.
All data is fictional.
"""

from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.cli.demo.browser import Demo, SeedError
from app.cli.demo.platform import SUPER_ADMIN, seed_platform
from app.cli.demo.schools import seed_schools
from app.tests.auth_support import (
    ORIGIN,
    PASSWORD,
    build_platform_app,
    client_for,
    log_in,
    make_login,
    use_fast_hashing,
)

DEMO_PASSWORD = "harmattan-kettle-blue-river"  # noqa: S105 (fictional; 27 characters)


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    return build_platform_app(db_session)


@pytest.fixture
def demo(app: FastAPI, db_session: Session) -> Demo:
    make_login(db_session, username=SUPER_ADMIN, full_name="Platform Admin", is_super_admin=True)
    made = Demo(app, password=DEMO_PASSWORD, origin=ORIGIN)
    made.people[SUPER_ADMIN] = made.log_in(SUPER_ADMIN, PASSWORD)
    return made


def schools(db: Session) -> dict[str, Any]:
    rows = db.execute(
        text(
            "select s.code, s.name, sub.billing_enabled,"
            " (select array_agg(f.feature order by f.feature) from school_features f"
            "   where f.school_id = s.id and f.enabled) as features,"
            " (select array_agg(l.level order by l.level) from school_levels l"
            "   where l.school_id = s.id and l.enabled) as levels"
            " from schools s left join school_subscriptions sub on sub.school_id = s.id"
        )
    )
    return {r.code: r for r in rows}


def test_the_three_schools_are_made_as_the_fixtures_say(demo: Demo, db_session: Session) -> None:
    seed_platform(demo)
    made = schools(db_session)
    assert set(made) == {"GMC", "BSA", "RCS"}
    assert made["GMC"].name == "Greenfield Model College"
    assert made["GMC"].billing_enabled is True
    assert len(made["GMC"].features) == 6
    assert made["GMC"].levels == ["junior_secondary", "senior_secondary"]
    assert made["BSA"].billing_enabled is False  # free pilot
    assert "correction_queue" not in made["BSA"].features
    assert made["BSA"].levels == ["nursery", "primary"]
    assert len(made["RCS"].levels) == 4


def test_the_default_prices_become_version_1(demo: Demo, db_session: Session) -> None:
    seed_platform(demo)
    assert db_session.scalar(text("select count(*) from pricing_versions")) == 1
    assert db_session.scalar(text("select max(version) from pricing_versions")) == 1


def test_each_principal_uses_the_demo_password(app: FastAPI, demo: Demo) -> None:
    seed_platform(demo)
    for username in ("ngozi.okeke", "chiamaka.nwafor", "femi.adeyemi"):
        assert log_in(client_for(app), username, DEMO_PASSWORD) == 200, username
        me = demo.as_(username).get("/auth/me")
        assert me["must_change_password"] is False


def test_the_principals_are_the_primary_admins_of_their_own_school(
    demo: Demo, db_session: Session
) -> None:
    seed_platform(demo)
    rows = db_session.execute(
        text(
            "select u.username, s.code, m.role, m.is_primary from school_memberships m"
            " join users u on u.id = m.user_id join schools s on s.id = m.school_id"
        )
    )
    assert {(r.username, r.code, r.role, r.is_primary) for r in rows} == {
        ("ngozi.okeke", "GMC", "school_admin", True),
        ("chiamaka.nwafor", "BSA", "school_admin", True),
        ("femi.adeyemi", "RCS", "school_admin", True),
    }


def test_it_refuses_to_seed_twice(demo: Demo, db_session: Session) -> None:
    seed_platform(demo)
    with pytest.raises(SeedError, match="GMC is already used"):
        seed_platform(demo)
    assert db_session.scalar(text("select count(*) from schools")) == 3


def test_a_failed_request_names_the_route_not_the_body(demo: Demo) -> None:
    owner = demo.as_(SUPER_ADMIN)
    with pytest.raises(SeedError) as failed:
        owner.post(
            "/auth/change-password",
            {"current_password": "wrong-one-here", "new_password": DEMO_PASSWORD},
        )
    assert "/auth/change-password" in str(failed.value)
    assert DEMO_PASSWORD not in str(failed.value)


def test_the_demo_uses_only_fictional_addresses(demo: Demo, db_session: Session) -> None:
    seed_platform(demo)
    emails = set(db_session.scalars(text("select email from users where email is not null")))
    emails |= set(db_session.scalars(text("select email from schools")))
    assert emails
    assert all(e.endswith(".example") for e in emails), emails


@pytest.fixture
def seeded(demo: Demo) -> Demo:
    seed_platform(demo)
    seed_schools(demo)
    return demo


def rows(db: Session, sql: str, **params: Any) -> list[Any]:
    return list(db.execute(text(sql), params))


def test_every_school_has_the_session_and_three_terms(seeded: Demo, db_session: Session) -> None:
    found = rows(
        db_session,
        "select s.code, y.name, t.term_number, t.is_active, t.starts_on, t.next_term_begins"
        " from terms t join academic_sessions y on y.id = t.session_id"
        " join schools s on s.id = t.school_id order by s.code, t.term_number",
    )
    assert [(r.code, r.name, r.term_number, r.is_active) for r in found] == [
        (code, "2026/2027", n, n == 1) for code in ("BSA", "GMC", "RCS") for n in (1, 2, 3)
    ]
    first = next(r for r in found if r.code == "GMC" and r.term_number == 1)
    assert (str(first.starts_on), str(first.next_term_begins)) == ("2026-09-07", "2027-01-05")


def test_gmc_has_its_classes_subjects_and_departments(seeded: Demo, db_session: Session) -> None:
    arms = rows(
        db_session,
        "select c.level, c.name || a.name as arm, count(x.subject_id) as subjects"
        " from class_arms a join classes c on c.id = a.class_id"
        " join schools s on s.id = c.school_id"
        " left join arm_subjects x on x.arm_id = a.id"
        " where s.code = 'GMC' group by c.level, c.name, a.name order by arm",
    )
    assert [(r.level, r.arm) for r in arms] == [
        ("junior_secondary", "JSS 1A"),
        ("junior_secondary", "JSS 1B"),
        ("junior_secondary", "JSS 3A"),
        ("senior_secondary", "SS 1A"),
    ]
    assert all(r.subjects >= 2 for r in arms)
    sciences = set(
        db_session.scalars(
            text(
                "select sb.name from subjects sb join departments d on d.id = sb.department_id"
                " join schools s on s.id = d.school_id where s.code = 'GMC' and d.name = 'Sciences'"
            )
        )
    )
    assert {
        "Mathematics",
        "Basic Science",
        "Basic Technology",
        "Agricultural Science",
        "Computer Studies",
    } <= sciences


def test_the_assessment_structures_add_up(seeded: Demo, db_session: Session) -> None:
    structures = rows(
        db_session,
        "select st.level, string_agg(ac.label || ' ' || ac.max_score, ', ' order by ac.position)"
        " as columns from assessment_structures st"
        " join assessment_components ac on ac.structure_id = st.id"
        " join schools s on s.id = st.school_id where s.code = 'GMC'"
        " group by st.level order by st.level",
    )
    assert [(r.level, r.columns) for r in structures] == [
        ("junior_secondary", "CA1 20, CA2 20, Exam 60"),
        ("senior_secondary", "CA1 10, CA2 10, CA3 10, Project 10, Exam 60"),
    ]


def test_staff_in_every_role_use_the_demo_password(
    app: FastAPI, seeded: Demo, db_session: Session
) -> None:
    roles = {
        (r.username, r.code, r.role, r.is_primary)
        for r in rows(
            db_session,
            "select u.username, s.code, m.role, m.is_primary from school_memberships m"
            " join users u on u.id = m.user_id join schools s on s.id = m.school_id"
            " where m.role <> 'student'",
        )
    }
    assert {
        ("chukwudi.eze", "GMC", "school_admin", False),
        ("emeka.nwosu", "GMC", "reviewer", False),
        ("tunde.adebayo", "GMC", "teacher", False),
        ("ifeoma.chukwu", "BSA", "teacher", False),
        ("ngozi.ani", "BSA", "teacher", False),
        ("amaka.udeh", "BSA", "teacher", False),
    } <= roles
    for username, *_ in roles:
        if username not in ("ngozi.okeke", "chiamaka.nwafor", "femi.adeyemi"):
            assert log_in(client_for(app), username, DEMO_PASSWORD) == 200, username
    still_temporary = db_session.scalar(
        text("select count(*) from users where must_change_password")
    )
    assert still_temporary == 0


def test_no_staff_email_is_queued(seeded: Demo, db_session: Session) -> None:
    """Principals get an activation email and each school office a set-up email;
    staff got login slips, so nothing else is queued."""
    to = set(db_session.scalars(text("select to_address from email_outbox")))
    assert to == {
        "ngozi.okeke@gmc.example",
        "chiamaka.nwafor@bsa.example",
        "femi.adeyemi@rcs.example",
        "office@gmc.example",
        "office@bsa.example",
        "office@rcs.example",
    }


def test_every_demo_subject_has_a_teacher(seeded: Demo, db_session: Session) -> None:
    """So every class can be entered, approved and published."""
    missing = rows(
        db_session,
        "select s.code, c.name || a.name as arm, sb.name from arm_subjects x"
        " join class_arms a on a.id = x.arm_id join classes c on c.id = a.class_id"
        " join schools s on s.id = c.school_id join subjects sb on sb.id = x.subject_id"
        " where not exists (select 1 from teacher_subjects ts"
        "   where ts.arm_id = x.arm_id and ts.subject_id = x.subject_id)",
    )
    assert missing == []


def test_tunde_teaches_mathematics_and_has_jss_1a(seeded: Demo, db_session: Session) -> None:
    taught = rows(
        db_session,
        "select c.name || a.name as arm, sb.name as subject, ta.is_form_teacher"
        " from teacher_assignments ta join users u on u.id = ta.teacher_id"
        " join class_arms a on a.id = ta.arm_id join classes c on c.id = a.class_id"
        " left join subjects sb on sb.id = ta.subject_id"
        " where u.username = 'tunde.adebayo' order by arm, ta.is_form_teacher",
    )
    assert {(r.arm, r.subject, r.is_form_teacher) for r in taught} >= {
        ("JSS 1A", "Mathematics", False),
        ("JSS 1B", "Mathematics", False),
        ("JSS 1A", None, True),
    }


def test_emeka_reviews_sciences(seeded: Demo, db_session: Session) -> None:
    scope = rows(
        db_session,
        "select d.name from reviewer_scopes rs join users u on u.id = rs.reviewer_id"
        " join departments d on d.id = rs.department_id where u.username = 'emeka.nwosu'",
    )
    assert [r.name for r in scope] == ["Sciences"]


def test_bsa_has_a_class_teacher_an_assistant_and_nursery_areas(
    seeded: Demo, db_session: Session
) -> None:
    ifeoma = rows(
        db_session,
        "select c.name || a.name as arm, ta.is_form_teacher, ta.teaches_all_subjects"
        " from teacher_assignments ta join users u on u.id = ta.teacher_id"
        " join class_arms a on a.id = ta.arm_id join classes c on c.id = a.class_id"
        " where u.username = 'ifeoma.chukwu'",
    )
    assert [(r.arm, r.is_form_teacher, r.teaches_all_subjects) for r in ifeoma] == [
        ("Primary 4A", True, True)
    ]
    assistants = rows(
        db_session,
        "select u.username, c.name || a.name as arm from class_assistants x"
        " join users u on u.id = x.assistant_id join class_arms a on a.id = x.arm_id"
        " join classes c on c.id = a.class_id",
    )
    assert ("ngozi.ani", "Primary 4A") in {(r.username, r.arm) for r in assistants}
    areas = rows(
        db_session,
        "select la.name from class_learning_areas cla join classes c on c.id = cla.class_id"
        " join learning_areas la on la.id = cla.learning_area_id"
        " join schools s on s.id = c.school_id where s.code = 'BSA' and c.name = 'Nursery 2'",
    )
    names = {r.name for r in areas}
    assert {"Number work", "Letter work"} <= names
    # Every area given to the class has skills to rate.
    assert "Pre-science" not in names and "Handwriting" not in names
    modes = dict(
        rows(
            db_session,
            "select l.level, l.assessment_mode from school_levels l"
            " join schools s on s.id = l.school_id where s.code = 'BSA' and l.enabled",
        )
    )
    assert modes == {"nursery": "skill_ratings", "primary": "scores"}


def test_rcs_has_a_class_on_each_level(seeded: Demo, db_session: Session) -> None:
    levels = {
        r.level
        for r in rows(
            db_session,
            "select c.level from classes c join schools s on s.id = c.school_id"
            " where s.code = 'RCS'",
        )
    }
    assert levels == {"nursery", "primary", "junior_secondary"}
