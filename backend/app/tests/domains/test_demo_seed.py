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

Round 3a: 20 to 30 fictional pupils per demo class (the brief's names first;
tests use the named ones only), enrolled with their class's subjects;
Chukwuemeka Obi is GMC/2026/014 and a BSA pupil shares 2026/014. Two pupils
get logins. Ikenna Obi joins from GMC's emailed link and accepts BSA's
request, so one account sees wards in both schools; other parents get
login slips. The seed's app never starts a real email or payment run.

Round 3b: teachers enter and submit scores and ratings, the reviewer reviews
Sciences, the principal approves; form teachers enter comments, attendance
and traits; principals write their comments and publish JSS 1A, Primary 4A
and Nursery 2, which fills Students needing attention with the brief's
examples. JSS 1B is left mid-week (one sheet submitted, one with gaps). GMC
and BSA save a report template, GMC pins the sports notice, and no seeded
email is left waiting.

Round 3c: the super admin generates the term's invoices; GMC's stays
unpaid, RCS's is paid by a recorded bank transfer, BSA (free pilot) gets
none. `seed_demo` runs every step in order and reports each one without
the password.
All data is fictional.
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.cli.demo.browser import Demo, SeedError
from app.cli.demo.platform import SUPER_ADMIN, seed_platform
from app.cli.demo.pupils import CLASSES, pupils_for, seed_pupils
from app.cli.demo.results import seed_results, split, total_for
from app.cli.demo.run import seed_demo
from app.cli.demo.schools import seed_schools
from app.platform.email import trigger
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


@contextmanager
def as_sender(db: Session) -> Generator[Session]:
    db.execute(text("set local role app_sender"))
    try:
        yield db
    finally:
        db.execute(text("reset role"))


@pytest.fixture
def demo(app: FastAPI, db_session: Session) -> Demo:
    make_login(db_session, username=SUPER_ADMIN, full_name="Platform Admin", is_super_admin=True)
    made = Demo(app, password=DEMO_PASSWORD, origin=ORIGIN, mail=lambda: as_sender(db_session))
    made.full = False  # the brief's named pupils only: quicker, same rules
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
    with pytest.raises(SeedError, match="already has schools"):
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


@pytest.fixture
def with_pupils(seeded: Demo) -> Demo:
    seed_pupils(seeded)
    return seeded


