"""Grading and assessment set-up (BUILD_PROMPT 9.1 item 5; SPEC F08 rules 0 to 6,
section 12; AC08.2, AC08.3, AC08.5, AC08.6; AT-04.2, AT-07.1 to AT-07.6, AT-30.2;
D-135, D-137).

Behaviour: each school keeps, per level, grade bands and remark bands that
cover 0 to 100 with no gaps or overlaps; one assessment structure per level
per term that holds the assessment mode and, in Scores mode, 1 to 8
components adding up to exactly 100 (none in Skill ratings mode), locked for
the term once entries exist (mode and components then wait for the next
term); affective and psychomotor rating traits with a 1 to 5 key; and a pass
mark from 1 to 99. Each school sees and changes only its own set-up.
All data is fictional; defaults come from grading/defaults.py (SPEC F08).
"""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from app.src.grading.defaults import (
    AFFECTIVE_TRAITS,
    DEFAULT_PASS_MARK,
    PRIMARY_GRADE_BANDS,
    PSYCHOMOTOR_TRAITS,
    SECONDARY_GRADE_BANDS,
    Component,
)
from app.tests.db_support import acting_as, refused, run_commit_checks, violates
from app.tests.factories import (
    add_component,
    add_grade_bands,
    add_remark_band,
    add_trait,
    add_trait_key,
    create_school,
    create_session,
    create_structure,
    create_term,
)

TABLES = (
    "grade_bands",
    "remark_bands",
    "assessment_structures",
    "assessment_components",
    "rating_traits",
    "trait_scale_points",
    "school_settings",
)
COUNT: dict[str, TextClause] = {table: text(f"select count(*) from {table}") for table in TABLES}  # noqa: S608
SSS_COMPONENTS = (
    Component("Continuous assessment 1", "CA1", 10),
    Component("Continuous assessment 2", "CA2", 10),
    Component("Continuous assessment 3", "CA3", 10),
    Component("Project", "Project", 10),
    Component("Examination", "Exam", 60),
)


@dataclass(frozen=True)
class Setup:
    gmc: uuid.UUID
    bsa: uuid.UUID
    first_term: uuid.UUID  # GMC, 2026/2027
    second_term: uuid.UUID
    jss_first_term: uuid.UUID  # GMC Junior Secondary structure, First Term
    bsa_term: uuid.UUID
    nursery_first_term: uuid.UUID  # BSA Nursery structure (Skill ratings)


@pytest.fixture
def setup(db_session: Session) -> Setup:
    s = db_session
    gmc = create_school(s, code="GMC", name="Greenfield Model College")
    bsa = create_school(s, code="BSA", name="Bright Stars Academy", school_type="nursery_primary")

    gmc_session = create_session(s, gmc)
    first_term = create_term(s, gmc, gmc_session, 1, is_active=True)
    second_term = create_term(s, gmc, gmc_session, 2)
    for level in ("junior_secondary", "senior_secondary"):
        add_grade_bands(s, gmc, level, SECONDARY_GRADE_BANDS)
    jss_first_term = create_structure(s, gmc, "junior_secondary", first_term)
    create_structure(s, gmc, "senior_secondary", first_term, SSS_COMPONENTS)
    add_remark_band(s, gmc, "junior_secondary", 0, 49, ["Work harder next term."])
    add_remark_band(
        s, gmc, "junior_secondary", 50, 100, ["A good result.", "Keep it up.", "Well done."]
    )
    for position, name in enumerate(AFFECTIVE_TRAITS, start=1):
        add_trait(s, gmc, "affective", name, position)
    for position, name in enumerate(PSYCHOMOTOR_TRAITS, start=1):
        add_trait(s, gmc, "psychomotor", name, position)
    add_trait_key(s, gmc)
    s.execute(text("insert into school_settings (school_id) values (:id)"), {"id": gmc})

    bsa_session = create_session(s, bsa)
    bsa_term = create_term(s, bsa, bsa_session, 1, is_active=True)
    add_grade_bands(s, bsa, "primary", PRIMARY_GRADE_BANDS)
    create_structure(s, bsa, "primary", bsa_term)
    nursery_first_term = create_structure(s, bsa, "nursery", bsa_term, (), mode="skill_ratings")
    add_remark_band(s, bsa, "primary", 0, 100, ["A good term."])
    add_trait(s, bsa, "affective", "Punctuality", 1)
    add_trait_key(s, bsa)
    s.execute(
        text("insert into school_settings (school_id, pass_mark) values (:id, 45)"), {"id": bsa}
    )
    run_commit_checks(s)
    return Setup(gmc, bsa, first_term, second_term, jss_first_term, bsa_term, nursery_first_term)


