"""School structure (BUILD_PROMPT 9.1 item 3; SPEC F04, F25; AC04.1, AC04.2, AC25.3,
AT-04.2, AT-04.3; D-137).

Behaviour: each school keeps its own academic sessions and terms (one active
term at a time), classes with arms at a level that is switched on, and
departments and subjects; every row points only at rows of the same school;
school users manage their own school's structure and nothing of any other
school; the platform reads sessions and terms (for billing) and nothing else.
All data is fictional (design brief section 12).
"""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from tests.db_support import acting_as, refused, violates
from tests.factories import (
    add_arm_subject,
    create_arm,
    create_class,
    create_department,
    create_school,
    create_session,
    create_subject,
    create_term,
)

TABLES = (
    "academic_sessions",
    "terms",
    "classes",
    "class_arms",
    "departments",
    "subjects",
    "arm_subjects",
)
COUNT: dict[str, TextClause] = {table: text(f"select count(*) from {table}") for table in TABLES}  # noqa: S608


@dataclass(frozen=True)
class Structure:
    gmc: uuid.UUID
    bsa: uuid.UUID
    gmc_session: uuid.UUID
    gmc_first_term: uuid.UUID
    jss1: uuid.UUID
    jss1a: uuid.UUID
    sciences: uuid.UUID
    mathematics: uuid.UUID
    bsa_session: uuid.UUID
    primary4a: uuid.UUID
    bsa_mathematics: uuid.UUID


@pytest.fixture
def structure(db_session: Session) -> Structure:
    s = db_session
    gmc = create_school(s, code="GMC", name="Greenfield Model College")
    bsa = create_school(s, code="BSA", name="Bright Stars Academy", school_type="nursery_primary")

    gmc_session = create_session(s, gmc)
    gmc_first_term = create_term(s, gmc, gmc_session, 1, is_active=True)
    jss1 = create_class(s, gmc, "junior_secondary", "JSS 1")
    jss1a = create_arm(s, gmc, jss1, "A")
    sciences = create_department(s, gmc, "Sciences")
    mathematics = create_subject(
        s, gmc, "Mathematics", department_id=sciences, category="Science and Mathematics"
    )
    add_arm_subject(s, gmc, jss1a, mathematics)

    bsa_session = create_session(s, bsa)
    create_term(s, bsa, bsa_session, 1, is_active=True)
    primary4 = create_class(s, bsa, "primary", "Primary 4")
    primary4a = create_arm(s, bsa, primary4, "A")
    early_years = create_department(s, bsa, "Early Years")
    bsa_mathematics = create_subject(s, bsa, "Mathematics", department_id=early_years)
    add_arm_subject(s, bsa, primary4a, bsa_mathematics)
    return Structure(
        gmc,
        bsa,
        gmc_session,
        gmc_first_term,
        jss1,
        jss1a,
        sciences,
        mathematics,
        bsa_session,
        primary4a,
        bsa_mathematics,
    )


def term_insert(
    school_id: uuid.UUID,
    session_id: uuid.UUID,
    number: int,
    starts: str,
    ends: str,
    nxt: str | None,
) -> tuple[TextClause, dict[str, object]]:
    return (
        text(
            "insert into terms (school_id, session_id, term_number, starts_on, ends_on,"
            " next_term_begins) values (:school, :session, :number, :starts, :ends, :next)"
        ),
        {
            "school": school_id,
            "session": session_id,
            "number": number,
            "starts": starts,
            "ends": ends,
            "next": nxt,
        },
    )


# --- academic sessions and terms ------------------------------------------------


@pytest.mark.parametrize("name", ["2026-2027", "2026/2028", "26/27", "2026/2025", "2026/2027 "])
def test_a_session_is_named_like_2026_slash_2027(
    structure: Structure, db_session: Session, name: str
) -> None:
    with violates(db_session, "ck_academic_sessions_name_format"):
        create_session(db_session, structure.gmc, name)


