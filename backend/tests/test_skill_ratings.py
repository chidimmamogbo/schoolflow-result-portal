"""Skill ratings (BUILD_PROMPT 9.1 item 6a; SPEC F26 rules 1 to 4, F06 rule 3, section 8;
AC26.1, AC26.2; AT-30.1, AT-30.2, AT-31.2, AT-32.1, AT-32.2; D-052, D-142, D-143,
D-144).

Behaviour: a school sets up learning areas for a level that is on (names
unique in the level) with skills under each, assigns them to classes of
that level, and keeps one rating scale with exactly one attention point.
A rating sheet covers one learning area of the arm's class for one term:
every pupil of the arm gets one rating per active skill of the area, each
with its author, and may get one comment of up to 300 characters.
"Teaches all subjects" also covers the class's learning areas, except an
area given to a specialist. Only the assigned teacher submits (assistants
never), and only when every skill is rated. Ratings and comments are locked
once submitted; after a return or a reopen, a changed rating needs a reason.
Rating sheets follow the same workflow, review rules and history as score
sheets. All data is fictional (Bright Stars Academy, Nursery 2).
"""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from schoolflow_api.db import use_context
from schoolflow_api.ratings.defaults import ATTENTION_POINT, LEARNING_AREAS, RATING_SCALE
from tests.db_support import acting_as, refused, run_commit_checks, violates
from tests.factories import (
    add_arm_subject,
    add_assistant,
    add_membership,
    add_reviewer_scope,
    assign_area_teacher,
    assign_area_to_class,
    assign_teacher,
    comment_on_area,
    create_arm,
    create_class,
    create_learning_area,
    create_rating_scale,
    create_rating_sheet,
    create_school,
    create_session,
    create_sheet,
    create_skill,
    create_structure,
    create_student,
    create_subject,
    create_term,
    create_user,
    enrol,
    move_sheet,
    rate,
)

TABLES = (
    "learning_areas",
    "class_learning_areas",
    "skills",
    "rating_scales",
    "rating_scale_points",
    "skill_ratings",
    "area_comments",
)
COUNT: dict[str, TextClause] = {table: text(f"select count(*) from {table}") for table in TABLES}  # noqa: S608


@dataclass(frozen=True)
class Nursery:
    bsa: uuid.UUID
    first_term: uuid.UUID
    second_term: uuid.UUID
    nursery2: uuid.UUID  # the class
    nursery2_arm: uuid.UUID  # its only arm (no arm letter)
    primary4: uuid.UUID
    primary4a: uuid.UUID
    structure: uuid.UUID  # Nursery, First Term, Skill ratings
    areas: dict[str, uuid.UUID]  # the ten default learning areas, by name
    skills: dict[str, uuid.UUID]  # the default skills, by name
    points: dict[str, uuid.UUID]  # the default scale, by code: E, VG, G, F, NI
    amaka: uuid.UUID  # class teacher of Nursery 2, teaches all subjects
    kemi: uuid.UUID  # specialist: Letter work in Nursery 2
    ngozi_ani: uuid.UUID  # class teacher assistant in Nursery 2
    obinna: uuid.UUID  # reviewer, no scope until a test gives one
    chiamaka: uuid.UUID  # head teacher (principal)
    chidera: uuid.UUID  # enrolment in Nursery 2
    hauwa: uuid.UUID  # enrolment in Nursery 2
    kosi: uuid.UUID  # enrolment in Primary 4A
    number_work: uuid.UUID  # rating sheet: Number work, Nursery 2, First Term
    letter_work: uuid.UUID  # rating sheet: Letter work, Nursery 2, First Term