def lock(session: Session, structure_id: uuid.UUID) -> None:
    """What the first saved score or rating will do (BUILD_PROMPT 9.1 item 6)."""
    session.execute(
        text("update assessment_structures set locked_at = now() where id = :id"),
        {"id": structure_id},
    )


# --- grade bands ------------------------------------------------------------------


def test_default_primary_grading_gives_65_a_b(setup: Setup, db_session: Session) -> None:
    # AC08.5 and AT-07.6: a Primary total of 65 is B, Very good.
    grade = db_session.execute(
        text(
            "select grade, remark from grade_bands where school_id = :school"
            " and level = 'primary' and 65 between min_score and max_score"
        ),
        {"school": setup.bsa},
    ).one()

    assert tuple(grade) == ("B", "Very good")


def test_default_secondary_grading_runs_a1_to_f9(setup: Setup, db_session: Session) -> None:
    grades = list(
        db_session.scalars(
            text(
                "select grade from grade_bands where school_id = :school"
                " and level = 'junior_secondary' order by min_score desc"
            ),
            {"school": setup.gmc},
        )
    )

    assert grades == ["A1", "B2", "B3", "C4", "C5", "C6", "D7", "E8", "F9"]


@pytest.mark.parametrize(("low", "high"), [(80, 70), (-1, 10), (90, 101)])
def test_a_band_runs_upwards_inside_0_to_100(
    setup: Setup, db_session: Session, low: int, high: int
) -> None:
    with violates(db_session, "ck_grade_bands_range_valid"):
        db_session.execute(
            text(
                "insert into grade_bands (school_id, level, grade, min_score, max_score, remark)"
                " values (:school, 'primary', 'X', :low, :high, 'Test')"
            ),
            {"school": setup.gmc, "low": low, "high": high},
        )


@pytest.mark.parametrize("grade", ["", "a1", "TOOLONG", "A 1"])
def test_a_grade_is_a_short_capital_code(setup: Setup, db_session: Session, grade: str) -> None:
    with violates(db_session, "ck_grade_bands_grade_format"):
        db_session.execute(
            text(
                "insert into grade_bands (school_id, level, grade, min_score, max_score, remark)"
                " values (:school, 'primary', :grade, 0, 100, 'Test')"
            ),
            {"school": setup.gmc, "grade": grade},
        )


def test_a_grade_appears_once_per_level(setup: Setup, db_session: Session) -> None:
    with violates(db_session, "uq_grade_bands_school_id_level_grade"):
        add_grade_bands(db_session, setup.gmc, "junior_secondary", [SECONDARY_GRADE_BANDS[0]])


def test_grade_bands_leave_no_gaps(setup: Setup, db_session: Session) -> None:
    # Denied ("No grade covers 40 to 44."): every total from 0 to 100 needs a grade.
    db_session.execute(
        text(
            "delete from grade_bands where school_id = :school"
            " and level = 'junior_secondary' and grade = 'E8'"
        ),
        {"school": setup.gmc},
    )

    with violates(db_session, "grade_bands_cover_0_to_100"):
        run_commit_checks(db_session)


def test_grade_bands_do_not_overlap(setup: Setup, db_session: Session) -> None:
    db_session.execute(
        text(
            "update grade_bands set min_score = 72 where school_id = :school"
            " and level = 'junior_secondary' and grade = 'A1'"
        ),
        {"school": setup.gmc},
    )

    with violates(db_session, "grade_bands_cover_0_to_100"):
        run_commit_checks(db_session)


def test_a_school_can_rewrite_its_bands_in_one_go(setup: Setup, db_session: Session) -> None:
    # Bands are checked at save (commit), so delete-and-replace in one change works.
    db_session.execute(
        text("delete from grade_bands where school_id = :school and level = 'primary'"),
        {"school": setup.bsa},
    )
    add_grade_bands(db_session, setup.bsa, "primary", SECONDARY_GRADE_BANDS)

    run_commit_checks(db_session)