def test_a_session_ends_after_it_starts(structure: Structure, db_session: Session) -> None:
    with violates(db_session, "ck_academic_sessions_dates_in_order"):
        db_session.execute(
            text(
                "insert into academic_sessions (school_id, name, starts_on, ends_on)"
                " values (:school, '2027/2028', '2028-07-31', '2027-09-01')"
            ),
            {"school": structure.gmc},
        )


def test_session_names_are_unique_within_a_school(
    structure: Structure, db_session: Session
) -> None:
    with violates(db_session, "uq_academic_sessions_school_id_name"):
        create_session(db_session, structure.gmc, "2026/2027")


@pytest.mark.parametrize("number", [0, 4])
def test_a_session_has_a_first_second_and_third_term(
    structure: Structure, db_session: Session, number: int
) -> None:
    with violates(db_session, "ck_terms_term_number_allowed"):
        create_term(db_session, structure.gmc, structure.gmc_session, number)


def test_each_term_appears_once_per_session(structure: Structure, db_session: Session) -> None:
    with violates(db_session, "uq_terms_session_id_term_number"):
        create_term(db_session, structure.gmc, structure.gmc_session, 1)


def test_a_term_ends_after_it_starts(structure: Structure, db_session: Session) -> None:
    statement, values = term_insert(
        structure.gmc, structure.gmc_session, 2, "2027-04-10", "2027-01-06", None
    )
    with violates(db_session, "ck_terms_dates_in_order"):
        db_session.execute(statement, values)


def test_next_term_begins_after_the_term_ends(structure: Structure, db_session: Session) -> None:
    statement, values = term_insert(
        structure.gmc, structure.gmc_session, 2, "2027-01-06", "2027-04-10", "2027-04-01"
    )
    with violates(db_session, "ck_terms_next_term_after_end"):
        db_session.execute(statement, values)


def test_a_school_has_one_active_term(structure: Structure, db_session: Session) -> None:
    # AC04.1: activating another term means deactivating the previous one first.
    second = create_term(db_session, structure.gmc, structure.gmc_session, 2)

    with violates(db_session, "ix_terms_one_active_per_school"):
        db_session.execute(text("update terms set is_active = true where id = :id"), {"id": second})

    db_session.execute(
        text("update terms set is_active = false where id = :id"), {"id": structure.gmc_first_term}
    )
    db_session.execute(text("update terms set is_active = true where id = :id"), {"id": second})
    active = list(
        db_session.scalars(
            text("select id from terms where school_id = :school and is_active"),
            {"school": structure.gmc},
        )
    )
    assert active == [second]


def test_a_term_belongs_to_a_session_of_the_same_school(
    structure: Structure, db_session: Session
) -> None:
    # Denied: a GMC term cannot sit in BSA's session.
    with violates(db_session, "fk_terms_session_id_academic_sessions"):
        create_term(db_session, structure.gmc, structure.bsa_session, 2)


# --- classes, arms and levels ----------------------------------------------------


def test_a_class_needs_its_level_switched_on(structure: Structure, db_session: Session) -> None:
    # Denied (AC04.2, AC25.3, AT-04.2): BSA has Secondary report cards off.
    with violates(db_session, "classes_level_is_on"):
        create_class(db_session, structure.bsa, "junior_secondary", "JSS 1")


def test_a_class_at_an_unknown_level_is_refused(structure: Structure, db_session: Session) -> None:
    with violates(db_session, "classes_level_is_on"):
        create_class(db_session, structure.gmc, "creche", "Creche 1")


def test_turning_a_level_off_keeps_its_classes(db_session: Session) -> None:
    # AT-04.3: data is kept; only new classes at that level are refused.
    rcs = create_school(
        db_session, code="RCS", name="Royal Crest Schools", school_type="all_levels"
    )
    nursery2 = create_class(db_session, rcs, "nursery", "Nursery 2")
    db_session.execute(
        text(
            "update school_levels set enabled = false where school_id = :id and level = 'nursery'"
        ),
        {"id": rcs},
    )

    assert (
        db_session.scalar(text("select name from classes where id = :id"), {"id": nursery2})
        == "Nursery 2"
    )
    with violates(db_session, "classes_level_is_on"):
        create_class(db_session, rcs, "nursery", "Nursery 3")