@pytest.fixture
def nursery(db_session: Session) -> Nursery:
    s = db_session
    bsa = create_school(s, code="BSA", name="Bright Stars Academy", school_type="nursery_primary")
    bsa_session = create_session(s, bsa)
    first_term = create_term(s, bsa, bsa_session, 1, is_active=True)
    second_term = create_term(s, bsa, bsa_session, 2)

    nursery2 = create_class(s, bsa, "nursery", "Nursery 2")
    nursery2_arm = create_arm(s, bsa, nursery2, "")
    primary4 = create_class(s, bsa, "primary", "Primary 4")
    primary4a = create_arm(s, bsa, primary4, "A")
    structure = create_structure(s, bsa, "nursery", first_term, (), mode="skill_ratings")

    # AT-30.1: the default learning areas and skills, every area given to Nursery 2.
    areas: dict[str, uuid.UUID] = {}
    skills: dict[str, uuid.UUID] = {}
    for position, (area, area_skills) in enumerate(LEARNING_AREAS.items(), start=1):
        areas[area] = create_learning_area(s, bsa, "nursery", area, position)
        assign_area_to_class(s, bsa, nursery2, areas[area])
        for skill_position, skill in enumerate(area_skills, start=1):
            skills[skill] = create_skill(s, bsa, areas[area], skill, skill_position)
    points = create_rating_scale(s, bsa)

    def member(username: str, full_name: str, role: str, principal: bool = False) -> uuid.UUID:
        user = create_user(s, username=username, full_name=full_name)
        add_membership(s, user, bsa, role, is_primary=principal)
        return user

    amaka = member("amaka.udeh", "Amaka Udeh", "teacher")
    kemi = member("kemi.balogun", "Kemi Balogun", "teacher")
    ngozi_ani = member("ngozi.ani", "Ngozi Ani", "teacher")
    obinna = member("obinna.eze", "Obinna Eze", "reviewer")
    chiamaka = member("chiamaka.nwafor", "Chiamaka Nwafor", "school_admin", principal=True)
    assign_teacher(s, bsa, amaka, nursery2_arm, form_teacher=True, teaches_all_subjects=True)
    assign_area_teacher(s, bsa, kemi, nursery2_arm, areas["Letter work"])
    add_assistant(s, bsa, nursery2_arm, ngozi_ani)

    def pupil(admission_number: str, surname: str, first_name: str, arm: uuid.UUID) -> uuid.UUID:
        student = create_student(s, bsa, admission_number, surname, first_name, gender="female")
        return enrol(s, bsa, student, bsa_session, arm)

    chidera = pupil("BSA/2026/031", "Okeke", "Chidera", nursery2_arm)
    hauwa = pupil("BSA/2026/032", "Sani", "Hauwa", nursery2_arm)
    kosi = pupil("BSA/2026/014", "Obi", "Kosi", primary4a)
    run_commit_checks(s)

    return Nursery(
        bsa,
        first_term,
        second_term,
        nursery2,
        nursery2_arm,
        primary4,
        primary4a,
        structure,
        areas,
        skills,
        points,
        amaka,
        kemi,
        ngozi_ani,
        obinna,
        chiamaka,
        chidera,
        hauwa,
        kosi,
        create_rating_sheet(s, bsa, first_term, nursery2_arm, structure, areas["Number work"]),
        create_rating_sheet(s, bsa, first_term, nursery2_arm, structure, areas["Letter work"]),
    )


def as_user(session: Session, n: Nursery, user: uuid.UUID) -> None:
    use_context(session, school_id=n.bsa, user_id=user)


def rate_all(
    session: Session, n: Nursery, sheet: uuid.UUID, area: str, user: uuid.UUID, code: str = "G"
) -> None:
    """The user rates both Nursery 2 pupils on every default skill of the area."""
    as_user(session, n, user)
    for skill in LEARNING_AREAS[area]:
        for enrolment in (n.chidera, n.hauwa):
            rate(session, n.bsa, sheet, enrolment, n.skills[skill], n.points[code])


def rate_number_work(session: Session, n: Nursery) -> None:
    """Amaka rates Number work (AT-32.2: Hauwa, Counts 1 to 20, Needs improvement)."""
    as_user(session, n, n.amaka)
    for enrolment, counting, shapes in ((n.chidera, "VG", "E"), (n.hauwa, "NI", "G")):
        for skill, code in (("Counts 1 to 20", counting), ("Recognises shapes", shapes)):
            rate(session, n.bsa, n.number_work, enrolment, n.skills[skill], n.points[code])


def submit_number_work(session: Session, n: Nursery) -> None:
    rate_number_work(session, n)
    move_sheet(session, n.number_work, "submitted")


def publish_number_work(session: Session, n: Nursery) -> None:
    """No reviewer covers Nursery 2 here, so the head teacher approves straight away (D-142)."""
    submit_number_work(session, n)
    as_user(session, n, n.chiamaka)
    move_sheet(session, n.number_work, "approved")
    move_sheet(session, n.number_work, "published")


CHANGE_RATING = text(
    "update skill_ratings set point_id = :point, change_reason = :reason"
    " where sheet_id = :sheet and enrolment_id = :enrolment and skill_id = :skill"
)
HAUWAS_COUNTING = text(
    "select p.code, r.change_reason, r.updated_by from skill_ratings r"
    " join rating_scale_points p on p.id = r.point_id"
    " where r.sheet_id = :sheet and r.enrolment_id = :enrolment and r.skill_id = :skill"
)


def change_hauwas_counting(
    session: Session, n: Nursery, code: str, reason: str | None = None
) -> None:
    session.execute(
        CHANGE_RATING,
        {
            "point": n.points[code],
            "reason": reason,
            "sheet": n.number_work,
            "enrolment": n.hauwa,
            "skill": n.skills["Counts 1 to 20"],
        },
    )


def hauwas_counting(session: Session, n: Nursery) -> tuple[str, str | None, uuid.UUID | None]:
    code, reason, updated_by = session.execute(
        HAUWAS_COUNTING,
        {"sheet": n.number_work, "enrolment": n.hauwa, "skill": n.skills["Counts 1 to 20"]},
    ).one()
    return code, reason, updated_by


def status_of(session: Session, sheet: uuid.UUID) -> tuple[str, int]:
    status, revision = session.execute(
        text("select status, revision from result_sheets where id = :id"), {"id": sheet}
    ).one()
    return status, revision


# --- defaults, learning areas and skills (F26 rules 1 and 2) -------------------------