# --- remark bands (suggested class teacher comments, F22 rule 3) -------------------


@pytest.mark.parametrize("comments", [[], ["One", "Two", "Three", "Four"], [" "], ["x" * 301]])
def test_a_remark_band_holds_one_to_three_comments(
    setup: Setup, db_session: Session, comments: list[str]
) -> None:
    with violates(db_session, "ck_remark_bands_comments_valid"):
        add_remark_band(db_session, setup.gmc, "senior_secondary", 0, 100, comments)


def test_remark_bands_cover_0_to_100(setup: Setup, db_session: Session) -> None:
    add_remark_band(db_session, setup.gmc, "senior_secondary", 0, 59, ["Work harder."])

    with violates(db_session, "remark_bands_cover_0_to_100"):
        run_commit_checks(db_session)


# --- assessment structures and components ------------------------------------------


def test_the_grid_shows_the_levels_components_in_order(setup: Setup, db_session: Session) -> None:
    # AT-07.1 and AT-07.2: SSS has five columns, JSS keeps CA1, CA2, Exam.
    columns = text(
        "select c.label || ' /' || c.max_score from assessment_components c"
        " join assessment_structures s on s.id = c.structure_id"
        " where s.school_id = :school and s.level = :level and s.term_id = :term"
        " order by c.position"
    )
    values = {"school": setup.gmc, "term": setup.first_term}

    sss = list(db_session.scalars(columns, {**values, "level": "senior_secondary"}))
    jss = list(db_session.scalars(columns, {**values, "level": "junior_secondary"}))

    assert sss == ["CA1 /10", "CA2 /10", "CA3 /10", "Project /10", "Exam /60"]
    assert jss == ["CA1 /20", "CA2 /20", "Exam /60"]


@pytest.mark.parametrize("exam", [55, 65])
def test_components_add_up_to_exactly_100(setup: Setup, db_session: Session, exam: int) -> None:
    # AC08.2 and AT-07.3: 95 or 105 is refused.
    create_structure(
        db_session,
        setup.gmc,
        "junior_secondary",
        setup.second_term,
        (Component("CA1", "CA1", 20), Component("CA2", "CA2", 20), Component("Exam", "Exam", exam)),
    )

    with violates(db_session, "assessment_structures_components_add_up"):
        run_commit_checks(db_session)


def test_a_scores_structure_has_at_least_one_component(setup: Setup, db_session: Session) -> None:
    create_structure(db_session, setup.gmc, "junior_secondary", setup.second_term, ())

    with violates(db_session, "assessment_structures_components_add_up"):
        run_commit_checks(db_session)


def test_a_structure_has_at_most_eight_components(setup: Setup, db_session: Session) -> None:
    with violates(db_session, "ck_assessment_components_position_range"):
        add_component(
            db_session, setup.gmc, setup.jss_first_term, 9, Component("Practical", "Prac", 1)
        )


@pytest.mark.parametrize("maximum", [0, 101])
def test_a_component_maximum_is_1_to_100(setup: Setup, db_session: Session, maximum: int) -> None:
    with violates(db_session, "ck_assessment_components_max_score_range"):
        add_component(
            db_session, setup.gmc, setup.jss_first_term, 4, Component("Test", "Test", maximum)
        )


def test_component_labels_are_unique_in_a_structure(setup: Setup, db_session: Session) -> None:
    db_session.execute(
        text(
            "update assessment_components set label = 'CA1'"
            " where structure_id = :id and position = 2"
        ),
        {"id": setup.jss_first_term},
    )

    with violates(db_session, "uq_assessment_components_structure_id_label"):
        run_commit_checks(db_session)


def test_components_can_be_reordered_in_one_go(setup: Setup, db_session: Session) -> None:
    # Positions are checked at save, so swapping CA1 and CA2 works.
    db_session.execute(
        text(
            "update assessment_components set position = 3 - position"
            " where structure_id = :id and position in (1, 2)"
        ),
        {"id": setup.jss_first_term},
    )

    run_commit_checks(db_session)


def test_one_structure_per_level_per_term(setup: Setup, db_session: Session) -> None:
    with violates(db_session, "uq_assessment_structures_school_id_level_term_id"):
        create_structure(db_session, setup.gmc, "junior_secondary", setup.first_term)