def test_class_names_are_unique_within_a_school(structure: Structure, db_session: Session) -> None:
    with violates(db_session, "ix_classes_unique_name"):
        create_class(db_session, structure.gmc, "junior_secondary", "jss 1")


@pytest.mark.parametrize("name", ["", "   ", "x" * 41])
def test_a_class_has_a_short_name(structure: Structure, db_session: Session, name: str) -> None:
    with violates(db_session, "ck_classes_name_valid"):
        create_class(db_session, structure.gmc, "junior_secondary", name)


def test_arms_are_unique_within_a_class(structure: Structure, db_session: Session) -> None:
    create_arm(db_session, structure.gmc, structure.jss1, "B")

    with violates(db_session, "ix_class_arms_unique_name"):
        create_arm(db_session, structure.gmc, structure.jss1, "b")


def test_a_single_arm_class_may_leave_the_arm_name_empty(db_session: Session) -> None:
    bsa = create_school(
        db_session, code="BSA", name="Bright Stars Academy", school_type="nursery_primary"
    )
    nursery2 = create_class(db_session, bsa, "nursery", "Nursery 2")

    create_arm(db_session, bsa, nursery2, "")


@pytest.mark.parametrize("name", [" A", "A ", "x" * 21])
def test_an_arm_name_is_short_and_trimmed(
    structure: Structure, db_session: Session, name: str
) -> None:
    with violates(db_session, "ck_class_arms_name_valid"):
        create_arm(db_session, structure.gmc, structure.jss1, name)


def test_an_arm_belongs_to_a_class_of_the_same_school(
    structure: Structure, db_session: Session
) -> None:
    with violates(db_session, "fk_class_arms_class_id_classes"):
        create_arm(db_session, structure.bsa, structure.jss1, "C")


# --- departments, subjects and what each arm takes ---------------------------------


def test_department_names_are_unique_within_a_school(
    structure: Structure, db_session: Session
) -> None:
    create_department(db_session, structure.bsa, "Sciences")  # another school: fine

    with violates(db_session, "ix_departments_unique_name"):
        create_department(db_session, structure.gmc, "SCIENCES")


def test_subject_names_are_unique_within_a_school(
    structure: Structure, db_session: Session
) -> None:
    with violates(db_session, "ix_subjects_unique_name"):
        create_subject(db_session, structure.gmc, "mathematics")


@pytest.mark.parametrize("category", ["", "  ", "x" * 61])
def test_a_subject_category_is_optional_but_never_blank(
    structure: Structure, db_session: Session, category: str
) -> None:
    with violates(db_session, "ck_subjects_category_valid"):
        create_subject(db_session, structure.gmc, "Basic Science", category=category)


def test_a_subjects_department_is_in_the_same_school(
    structure: Structure, db_session: Session
) -> None:
    with violates(db_session, "fk_subjects_department_id_departments"):
        create_subject(db_session, structure.bsa, "Basic Science", department_id=structure.sciences)


def test_an_arm_takes_each_subject_once(structure: Structure, db_session: Session) -> None:
    with violates(db_session, "uq_arm_subjects_arm_id_subject_id"):
        add_arm_subject(db_session, structure.gmc, structure.jss1a, structure.mathematics)


def test_an_arm_takes_only_its_own_schools_subjects(
    structure: Structure, db_session: Session
) -> None:
    with violates(db_session, "fk_arm_subjects_subject_id_subjects"):
        add_arm_subject(db_session, structure.gmc, structure.jss1a, structure.bsa_mathematics)


# --- row-level security ----------------------------------------------------------