def test_the_defaults_follow_the_spec() -> None:
    # F26 rules 1 and 2 and AT-30.1: ten learning areas, five points best first, NI flags.
    assert list(LEARNING_AREAS) == [
        "Number work",
        "Letter work",
        "Phonics",
        "Rhymes and songs",
        "Pre-science",
        "Handwriting",
        "Creative arts",
        "Social habits",
        "Health habits",
        "Physical development",
    ]
    assert [(point.name, point.code) for point in RATING_SCALE] == [
        ("Excellent", "E"),
        ("Very good", "VG"),
        ("Good", "G"),
        ("Fair", "F"),
        ("Needs improvement", "NI"),
    ]
    assert ATTENTION_POINT == "NI"


def test_area_names_are_unique_per_level(nursery: Nursery, db_session: Session) -> None:
    # "There's already a learning area called {name}." Capitals do not matter.
    with violates(db_session, "ix_learning_areas_unique_name"):
        create_learning_area(db_session, nursery.bsa, "nursery", "number WORK", 11)

    create_learning_area(db_session, nursery.bsa, "primary", "Number work")  # another level


def test_learning_areas_only_for_levels_that_are_on(nursery: Nursery, db_session: Session) -> None:
    # AT-04.2: Bright Stars has Secondary switched off.
    with violates(db_session, "learning_areas_level_is_on"):
        create_learning_area(db_session, nursery.bsa, "junior_secondary", "Number work")


def test_an_area_is_given_only_to_classes_of_its_level(
    nursery: Nursery, db_session: Session
) -> None:
    with violates(db_session, "class_learning_areas_same_level"):
        assign_area_to_class(
            db_session, nursery.bsa, nursery.primary4, nursery.areas["Number work"]
        )


def test_an_area_is_given_to_a_class_once(nursery: Nursery, db_session: Session) -> None:
    with violates(db_session, "uq_class_learning_areas_class_id_learning_area_id"):
        assign_area_to_class(
            db_session, nursery.bsa, nursery.nursery2, nursery.areas["Number work"]
        )


REMOVE_AREA = text(
    "delete from class_learning_areas where class_id = :class and learning_area_id = :area"
)


def test_an_area_in_use_stays_with_the_class(nursery: Nursery, db_session: Session) -> None:
    # Like a subject an arm takes: once the class has a sheet or a teacher for it, it stays.
    assign_area_teacher(
        db_session, nursery.bsa, nursery.kemi, nursery.nursery2_arm, nursery.areas["Phonics"]
    )

    for area in ("Number work", "Phonics"):  # a rating sheet; a specialist teacher
        with violates(db_session, "class_learning_areas_in_use"):
            db_session.execute(
                REMOVE_AREA, {"class": nursery.nursery2, "area": nursery.areas[area]}
            )
    db_session.execute(
        REMOVE_AREA, {"class": nursery.nursery2, "area": nursery.areas["Rhymes and songs"]}
    )


def test_skill_names_are_unique_per_area(nursery: Nursery, db_session: Session) -> None:
    # "{area} already has a skill called {name}."
    with violates(db_session, "ix_skills_unique_name"):
        create_skill(db_session, nursery.bsa, nursery.areas["Number work"], "counts 1 to 20", 3)

    create_skill(db_session, nursery.bsa, nursery.areas["Phonics"], "Counts 1 to 20")


@pytest.mark.parametrize(
    ("statement", "rule"),
    [
        ("update learning_areas set name = ' '", "ck_learning_areas_name_valid"),
        ("update skills set name = ' '", "ck_skills_name_valid"),
        ("update skills set description = ' '", "ck_skills_description_valid"),
        ("update rating_scale_points set name = ' '", "ck_rating_scale_points_name_valid"),
        ("update rating_scale_points set code = 'vg'", "ck_rating_scale_points_code_format"),
        (
            "update rating_scale_points set description = ''",
            "ck_rating_scale_points_description_valid",
        ),
    ],
)
def test_words_and_codes_are_filled_in(
    nursery: Nursery, db_session: Session, statement: str, rule: str
) -> None:
    # "Word is needed." "Code is needed." An empty description is stored as none.
    with violates(db_session, rule):
        db_session.execute(text(statement))


# --- the rating scale (F26 rule 2) ----------------------------------------------------


def test_one_rating_scale_per_school(nursery: Nursery, db_session: Session) -> None:
    with violates(db_session, "uq_rating_scales_school_id"):
        create_rating_scale(db_session, nursery.bsa)


@pytest.mark.parametrize(("code", "flag"), [("F", True), ("NI", False)])
def test_a_scale_has_exactly_one_attention_point(
    nursery: Nursery, db_session: Session, code: str, flag: bool
) -> None:
    # Two attention points, or none, cannot be saved.
    db_session.execute(
        text("update rating_scale_points set is_attention = :flag where id = :id"),
        {"flag": flag, "id": nursery.points[code]},
    )

    with violates(db_session, "rating_scales_one_attention_point"):
        run_commit_checks(db_session)


def test_the_attention_point_moves_in_one_save(nursery: Nursery, db_session: Session) -> None:
    # "Flag in Students needing attention at or below": Fair instead of Needs improvement.
    db_session.execute(
        text("update rating_scale_points set is_attention = (code = 'F') where school_id = :id"),
        {"id": nursery.bsa},
    )
    run_commit_checks(db_session)

    attention = db_session.scalar(
        text("select code from rating_scale_points where school_id = :id and is_attention"),
        {"id": nursery.bsa},
    )
    assert attention == "F"