@pytest.fixture
def with_results(with_pupils: Demo) -> Demo:
    seed_results(with_pupils)
    return with_pupils


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
    assert (str(first.starts_on), str(first.next_term_begins)) == ("2026-09-08", "2027-01-05")


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
    assert to <= {
        "ngozi.okeke@gmc.example",
        "chiamaka.nwafor@bsa.example",
        "femi.adeyemi@rcs.example",
        "office@gmc.example",
        "office@bsa.example",
        "office@rcs.example",
        "ikenna.obi@home.example",
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


def test_the_seed_never_starts_a_real_email_or_payment_run(app: FastAPI, demo: Demo) -> None:
    kick = app.dependency_overrides[trigger.get_email_kick]()
    assert kick() is None
    from app.src.billing import processing

    assert app.dependency_overrides[processing.get_payment_kick]()  # a do-nothing kick


def test_it_refuses_a_database_that_has_any_school(demo: Demo, db_session: Session) -> None:
    from app.tests.factories import create_school

    create_school(db_session, code="ZZZ", name="Some Real School")
    with pytest.raises(SeedError, match="already has schools"):
        seed_platform(demo)


def test_full_classes_have_20_to_30_fictional_pupils() -> None:
    for code, arm in CLASSES:
        pupils = pupils_for(code, arm, full=True)
        assert 20 <= len(pupils) <= 30, (code, arm)
        assert len({(p.first_name, p.surname) for p in pupils}) == len(pupils), (code, arm)
    jss1a = pupils_for("GMC", "JSS 1A", full=True)
    assert len(jss1a) == 25
    chukwuemeka = next(p for p in jss1a if p.first_name == "Chukwuemeka")
    assert chukwuemeka.admission_number == "GMC/2026/014"
    numbers = [p.admission_number for code, arm in CLASSES if code == "GMC"
               for p in pupils_for(code, arm, full=True)]  # fmt: skip
    assert len(numbers) == len(set(numbers))
    bsa = [p.admission_number for code, arm in CLASSES if code == "BSA"
           for p in pupils_for(code, arm, full=True)]  # fmt: skip
    assert "2026/014" in bsa and len(bsa) == len(set(bsa))


def test_pupils_are_enrolled_with_their_class_subjects(
    with_pupils: Demo, db_session: Session
) -> None:
    found = rows(
        db_session,
        "select p.first_name, p.surname, p.admission_number, c.name || a.name as arm,"
        " (select count(*) from student_subjects ss where ss.enrolment_id = e.id) as subjects"
        " from students p join enrolments e on e.student_id = p.id"
        " join class_arms a on a.id = e.arm_id join classes c on c.id = a.class_id"
        " join schools s on s.id = p.school_id where s.code = 'GMC'",
    )
    by_name = {(r.first_name, r.surname): r for r in found}
    chukwuemeka = by_name[("Chukwuemeka", "Obi")]
    assert (chukwuemeka.admission_number, chukwuemeka.arm, chukwuemeka.subjects) == (
        "GMC/2026/014",
        "JSS 1A",
        8,
    )
    assert by_name[("Adaeze", "Obi")].arm == "JSS 3A"
    assert all(r.subjects > 0 for r in found)
    for code, arm in CLASSES:
        count = db_session.scalar(
            text(
                "select count(*) from enrolments e join class_arms a on a.id = e.arm_id"
                " join classes c on c.id = a.class_id join schools s on s.id = c.school_id"
                " where s.code = :code and c.name || a.name = :arm"
            ),
            {"code": code, "arm": arm},
        )
        assert count == len(pupils_for(code, arm, full=False)) > 0, (code, arm)


def test_two_pupils_log_in_with_their_school_code(app: FastAPI, with_pupils: Demo) -> None:
    assert log_in(client_for(app), "GMC/2026/014", DEMO_PASSWORD, school_code="GMC") == 200
    assert log_in(client_for(app), "2026/014", DEMO_PASSWORD, school_code="BSA") == 200
    # The same number at the other school is not this pupil (AC02.6).
    assert log_in(client_for(app), "2026/014", DEMO_PASSWORD, school_code="GMC") == 401


def test_ikenna_is_one_parent_in_two_schools(
    app: FastAPI, with_pupils: Demo, db_session: Session
) -> None:
    links = rows(
        db_session,
        "select s.code, p.first_name from guardian_students gs"
        " join guardians g on g.id = gs.guardian_id join students p on p.id = gs.student_id"
        " join schools s on s.id = g.school_id join users u on u.id = g.user_id"
        " where u.email = 'ikenna.obi@home.example'",
    )
    assert {(r.code, r.first_name) for r in links} == {
        ("GMC", "Chukwuemeka"),
        ("GMC", "Adaeze"),
        ("BSA", "Kosi"),
    }
    accounts = db_session.scalar(
        text("select count(*) from users where email = 'ikenna.obi@home.example'")
    )
    assert accounts == 1
    assert log_in(client_for(app), "ikenna.obi@home.example", DEMO_PASSWORD) == 200
    children = with_pupils.as_("ikenna.obi").get("/me/children")
    assert {school["school_code"] for school in children} == {"GMC", "BSA"}


def test_other_parents_use_login_slips(
    app: FastAPI, with_pupils: Demo, db_session: Session
) -> None:
    for username in ("aisha.ibrahim", "ada.okeke", "peter.udo"):
        assert log_in(client_for(app), username, DEMO_PASSWORD) == 200, username
    no_email = db_session.scalar(
        text(
            "select count(*) from users where username in ('aisha.ibrahim', 'ada.okeke',"
            " 'peter.udo') and email is null"
        )
    )
    assert no_email == 3


def test_no_seeded_email_is_left_waiting(with_pupils: Demo, db_session: Session) -> None:
    """The seed read its own mail; nothing is left for the real sender."""
    assert db_session.scalar(text("select count(*) from email_outbox where status = 'queued'")) == 0


@pytest.mark.parametrize(
    ("total", "columns"),
    [(78, [20, 20, 60]), (38, [20, 20, 60]), (100, [20, 20, 60]), (0, [20, 20, 60]),
     (63, [10, 10, 10, 10, 60]), (97, [10, 10, 10, 10, 60]), (7, [10, 10, 10, 10, 60])],
)  # fmt: skip
def test_a_total_is_split_across_the_columns(total: int, columns: list[int]) -> None:
    parts = split(total, columns)
    assert sum(parts) == total
    assert all(0 <= part <= top for part, top in zip(parts, columns, strict=True))


def test_the_brief_examples_have_their_totals() -> None:
    assert total_for("Chukwuemeka Obi", "Mathematics") == 78
    assert total_for("Musa Ibrahim", "Mathematics") == 38
    assert total_for("Halima Garba", "Basic Science") == 35
    assert total_for("Halima Garba", "Mathematics") == 39
    from app.cli.demo.schools import JSS

    subjects = JSS
    daniel = [total_for("Daniel Okon", subject) for subject in subjects]
    assert sum(daniel) / len(daniel) == 38.5
    assert sum(1 for t in daniel if t < 40) == 6
    # Everyone else passes, so the list holds only the brief's examples.
    assert total_for("Zainab Yusuf", "Mathematics") >= 40


def test_three_classes_are_published(with_results: Demo, db_session: Session) -> None:
    published = rows(
        db_session,
        "select s.code, c.name || a.name as arm, count(*) as reports"
        " from report_documents d join class_arms a on a.id = d.arm_id"
        " join classes c on c.id = a.class_id join schools s on s.id = c.school_id"
        " where d.status = 'valid' group by s.code, c.name, a.name order by arm",
    )
    expected = {
        ("GMC", "JSS 1A"): len(pupils_for("GMC", "JSS 1A", full=False)),
        ("BSA", "Primary 4A"): len(pupils_for("BSA", "Primary 4A", full=False)),
        ("BSA", "Nursery 2"): len(pupils_for("BSA", "Nursery 2", full=False)),
    }
    assert {(r.code, r.arm): r.reports for r in published} == expected
    chukwuemeka = rows(
        db_session,
        "select ac.label, sc.value from scores sc join enrolments e on e.id = sc.enrolment_id"
        " join students p on p.id = e.student_id join result_sheets r on r.id = sc.sheet_id"
        " join subjects sb on sb.id = r.subject_id"
        " join assessment_components ac on ac.id = sc.component_id"
        " where p.admission_number = 'GMC/2026/014' and sb.name = 'Mathematics'"
        " order by ac.position",
    )
    assert [(r.label, r.value) for r in chukwuemeka] == [("CA1", 16), ("CA2", 15), ("Exam", 47)]


def test_students_needing_attention_shows_the_brief_examples(with_results: Demo) -> None:
    ngozi = with_results.as_("ngozi.okeke")
    by_subject = ngozi.get("/attention?view=by_subject")["rows"]
    found = {(r["student_name"], r["subject"], r["score"]) for r in by_subject}
    assert ("Musa Ibrahim", "Mathematics", 38) in found
    assert ("Halima Garba", "Basic Science", 35) in found
    assert ("Halima Garba", "Mathematics", 39) in found
    by_student = ngozi.get("/attention?view=by_student")["rows"]
    daniel = next(r for r in by_student if r["student_name"] == "Daniel Okon")
    assert (daniel["failed_count"], daniel["average"], daniel["average_below_pass_mark"]) == (
        6,
        "38.50",
        True,
    )
    skills = with_results.as_("chiamaka.nwafor").get("/attention?view=by_learning_area")["rows"]
    assert ("Hauwa Sani", "Number work", "Counts 1 to 20") in {
        (r["student_name"], r["learning_area"], r["skill"]) for r in skills
    }


def test_ikenna_sees_published_reports_in_both_schools(with_results: Demo) -> None:
    ikenna = with_results.as_("ikenna.obi")
    seen: set[tuple[str, str]] = set()
    for school in ikenna.get("/me/children"):
        for child in school["children"]:
            reports = ikenna.get(f"/me/students/{child['student_id']}/reports",
                                 school=school["school_id"])  # fmt: skip
            if reports:
                seen.add((school["school_code"], child["name"].split()[0]))
    assert {("GMC", "Chukwuemeka"), ("BSA", "Kosi")} <= seen


def test_jss_1b_is_left_mid_week(with_results: Demo, db_session: Session) -> None:
    sheets = {
        r.subject: r.status
        for r in rows(
            db_session,
            "select sb.name as subject, r.status from result_sheets r"
            " join subjects sb on sb.id = r.subject_id join class_arms a on a.id = r.arm_id"
            " join classes c on c.id = a.class_id where c.name || a.name = 'JSS 1B'",
        )
    }
    assert sheets == {"Mathematics": "submitted", "English Language": "draft"}
    dashboard = with_results.as_("ngozi.okeke").get("/dashboard/school")["results"]
    assert dashboard["missing_scores"]["count"] > 0
    assert dashboard["attention"]["subject_results"] >= 4


def test_templates_and_notices_are_there(with_results: Demo, db_session: Session) -> None:
    templates = {
        (r.code, r.level, r.style)
        for r in rows(
            db_session,
            "select s.code, t.level, t.style from report_templates t"
            " join schools s on s.id = t.school_id",
        )
    }
    assert ("GMC", "junior_secondary", "classic") in templates
    assert ("BSA", "primary", "modern") in templates
    pinned = rows(
        db_session,
        "select s.code, n.title, n.pinned from notices n join schools s on s.id = n.school_id"
        " where n.kind = 'manual'",
    )
    assert ("GMC", "Inter-house sports holds on Friday, 14 November", True) in {
        (r.code, r.title, r.pinned) for r in pinned
    }
    assert db_session.scalar(text("select count(*) from email_outbox where status = 'queued'")) == 0


def test_the_whole_seed_runs_and_bills_two_schools(demo: Demo, db_session: Session) -> None:
    said: list[str] = []
    seed_demo(demo, said.append)
    invoices = {
        r.code: r
        for r in rows(
            db_session,
            "select s.code, i.status, i.amount_kobo, (select p.receipt_number from payments p"
            " where p.invoice_id = i.id and p.status = 'succeeded') as receipt_number"
            " from invoices i"
            " join schools s on s.id = i.school_id",
        )
    }
    assert set(invoices) == {"GMC", "RCS"}  # BSA is on a free pilot
    assert invoices["GMC"].status == "unpaid"
    assert (invoices["RCS"].status, invoices["RCS"].receipt_number is not None) == ("paid", True)
    assert all(i.amount_kobo > 0 for i in invoices.values())
    assert db_session.scalar(text("select count(*) from email_outbox where status = 'queued'")) == 0
    assert any("Done" in line for line in said)
    assert all(DEMO_PASSWORD not in line for line in said)