@pytest.mark.parametrize("table", TABLES)
def test_a_school_sees_only_its_own_structure(
    structure: Structure, db_session: Session, table: str
) -> None:
    with acting_as(db_session, "app_user", school_id=structure.gmc):
        own_school = db_session.scalar(COUNT[table])
    with acting_as(db_session, "app_user", school_id=structure.bsa):
        other_school = db_session.scalar(COUNT[table])
    total = db_session.scalar(COUNT[table])

    assert own_school + other_school == total
    assert own_school >= 1
    assert other_school >= 1


def test_a_school_manages_its_own_structure(structure: Structure, db_session: Session) -> None:
    with acting_as(db_session, "app_user", school_id=structure.gmc):
        second = create_term(db_session, structure.gmc, structure.gmc_session, 2)
        jss2 = create_class(db_session, structure.gmc, "junior_secondary", "JSS 2")
        jss2a = create_arm(db_session, structure.gmc, jss2, "A")
        english = create_subject(
            db_session, structure.gmc, "English Language", category="Languages"
        )
        add_arm_subject(db_session, structure.gmc, jss2a, english)
        renamed = list(
            db_session.scalars(
                text("update class_arms set name = 'Gold' where id = :id returning id"),
                {"id": jss2a},
            )
        )

    assert second and renamed == [jss2a]


@pytest.mark.parametrize(
    "build",
    ["session", "term", "department", "subject"],
)
def test_a_school_cannot_add_structure_to_another_school(
    structure: Structure, db_session: Session, build: str
) -> None:
    # Denied: row-level security refuses rows for any school but the current one.
    builders = {
        "session": lambda: create_session(db_session, structure.bsa, "2027/2028"),
        "term": lambda: create_term(db_session, structure.bsa, structure.bsa_session, 2),
        "department": lambda: create_department(db_session, structure.bsa, "Languages"),
        "subject": lambda: create_subject(db_session, structure.bsa, "English Studies"),
    }
    with acting_as(db_session, "app_user", school_id=structure.gmc), refused(db_session):
        builders[build]()


def test_a_school_cannot_add_a_class_to_another_school(
    structure: Structure, db_session: Session
) -> None:
    # Denied too, but by the level rule first: row-level security hides BSA's
    # levels from GMC, so to GMC no BSA level is switched on at all.
    with (
        acting_as(db_session, "app_user", school_id=structure.gmc),
        violates(db_session, "classes_level_is_on"),
    ):
        create_class(db_session, structure.bsa, "primary", "Primary 5")


def test_a_school_user_is_refused_a_class_at_a_level_that_is_off(
    structure: Structure, db_session: Session
) -> None:
    # AT-04.2 through the app's own role, not only as the owner.
    with (
        acting_as(db_session, "app_user", school_id=structure.bsa),
        violates(db_session, "classes_level_is_on"),
    ):
        create_class(db_session, structure.bsa, "junior_secondary", "JSS 1")


def test_the_platform_reads_sessions_and_terms_for_billing(
    structure: Structure, db_session: Session
) -> None:
    with acting_as(db_session, "app_platform"):
        sessions = db_session.scalar(COUNT["academic_sessions"])
        terms = db_session.scalar(COUNT["terms"])

    assert (sessions, terms) == (2, 2)


@pytest.mark.parametrize(
    "statement",
    [
        "select count(*) from classes",
        "select count(*) from subjects",
        "update terms set is_active = false",
        "delete from academic_sessions",
    ],
)
def test_the_platform_reads_nothing_else_and_changes_nothing(
    structure: Structure, db_session: Session, statement: str
) -> None:
    with acting_as(db_session, "app_platform"), refused(db_session):
        db_session.execute(text(statement))


@pytest.mark.parametrize("table", TABLES)
def test_the_verification_role_cannot_read_structure(
    structure: Structure, db_session: Session, table: str
) -> None:
    with acting_as(db_session, "app_verifier"), refused(db_session):
        db_session.execute(COUNT[table])