def test_points_can_be_reordered_and_recoded_in_one_save(
    nursery: Nursery, db_session: Session
) -> None:
    # Positions and codes are checked at save, so two points can swap both in one go.
    db_session.execute(
        text(
            "update rating_scale_points set position = 7 - position,"
            " code = case code when 'G' then 'F' else 'G' end where id in (:good, :fair)"
        ),
        {"good": nursery.points["G"], "fair": nursery.points["F"]},
    )

    run_commit_checks(db_session)


def test_rating_codes_are_unique_in_a_scale(nursery: Nursery, db_session: Session) -> None:
    # "Code VG is already used."
    db_session.execute(
        text("update rating_scale_points set code = 'VG' where id = :id"),
        {"id": nursery.points["G"]},
    )

    with violates(db_session, "uq_rating_scale_points_scale_id_code"):
        run_commit_checks(db_session)


# --- who rates which area (F26 rule 3, F06) -----------------------------------------

ADD_ASSIGNMENT = text(
    "insert into teacher_assignments (school_id, teacher_id, arm_id, subject_id,"
    " learning_area_id, is_form_teacher) values (:school, :teacher, :arm, :subject, :area,"
    " :form_teacher)"
)


@pytest.mark.parametrize("other_kind", ["subject", "form_teacher"])
def test_an_assignment_row_is_exactly_one_kind(
    nursery: Nursery, db_session: Session, other_kind: str
) -> None:
    # A learning area row names no subject and is not the form teacher row.
    mathematics = create_subject(db_session, nursery.bsa, "Mathematics")
    add_arm_subject(db_session, nursery.bsa, nursery.nursery2_arm, mathematics)

    with violates(db_session, "ck_teacher_assignments_one_kind"):
        db_session.execute(
            ADD_ASSIGNMENT,
            {
                "school": nursery.bsa,
                "teacher": nursery.kemi,
                "arm": nursery.nursery2_arm,
                "subject": mathematics if other_kind == "subject" else None,
                "area": nursery.areas["Phonics"],
                "form_teacher": other_kind == "form_teacher",
            },
        )


def test_one_teacher_per_area_per_arm(nursery: Nursery, db_session: Session) -> None:
    with violates(db_session, "ix_teacher_assignments_one_teacher_per_area"):
        assign_area_teacher(
            db_session,
            nursery.bsa,
            nursery.ngozi_ani,
            nursery.nursery2_arm,
            nursery.areas["Letter work"],
        )


def test_an_area_teacher_needs_the_area_in_the_class(nursery: Nursery, db_session: Session) -> None:
    story_time = create_learning_area(db_session, nursery.bsa, "nursery", "Story time", 11)

    with violates(db_session, "teacher_assignments_area_in_class"):
        assign_area_teacher(db_session, nursery.bsa, nursery.kemi, nursery.nursery2_arm, story_time)


AREAS_OF = text(
    "select la.name, ts.source from teacher_subjects ts"
    " join learning_areas la on la.id = ts.learning_area_id"
    " where ts.teacher_id = :teacher and ts.arm_id = :arm"
)


def areas_of(session: Session, n: Nursery, teacher: uuid.UUID) -> dict[str, str]:
    rows = session.execute(AREAS_OF, {"teacher": teacher, "arm": n.nursery2_arm})
    return {name: source for name, source in rows}


def test_teaches_all_covers_the_class_areas_except_a_specialists(
    nursery: Nursery, db_session: Session
) -> None:
    # F26 rule 3 and AT-31.1: Amaka has every Nursery 2 area, including one added later,
    # except Letter work, which Kemi teaches. Ngozi Ani assists and has none.
    story_time = create_learning_area(db_session, nursery.bsa, "nursery", "Story time", 11)
    assign_area_to_class(db_session, nursery.bsa, nursery.nursery2, story_time)

    amaka = areas_of(db_session, nursery, nursery.amaka)

    assert set(amaka) == (set(LEARNING_AREAS) - {"Letter work"}) | {"Story time"}
    assert set(amaka.values()) == {"teaches_all_subjects"}
    assert areas_of(db_session, nursery, nursery.kemi) == {"Letter work": "assigned"}
    assert areas_of(db_session, nursery, nursery.ngozi_ani) == {}


# --- rating sheets (F26 rule 3) ------------------------------------------------------


def test_one_rating_sheet_per_area_per_arm_per_term(nursery: Nursery, db_session: Session) -> None:
    with violates(db_session, "ix_result_sheets_one_rating_sheet"):
        create_rating_sheet(
            db_session,
            nursery.bsa,
            nursery.first_term,
            nursery.nursery2_arm,
            nursery.structure,
            nursery.areas["Number work"],
        )