def test_a_structure_needs_its_level_switched_on(setup: Setup, db_session: Session) -> None:
    # AT-04.2: BSA has Secondary off, so no Junior Secondary structure.
    with violates(db_session, "assessment_structures_level_is_on"):
        create_structure(db_session, setup.bsa, "junior_secondary", setup.bsa_term)


def test_skill_ratings_levels_have_no_components(setup: Setup, db_session: Session) -> None:
    add_component(
        db_session, setup.bsa, setup.nursery_first_term, 1, Component("Exam", "Exam", 100)
    )

    with violates(db_session, "assessment_structures_ratings_have_no_components"):
        run_commit_checks(db_session)


def test_a_structures_term_is_in_the_same_school(setup: Setup, db_session: Session) -> None:
    with violates(db_session, "fk_assessment_structures_term_id_terms"):
        create_structure(db_session, setup.gmc, "junior_secondary", setup.bsa_term)


# --- locking for the term (AC08.3, AC08.6) -----------------------------------------

LOCKED_CHANGES = {
    "change a maximum": "update assessment_components set max_score = 30 where structure_id = :id"
    " and position = 1",
    "add a component": "insert into assessment_components (school_id, structure_id, position,"
    " name, label, max_score) select school_id, id, 4, 'Test', 'Test', 1"
    " from assessment_structures where id = :id",
    "remove a component": "delete from assessment_components where structure_id = :id"
    " and position = 3",
}


@pytest.mark.parametrize("change", list(LOCKED_CHANGES))
def test_a_locked_structure_keeps_its_components(
    setup: Setup, db_session: Session, change: str
) -> None:
    # AT-07.4: once a score exists for First Term, First Term's structure is fixed.
    lock(db_session, setup.jss_first_term)

    with violates(db_session, "assessment_components_structure_locked"):
        db_session.execute(text(LOCKED_CHANGES[change]), {"id": setup.jss_first_term})


def test_a_locked_level_keeps_its_mode_for_the_term(setup: Setup, db_session: Session) -> None:
    # AC08.6 and AT-30.2: Nursery cannot switch to Scores during First Term.
    lock(db_session, setup.nursery_first_term)

    with violates(db_session, "assessment_structures_locked"):
        db_session.execute(
            text("update assessment_structures set assessment_mode = 'scores' where id = :id"),
            {"id": setup.nursery_first_term},
        )


@pytest.mark.parametrize(
    "statement",
    [
        "update assessment_structures set locked_at = null where id = :id",
        "delete from assessment_structures where id = :id",
    ],
)
def test_a_lock_is_final(setup: Setup, db_session: Session, statement: str) -> None:
    lock(db_session, setup.jss_first_term)

    with violates(db_session, "assessment_structures_locked"):
        db_session.execute(text(statement), {"id": setup.jss_first_term})


def test_changes_wait_for_the_next_term(setup: Setup, db_session: Session) -> None:
    # AC08.3: First Term is locked; Second Term gets the new structure.
    lock(db_session, setup.jss_first_term)

    create_structure(
        db_session,
        setup.gmc,
        "junior_secondary",
        setup.second_term,
        (Component("CA1", "CA1", 30), Component("Exam", "Exam", 70)),
    )
    run_commit_checks(db_session)


# --- rating traits and the 1 to 5 key ----------------------------------------------


def test_default_traits_are_seven_affective_and_six_psychomotor(
    setup: Setup, db_session: Session
) -> None:
    counts = {
        domain: count
        for domain, count in db_session.execute(
            text(
                "select domain, count(*) from rating_traits where school_id = :school"
                " group by domain"
            ),
            {"school": setup.gmc},
        )
    }

    assert counts == {"affective": 7, "psychomotor": 6}


def test_a_trait_belongs_to_affective_or_psychomotor(setup: Setup, db_session: Session) -> None:
    with violates(db_session, "ck_rating_traits_domain_allowed"):
        add_trait(db_session, setup.gmc, "cognitive", "Memory", 1)


def test_a_trait_name_is_unique_in_its_domain(setup: Setup, db_session: Session) -> None:
    add_trait(db_session, setup.gmc, "psychomotor", "Punctuality", 7)  # other domain: fine

    with violates(db_session, "ix_rating_traits_unique_name"):
        add_trait(db_session, setup.gmc, "affective", "PUNCTUALITY", 8)