def test_a_rating_sheet_is_for_an_area_of_the_arms_class(
    nursery: Nursery, db_session: Session
) -> None:
    story_time = create_learning_area(db_session, nursery.bsa, "nursery", "Story time", 11)

    with violates(db_session, "result_sheets_area_in_class"):
        create_rating_sheet(
            db_session,
            nursery.bsa,
            nursery.first_term,
            nursery.nursery2_arm,
            nursery.structure,
            story_time,
        )


def test_a_rating_sheet_has_no_score_columns(nursery: Nursery, db_session: Session) -> None:
    # AC26.1: Nursery on Scores for Second Term cannot drive a rating sheet.
    scores = create_structure(db_session, nursery.bsa, "nursery", nursery.second_term)

    with violates(db_session, "result_sheets_structure_matches"):
        create_rating_sheet(
            db_session,
            nursery.bsa,
            nursery.second_term,
            nursery.nursery2_arm,
            scores,
            nursery.areas["Number work"],
        )


# --- ratings ---------------------------------------------------------------------------


def test_a_teacher_rates_each_skill_with_their_name_on_it(
    nursery: Nursery, db_session: Session
) -> None:
    # AC26.1 and AT-32.2: one rating per pupil per skill; Hauwa gets Needs improvement.
    rate_number_work(db_session, nursery)

    ratings, by_amaka = db_session.execute(
        text(
            "select count(*), count(*) filter (where entered_by = :amaka) from skill_ratings"
            " where sheet_id = :sheet"
        ),
        {"amaka": nursery.amaka, "sheet": nursery.number_work},
    ).one()
    assert (ratings, by_amaka) == (4, 4)
    assert hauwas_counting(db_session, nursery) == ("NI", None, None)


def test_the_first_rating_locks_the_level_for_the_term(
    nursery: Nursery, db_session: Session
) -> None:
    # AT-30.2: with ratings in First Term, Nursery switches to Scores from Second Term only.
    rate_number_work(db_session, nursery)

    with violates(db_session, "assessment_structures_locked"):
        db_session.execute(
            text("update assessment_structures set assessment_mode = 'scores' where id = :id"),
            {"id": nursery.structure},
        )


def test_an_assistant_enters_ratings_with_her_name(nursery: Nursery, db_session: Session) -> None:
    # F06 rule 3 and AT-31.2: Ngozi Ani's ratings save with her name in the audit trail.
    as_user(db_session, nursery, nursery.ngozi_ani)
    rate(
        db_session,
        nursery.bsa,
        nursery.number_work,
        nursery.chidera,
        nursery.skills["Counts 1 to 20"],
        nursery.points["G"],
    )

    author = db_session.scalar(
        text("select entered_by from skill_ratings where sheet_id = :id"),
        {"id": nursery.number_work},
    )
    assert author == nursery.ngozi_ani


@pytest.mark.parametrize("skill", ["Recognises letters A to Z", "Counts 1 to 20"])
def test_a_rating_is_for_an_active_skill_of_the_sheets_area(
    nursery: Nursery, db_session: Session, skill: str
) -> None:
    # A Letter work skill on the Number work sheet; or Counts 1 to 20 once retired.
    db_session.execute(
        text("update skills set is_active = false where id = :id"),
        {"id": nursery.skills["Counts 1 to 20"]},
    )
    as_user(db_session, nursery, nursery.amaka)

    with violates(db_session, "skill_ratings_skill_in_area"):
        rate(
            db_session,
            nursery.bsa,
            nursery.number_work,
            nursery.chidera,
            nursery.skills[skill],
            nursery.points["G"],
        )


def test_only_pupils_of_the_arm_are_rated(nursery: Nursery, db_session: Session) -> None:
    # Kosi Obi is in Primary 4A, not Nursery 2.
    as_user(db_session, nursery, nursery.amaka)

    with violates(db_session, "skill_ratings_pupil_in_arm"):
        rate(
            db_session,
            nursery.bsa,
            nursery.number_work,
            nursery.kosi,
            nursery.skills["Counts 1 to 20"],
            nursery.points["G"],
        )


def test_one_rating_per_pupil_per_skill(nursery: Nursery, db_session: Session) -> None:
    rate_number_work(db_session, nursery)

    with violates(db_session, "uq_skill_ratings_sheet_id_enrolment_id_skill_id"):
        rate(
            db_session,
            nursery.bsa,
            nursery.number_work,
            nursery.hauwa,
            nursery.skills["Counts 1 to 20"],
            nursery.points["G"],
        )


def test_a_rating_uses_the_schools_own_scale(nursery: Nursery, db_session: Session) -> None:
    rcs = create_school(
        db_session, code="RCS", name="Royal Crest Schools", school_type="all_levels"
    )
    rcs_points = create_rating_scale(db_session, rcs)
    as_user(db_session, nursery, nursery.amaka)

    with violates(db_session, "fk_skill_ratings_point_id_rating_scale_points"):
        rate(
            db_session,
            nursery.bsa,
            nursery.number_work,
            nursery.chidera,
            nursery.skills["Counts 1 to 20"],
            rcs_points["E"],
        )


def test_every_rating_has_an_author(nursery: Nursery, db_session: Session) -> None:
    use_context(db_session, school_id=nursery.bsa)  # nobody signed in

    with violates(db_session, "skill_ratings_need_an_author"):
        rate(
            db_session,
            nursery.bsa,
            nursery.number_work,
            nursery.chidera,
            nursery.skills["Counts 1 to 20"],
            nursery.points["G"],
        )


def test_first_draft_changes_need_no_reason(nursery: Nursery, db_session: Session) -> None:
    # D-143: Amaka fixes her own clicks freely before the first submission.
    rate_number_work(db_session, nursery)

    change_hauwas_counting(db_session, nursery, "F")

    assert hauwas_counting(db_session, nursery) == ("F", None, nursery.amaka)


# --- submitting (AC26.2, F06 rule 3) -------------------------------------------------


def test_submitting_needs_every_skill_rated(nursery: Nursery, db_session: Session) -> None:
    # AT-32.1 and AC26.2: Hauwa has no rating for Counts 1 to 20.
    as_user(db_session, nursery, nursery.amaka)
    for skill, code in (("Counts 1 to 20", "VG"), ("Recognises shapes", "E")):
        rate(
            db_session,
            nursery.bsa,
            nursery.number_work,
            nursery.chidera,
            nursery.skills[skill],
            nursery.points[code],
        )
    rate(
        db_session,
        nursery.bsa,
        nursery.number_work,
        nursery.hauwa,
        nursery.skills["Recognises shapes"],
        nursery.points["G"],
    )

    with violates(db_session, "result_sheets_ratings_missing"):
        move_sheet(db_session, nursery.number_work, "submitted")


def test_a_retired_skill_is_not_needed_to_submit(nursery: Nursery, db_session: Session) -> None:
    db_session.execute(
        text("update skills set is_active = false where id = :id"),
        {"id": nursery.skills["Recognises shapes"]},
    )
    as_user(db_session, nursery, nursery.amaka)
    for enrolment in (nursery.chidera, nursery.hauwa):
        rate(
            db_session,
            nursery.bsa,
            nursery.number_work,
            enrolment,
            nursery.skills["Counts 1 to 20"],
            nursery.points["G"],
        )

    move_sheet(db_session, nursery.number_work, "submitted")

    assert status_of(db_session, nursery.number_work) == ("submitted", 1)


@pytest.mark.parametrize(
    ("who", "area"),
    [("ngozi_ani", "Number work"), ("kemi", "Number work"), ("amaka", "Letter work")],
)
def test_only_the_assigned_teacher_submits_a_rating_sheet(
    nursery: Nursery, db_session: Session, who: str, area: str
) -> None:
    # Ngozi Ani assists and never submits (AT-31.2); Kemi teaches Letter work only; Letter
    # work is Kemi's, so Amaka's Teaches all subjects does not cover it.
    sheet = nursery.number_work if area == "Number work" else nursery.letter_work
    rate_all(db_session, nursery, sheet, area, nursery.amaka)
    as_user(db_session, nursery, getattr(nursery, who))

    with violates(db_session, "result_sheets_submitted_by_assigned_teacher"):
        move_sheet(db_session, sheet, "submitted")


def test_a_specialist_submits_their_own_area(nursery: Nursery, db_session: Session) -> None:
    rate_all(db_session, nursery, nursery.letter_work, "Letter work", nursery.kemi)

    move_sheet(db_session, nursery.letter_work, "submitted")

    assert status_of(db_session, nursery.letter_work) == ("submitted", 1)


# --- locks and reasons (SPEC section 8, D-143) ----------------------------------------


def test_ratings_are_locked_once_submitted(nursery: Nursery, db_session: Session) -> None:
    submit_number_work(db_session, nursery)

    with violates(db_session, "skill_ratings_sheet_is_locked"):
        change_hauwas_counting(db_session, nursery, "F", "Second look")
    with violates(db_session, "skill_ratings_sheet_is_locked"):
        db_session.execute(
            text("delete from skill_ratings where sheet_id = :id"), {"id": nursery.number_work}
        )


def return_number_work(session: Session, n: Nursery) -> None:
    submit_number_work(session, n)
    as_user(session, n, n.obinna)
    move_sheet(
        session, n.number_work, "returned_for_correction", comment="Please check Hauwa's counting."
    )
    as_user(session, n, n.amaka)


def test_rating_changes_after_a_return_need_a_reason(nursery: Nursery, db_session: Session) -> None:
    # D-143: Amaka changes Hauwa's rating after the return only with a reason.
    return_number_work(db_session, nursery)

    with violates(db_session, "skill_ratings_change_needs_reason"):
        change_hauwas_counting(db_session, nursery, "F")
    change_hauwas_counting(db_session, nursery, "F", "Counted to 20 on a second try")

    assert hauwas_counting(db_session, nursery) == (
        "F",
        "Counted to 20 on a second try",
        nursery.amaka,
    )


def test_ratings_are_removed_only_in_the_first_draft(nursery: Nursery, db_session: Session) -> None:
    return_number_work(db_session, nursery)

    with violates(db_session, "skill_ratings_removed_only_in_first_draft"):
        db_session.execute(
            text("delete from skill_ratings where sheet_id = :id"), {"id": nursery.number_work}
        )


# --- comments on a learning area (F26 rule 3) -----------------------------------------