def test_a_trait_can_be_retired_without_deleting_it(setup: Setup, db_session: Session) -> None:
    db_session.execute(
        text(
            "update rating_traits set is_active = false"
            " where school_id = :school and name = 'Leadership'"
        ),
        {"school": setup.gmc},
    )

    active = db_session.scalar(
        text(
            "select count(*) from rating_traits where school_id = :school"
            " and domain = 'affective' and is_active"
        ),
        {"school": setup.gmc},
    )
    assert active == 6


@pytest.mark.parametrize("value", [0, 6])
def test_the_trait_key_runs_from_1_to_5(setup: Setup, db_session: Session, value: int) -> None:
    with violates(db_session, "ck_trait_scale_points_value_range"):
        db_session.execute(
            text(
                "insert into trait_scale_points (school_id, value, label)"
                " values (:school, :value, 'Test')"
            ),
            {"school": setup.bsa, "value": value},
        )


def test_each_key_value_has_one_label(setup: Setup, db_session: Session) -> None:
    with violates(db_session, "uq_trait_scale_points_school_id_value"):
        db_session.execute(
            text(
                "insert into trait_scale_points (school_id, value, label)"
                " values (:school, 5, 'Outstanding')"
            ),
            {"school": setup.gmc},
        )


# --- pass mark -------------------------------------------------------------------


def test_the_pass_mark_defaults_to_40(setup: Setup, db_session: Session) -> None:
    pass_mark = db_session.scalar(
        text("select pass_mark from school_settings where school_id = :school"),
        {"school": setup.gmc},
    )

    assert pass_mark == DEFAULT_PASS_MARK


@pytest.mark.parametrize("pass_mark", [0, 100])
def test_the_pass_mark_is_1_to_99(setup: Setup, db_session: Session, pass_mark: int) -> None:
    # AT-07.5: "Pass mark must be a whole number from 1 to 99."
    with violates(db_session, "ck_school_settings_pass_mark_range"):
        db_session.execute(
            text("update school_settings set pass_mark = :pass_mark where school_id = :school"),
            {"pass_mark": pass_mark, "school": setup.gmc},
        )


def test_one_settings_row_per_school(setup: Setup, db_session: Session) -> None:
    with violates(db_session, "pk_school_settings"):
        db_session.execute(
            text("insert into school_settings (school_id) values (:id)"), {"id": setup.gmc}
        )


# --- row-level security -----------------------------------------------------------


@pytest.mark.parametrize("table", TABLES)
def test_a_school_sees_only_its_own_set_up(setup: Setup, db_session: Session, table: str) -> None:
    with acting_as(db_session, "app_user", school_id=setup.gmc):
        gmc = db_session.scalar(COUNT[table])
    with acting_as(db_session, "app_user", school_id=setup.bsa):
        bsa = db_session.scalar(COUNT[table])
    total = db_session.scalar(COUNT[table])

    assert gmc >= 1
    assert bsa >= 1
    assert gmc + bsa == total


def test_a_school_sets_its_own_pass_mark(setup: Setup, db_session: Session) -> None:
    with acting_as(db_session, "app_user", school_id=setup.gmc):
        changed = list(
            db_session.scalars(
                text("update school_settings set pass_mark = 50 returning school_id")
            )
        )

    assert changed == [setup.gmc]


@pytest.mark.parametrize(
    "statement",
    [
        "update school_settings set pass_mark = 50 where school_id = :bsa returning school_id",
        "update grade_bands set remark = 'Changed' where school_id = :bsa returning id",
    ],
)
def test_a_school_cannot_change_another_schools_set_up(
    setup: Setup, db_session: Session, statement: str
) -> None:
    with acting_as(db_session, "app_user", school_id=setup.gmc):
        changed = list(db_session.scalars(text(statement), {"bsa": setup.bsa}))

    assert changed == []


def test_school_settings_are_never_deleted(setup: Setup, db_session: Session) -> None:
    with acting_as(db_session, "app_user", school_id=setup.gmc), refused(db_session):
        db_session.execute(text("delete from school_settings"))


@pytest.mark.parametrize("role", ["app_platform", "app_verifier"])
@pytest.mark.parametrize("table", TABLES)
def test_platform_and_verification_roles_cannot_read_set_up(
    setup: Setup, db_session: Session, role: str, table: str
) -> None:
    with acting_as(db_session, role), refused(db_session):
        db_session.execute(COUNT[table])