def test_an_area_comment_is_optional_and_short(nursery: Nursery, db_session: Session) -> None:
    # "Comment on Number work (optional)": one per pupil, up to 300 characters.
    as_user(db_session, nursery, nursery.amaka)
    comment_on_area(
        db_session, nursery.bsa, nursery.number_work, nursery.chidera, "Counts with confidence."
    )

    with violates(db_session, "uq_area_comments_sheet_id_enrolment_id"):
        comment_on_area(
            db_session, nursery.bsa, nursery.number_work, nursery.chidera, "A second comment."
        )
    for comment in (" ", "x" * 301):
        with violates(db_session, "ck_area_comments_comment_valid"):
            comment_on_area(db_session, nursery.bsa, nursery.number_work, nursery.hauwa, comment)


def test_area_comments_are_locked_once_submitted(nursery: Nursery, db_session: Session) -> None:
    as_user(db_session, nursery, nursery.amaka)
    comment_on_area(
        db_session, nursery.bsa, nursery.number_work, nursery.chidera, "Counts with confidence."
    )
    submit_number_work(db_session, nursery)

    with violates(db_session, "area_comments_sheet_is_locked"):
        comment_on_area(
            db_session, nursery.bsa, nursery.number_work, nursery.hauwa, "A late comment."
        )
    with violates(db_session, "area_comments_sheet_is_locked"):
        db_session.execute(
            text("update area_comments set comment = 'Changed' where sheet_id = :id"),
            {"id": nursery.number_work},
        )
    with violates(db_session, "area_comments_sheet_is_locked"):
        db_session.execute(
            text("delete from area_comments where sheet_id = :id"), {"id": nursery.number_work}
        )


def test_an_area_comment_is_for_a_pupil_of_the_arm(nursery: Nursery, db_session: Session) -> None:
    as_user(db_session, nursery, nursery.amaka)

    with violates(db_session, "area_comments_pupil_in_arm"):
        comment_on_area(db_session, nursery.bsa, nursery.number_work, nursery.kosi, "Not here.")


def test_area_comments_go_only_on_rating_sheets(nursery: Nursery, db_session: Session) -> None:
    # Primary 4A's Mathematics sheet has scores, not learning areas.
    mathematics = create_subject(db_session, nursery.bsa, "Mathematics")
    add_arm_subject(db_session, nursery.bsa, nursery.primary4a, mathematics)
    primary = create_structure(db_session, nursery.bsa, "primary", nursery.first_term)
    maths_4a = create_sheet(
        db_session, nursery.bsa, nursery.first_term, nursery.primary4a, primary, mathematics
    )
    as_user(db_session, nursery, nursery.chiamaka)

    with violates(db_session, "area_comments_on_a_rating_sheet"):
        comment_on_area(db_session, nursery.bsa, maths_4a, nursery.kosi, "Good work.")


def test_every_area_comment_has_an_author(nursery: Nursery, db_session: Session) -> None:
    use_context(db_session, school_id=nursery.bsa)  # nobody signed in

    with violates(db_session, "area_comments_need_an_author"):
        comment_on_area(
            db_session, nursery.bsa, nursery.number_work, nursery.chidera, "Counts well."
        )


# --- the same workflow as score sheets (F26 rule 4, SPEC section 8) -------------------


def test_a_covered_rating_sheet_must_be_reviewed(nursery: Nursery, db_session: Session) -> None:
    # D-142: Obinna reviews Nursery 2, so the head teacher cannot skip the review.
    add_reviewer_scope(db_session, nursery.bsa, nursery.obinna, class_id=nursery.nursery2)
    submit_number_work(db_session, nursery)
    as_user(db_session, nursery, nursery.chiamaka)

    with violates(db_session, "result_sheets_needs_review"):
        move_sheet(db_session, nursery.number_work, "approved")


def test_an_uncovered_rating_sheet_can_be_approved_straight_away(
    nursery: Nursery, db_session: Session
) -> None:
    # D-142: Obinna's scope is Mathematics in Primary 4, which covers no rating sheet.
    mathematics = create_subject(db_session, nursery.bsa, "Mathematics")
    add_reviewer_scope(
        db_session, nursery.bsa, nursery.obinna, subject_id=mathematics, class_id=nursery.primary4
    )
    submit_number_work(db_session, nursery)
    as_user(db_session, nursery, nursery.chiamaka)

    move_sheet(db_session, nursery.number_work, "approved")

    assert status_of(db_session, nursery.number_work) == ("approved", 1)


def test_a_head_who_teaches_an_area_never_approves_it(
    nursery: Nursery, db_session: Session
) -> None:
    # D-052 and D-144: Chiamaka teaches Rhymes and songs, submits it and cannot approve it.
    area = nursery.areas["Rhymes and songs"]
    assign_area_teacher(db_session, nursery.bsa, nursery.chiamaka, nursery.nursery2_arm, area)
    rhymes = create_rating_sheet(
        db_session, nursery.bsa, nursery.first_term, nursery.nursery2_arm, nursery.structure, area
    )
    rate_all(db_session, nursery, rhymes, "Rhymes and songs", nursery.chiamaka)
    move_sheet(db_session, rhymes, "submitted")

    with violates(db_session, "result_sheets_separation_of_duties"):
        move_sheet(db_session, rhymes, "approved")


def test_a_rating_sheet_runs_the_whole_workflow(nursery: Nursery, db_session: Session) -> None:
    # F26 rule 4: return, correction with a reason, review, approval, publication.
    add_reviewer_scope(db_session, nursery.bsa, nursery.obinna, class_id=nursery.nursery2)
    return_number_work(db_session, nursery)
    change_hauwas_counting(db_session, nursery, "F", "Counted to 20 on a second try")
    move_sheet(db_session, nursery.number_work, "resubmitted")
    as_user(db_session, nursery, nursery.obinna)
    move_sheet(db_session, nursery.number_work, "reviewed")
    as_user(db_session, nursery, nursery.chiamaka)
    move_sheet(db_session, nursery.number_work, "approved")
    move_sheet(db_session, nursery.number_work, "published")

    steps = sorted(
        db_session.scalars(
            text("select to_status from approval_actions where sheet_id = :id"),
            {"id": nursery.number_work},
        )
    )
    assert steps == sorted(
        [
            "submitted",
            "returned_for_correction",
            "resubmitted",
            "reviewed",
            "approved",
            "published",
        ]
    )
    assert status_of(db_session, nursery.number_work) == ("published", 1)


def test_published_ratings_and_comments_never_change(nursery: Nursery, db_session: Session) -> None:
    # AC11.1 for rating sheets: the database refuses, whoever asks.
    as_user(db_session, nursery, nursery.amaka)
    comment_on_area(
        db_session, nursery.bsa, nursery.number_work, nursery.hauwa, "Keeps trying with numbers."
    )
    publish_number_work(db_session, nursery)

    with violates(db_session, "skill_ratings_sheet_is_locked"):
        change_hauwas_counting(db_session, nursery, "F", "Late correction")
    with violates(db_session, "area_comments_sheet_is_locked"):
        db_session.execute(
            text("update area_comments set comment = 'Changed' where sheet_id = :id"),
            {"id": nursery.number_work},
        )


def test_a_reopened_rating_sheet_needs_reasons_for_changes(
    nursery: Nursery, db_session: Session
) -> None:
    # AT-23.1 and D-143 for rating sheets: revision 2 opens with a reason.
    publish_number_work(db_session, nursery)
    move_sheet(
        db_session, nursery.number_work, "draft", comment="Hauwa was assessed again", reopen=True
    )
    as_user(db_session, nursery, nursery.amaka)

    with violates(db_session, "skill_ratings_change_needs_reason"):
        change_hauwas_counting(db_session, nursery, "F")
    change_hauwas_counting(db_session, nursery, "F", "Hauwa was assessed again")

    assert status_of(db_session, nursery.number_work) == ("draft", 2)


# --- row-level security and grants ---------------------------------------------------


def rate_and_comment(session: Session, n: Nursery) -> None:
    rate_number_work(session, n)
    comment_on_area(session, n.bsa, n.number_work, n.chidera, "Counts with confidence.")


def test_school_users_see_their_skill_records(nursery: Nursery, db_session: Session) -> None:
    rate_and_comment(db_session, nursery)

    with acting_as(db_session, "app_user", school_id=nursery.bsa):
        counts = [db_session.scalar(COUNT[table]) for table in TABLES]

    assert all(count >= 1 for count in counts)


@pytest.mark.parametrize("table", TABLES)
def test_another_school_sees_none_of_these(
    nursery: Nursery, db_session: Session, table: str
) -> None:
    rate_and_comment(db_session, nursery)
    gmc = create_school(db_session, code="GMC", name="Greenfield Model College")

    with acting_as(db_session, "app_user", school_id=gmc):
        assert db_session.scalar(COUNT[table]) == 0


@pytest.mark.parametrize(
    "statement",
    [
        "update skill_ratings set entered_by = :user",
        "update area_comments set entered_by = :user",
        "update skills set learning_area_id = :area",
        "update learning_areas set level = 'primary'",
        "update class_learning_areas set class_id = :class",
        "delete from rating_scales",
    ],
)
def test_the_app_changes_only_what_it_may(
    nursery: Nursery, db_session: Session, statement: str
) -> None:
    # Authors come from the signed-in user; skills, areas and links never move.
    rate_and_comment(db_session, nursery)

    with (
        acting_as(db_session, "app_user", school_id=nursery.bsa, user_id=nursery.chiamaka),
        refused(db_session),
    ):
        db_session.execute(
            text(statement),
            {
                "user": nursery.chiamaka,
                "area": nursery.areas["Phonics"],
                "class": nursery.primary4,
            },
        )


@pytest.mark.parametrize("role", ["app_platform", "app_verifier"])
@pytest.mark.parametrize("table", TABLES)
def test_platform_and_verification_roles_cannot_read_ratings(
    nursery: Nursery, db_session: Session, role: str, table: str
) -> None:
    # D-051: the platform never reads pupils' results.
    with acting_as(db_session, role), refused(db_session):
        db_session.execute(COUNT[table])
