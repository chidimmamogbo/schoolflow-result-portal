"""Form teacher class sections (BUILD_PROMPT 9.1 item 6b; SPEC F22, F10, section 8;
AC22.3, AC22.4; AT-15.3 to AT-15.5; D-146, D-148; approved CHANGE "Rating traits get a
same-school key").

Behaviour: each arm has one set of class sections per term. Times school
opened is set once for the class (1 to 366), and a pupil's times present
never exceeds it. Each pupil of the arm has one term entry: the form
teacher's comment and the head's comment (up to 300 characters each), times
present, and one rating per active trait on the school's 1 to 5 key, each
with its author. Assistants enter, but only the form teacher submits; a
school admin returns the sections with a comment. Teacher entries lock while
submitted; the head's comment can be written until publication; everything
locks once published; a reopen needs a reason and starts the next revision.
Every move is kept in a history the app cannot edit. All data is fictional.
"""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from app.db.session import use_context
from app.src.grading.defaults import AFFECTIVE_TRAITS, PSYCHOMOTOR_TRAITS
from app.tests.db_support import acting_as, refused, violates
from app.tests.factories import (
    add_assistant,
    add_membership,
    add_trait,
    add_trait_key,
    assign_teacher,
    create_arm,
    create_class,
    create_class_section,
    create_school,
    create_session,
    create_student,
    create_term,
    create_user,
    enrol,
    move_section,
    rate_trait,
    write_term_entry,
)

TABLES = (
    "class_report_sections",
    "class_section_actions",
    "student_term_entries",
    "student_trait_ratings",
)
COUNT: dict[str, TextClause] = {table: text(f"select count(*) from {table}") for table in TABLES}  # noqa: S608


@dataclass(frozen=True)
class FormClass:
    gmc: uuid.UUID
    first_term: uuid.UUID
    jss1a: uuid.UUID
    section: uuid.UUID  # JSS 1A, First Term
    traits: dict[str, uuid.UUID]  # the default affective and psychomotor traits, by name
    tunde: uuid.UUID  # form teacher of JSS 1A
    grace: uuid.UUID  # teacher, not a form teacher
    bola: uuid.UUID  # class teacher assistant in JSS 1A
    ngozi: uuid.UUID  # principal
    chukwudi: uuid.UUID  # additional school admin
    chukwuemeka: uuid.UUID  # enrolment in JSS 1A
    musa: uuid.UUID  # enrolment in JSS 1A
    tobi: uuid.UUID  # enrolment in JSS 1B


@pytest.fixture
def form_class(db_session: Session) -> FormClass:
    s = db_session
    gmc = create_school(s, code="GMC", name="Greenfield Model College")
    gmc_session = create_session(s, gmc)
    first_term = create_term(s, gmc, gmc_session, 1, is_active=True)
    jss1 = create_class(s, gmc, "junior_secondary", "JSS 1")
    jss1a, jss1b = create_arm(s, gmc, jss1, "A"), create_arm(s, gmc, jss1, "B")

    traits: dict[str, uuid.UUID] = {}
    for domain, names in (("affective", AFFECTIVE_TRAITS), ("psychomotor", PSYCHOMOTOR_TRAITS)):
        for position, name in enumerate(names, start=1):
            traits[name] = add_trait(s, gmc, domain, name, position)
    add_trait_key(s, gmc)

    def member(username: str, full_name: str, role: str, principal: bool = False) -> uuid.UUID:
        user = create_user(s, username=username, full_name=full_name)
        add_membership(s, user, gmc, role, is_primary=principal)
        return user

    tunde = member("tunde.adebayo", "Tunde Adebayo", "teacher")
    grace = member("grace.etim", "Grace Etim", "teacher")
    bola = member("bola.ige", "Bola Ige", "teacher")
    ngozi = member("ngozi.okeke", "Ngozi Okeke", "school_admin", principal=True)
    chukwudi = member("chukwudi.eze", "Chukwudi Eze", "school_admin")
    assign_teacher(s, gmc, tunde, jss1a, form_teacher=True)
    add_assistant(s, gmc, jss1a, bola)

    def pupil(admission_number: str, surname: str, first_name: str, arm: uuid.UUID) -> uuid.UUID:
        student = create_student(s, gmc, admission_number, surname, first_name)
        return enrol(s, gmc, student, gmc_session, arm)

    return FormClass(
        gmc,
        first_term,
        jss1a,
        create_class_section(s, gmc, first_term, jss1a),
        traits,
        tunde,
        grace,
        bola,
        ngozi,
        chukwudi,
        pupil("GMC/2026/014", "Obi", "Chukwuemeka", jss1a),
        pupil("GMC/2026/015", "Ibrahim", "Musa", jss1a),
        pupil("GMC/2026/031", "Lawal", "Tobi", jss1b),
    )


def as_user(session: Session, f: FormClass, user: uuid.UUID) -> None:
    use_context(session, school_id=f.gmc, user_id=user)


SET_TIMES_OPENED = text(
    "update class_report_sections set times_school_opened = :opened where id = :id"
)
UPDATE_COMMENT = text(
    "update student_term_entries set form_teacher_comment = :comment where id = :id"
)
UPDATE_HEAD_COMMENT = text("update student_term_entries set head_comment = :comment where id = :id")
UPDATE_PRESENT = text("update student_term_entries set times_present = :present where id = :id")


def fill_chukwuemeka(session: Session, f: FormClass) -> uuid.UUID:
    """AT-15.3: Tunde's entry for Chukwuemeka Obi; school opened 60 times, he was present 57."""
    as_user(session, f, f.tunde)
    session.execute(SET_TIMES_OPENED, {"opened": 60, "id": f.section})
    entry = write_term_entry(
        session,
        f.gmc,
        f.section,
        f.chukwuemeka,
        comment="A focused and respectful student. Keep it up in Mathematics.",
        times_present=57,
    )
    for trait, value in (
        ("Punctuality", 5),
        ("Neatness", 4),
        ("Politeness", 5),
        ("Handwriting", 4),
        ("Games and sports", 3),
    ):
        rate_trait(session, f.gmc, entry, f.traits[trait], value)
    return entry


def submit_sections(session: Session, f: FormClass) -> uuid.UUID:
    entry = fill_chukwuemeka(session, f)
    move_section(session, f.section, "submitted")
    return entry


def publish_sections(session: Session, f: FormClass) -> uuid.UUID:
    """The principal publishes JSS 1A for First Term (the sections go with the class)."""
    entry = submit_sections(session, f)
    as_user(session, f, f.ngozi)
    move_section(session, f.section, "published")
    return entry


def status_of(session: Session, section: uuid.UUID) -> tuple[str, int]:
    status, revision = session.execute(
        text("select status, revision from class_report_sections where id = :id"), {"id": section}
    ).one()
    return status, revision


# --- class sections and attendance (F22 rules 5 and 9) -------------------------------


def test_new_sections_are_open_at_revision_1(form_class: FormClass, db_session: Session) -> None:
    assert status_of(db_session, form_class.section) == ("open", 1)


def test_one_set_of_sections_per_arm_per_term(form_class: FormClass, db_session: Session) -> None:
    with violates(db_session, "uq_class_report_sections_term_id_arm_id"):
        create_class_section(db_session, form_class.gmc, form_class.first_term, form_class.jss1a)


@pytest.mark.parametrize("opened", [0, 367])
def test_times_school_opened_is_1_to_366(
    form_class: FormClass, db_session: Session, opened: int
) -> None:
    as_user(db_session, form_class, form_class.tunde)

    with violates(db_session, "ck_class_report_sections_times_school_opened_range"):
        db_session.execute(SET_TIMES_OPENED, {"opened": opened, "id": form_class.section})


def test_times_present_never_exceeds_times_opened(
    form_class: FormClass, db_session: Session
) -> None:
    # AC22.4 and AT-15.4: checked from both sides (60 opened, 57 present).
    entry = fill_chukwuemeka(db_session, form_class)

    with violates(db_session, "student_term_entries_present_within_opened"):
        db_session.execute(UPDATE_PRESENT, {"present": 61, "id": entry})
    with violates(db_session, "class_report_sections_opened_covers_present"):
        db_session.execute(SET_TIMES_OPENED, {"opened": 56, "id": form_class.section})


# --- pupils' term entries (F22 rules 3 to 5 and 8) -----------------------------------


def test_the_form_teacher_fills_a_pupils_entry(form_class: FormClass, db_session: Session) -> None:
    # AT-15.3 and AC22.3: a comment, five ratings, 60 opened and 57 present (3 absent).
    entry = fill_chukwuemeka(db_session, form_class)

    present, absent, author, ratings = db_session.execute(
        text(
            "select e.times_present, s.times_school_opened - e.times_present, e.entered_by,"
            " (select count(*) from student_trait_ratings r where r.entry_id = e.id)"
            " from student_term_entries e join class_report_sections s on s.id = e.section_id"
            " where e.id = :id"
        ),
        {"id": entry},
    ).one()
    assert (present, absent, author, ratings) == (57, 3, form_class.tunde, 5)


@pytest.mark.parametrize(
    ("statement", "rule"),
    [
        (UPDATE_COMMENT, "ck_student_term_entries_form_teacher_comment_valid"),
        (UPDATE_HEAD_COMMENT, "ck_student_term_entries_head_comment_valid"),
    ],
)
def test_comments_are_up_to_300_characters(
    form_class: FormClass, db_session: Session, statement: TextClause, rule: str
) -> None:
    # AT-15.4: a 301-character comment is refused, and so is a blank one (it is stored as none).
    entry = fill_chukwuemeka(db_session, form_class)

    for comment in ("x" * 301, " "):
        with violates(db_session, rule):
            db_session.execute(statement, {"comment": comment, "id": entry})


@pytest.mark.parametrize("value", [0, 6])
def test_a_trait_rating_is_on_the_schools_1_to_5_key(
    form_class: FormClass, db_session: Session, value: int
) -> None:
    # AT-15.4: a rating of 6 is refused.
    entry = fill_chukwuemeka(db_session, form_class)

    with violates(db_session, "fk_student_trait_ratings_school_id_trait_scale_points"):
        rate_trait(db_session, form_class.gmc, entry, form_class.traits["Honesty"], value)


def test_one_entry_per_pupil_and_one_rating_per_trait(
    form_class: FormClass, db_session: Session
) -> None:
    entry = fill_chukwuemeka(db_session, form_class)

    with violates(db_session, "uq_student_term_entries_section_id_enrolment_id"):
        write_term_entry(db_session, form_class.gmc, form_class.section, form_class.chukwuemeka)
    with violates(db_session, "uq_student_trait_ratings_entry_id_trait_id"):
        rate_trait(db_session, form_class.gmc, entry, form_class.traits["Punctuality"], 4)


def test_entries_are_for_pupils_of_the_arm(form_class: FormClass, db_session: Session) -> None:
    # Tobi Lawal is in JSS 1B, not JSS 1A.
    as_user(db_session, form_class, form_class.tunde)

    with violates(db_session, "student_term_entries_pupil_in_arm"):
        write_term_entry(
            db_session, form_class.gmc, form_class.section, form_class.tobi, comment="Not here."
        )


def test_a_retired_trait_gets_no_new_ratings(form_class: FormClass, db_session: Session) -> None:
    entry = fill_chukwuemeka(db_session, form_class)
    db_session.execute(
        text("update rating_traits set is_active = false where id = :id"),
        {"id": form_class.traits["Leadership"]},
    )

    with violates(db_session, "student_trait_ratings_trait_is_active"):
        rate_trait(db_session, form_class.gmc, entry, form_class.traits["Leadership"], 4)


def test_a_rating_uses_the_schools_own_trait(form_class: FormClass, db_session: Session) -> None:
    # Approved CHANGE (2026-10-14): a Bright Stars trait cannot be used on a GMC entry.
    bsa = create_school(
        db_session, code="BSA", name="Bright Stars Academy", school_type="nursery_primary"
    )
    bsa_punctuality = add_trait(db_session, bsa, "affective", "Punctuality", 1)
    entry = fill_chukwuemeka(db_session, form_class)

    with violates(db_session, "fk_student_trait_ratings_trait_id_rating_traits"):
        rate_trait(db_session, form_class.gmc, entry, bsa_punctuality, 4)


def test_an_assistant_enters_with_their_own_name(
    form_class: FormClass, db_session: Session
) -> None:
    # F22 rule 8: Bola Ige assists in JSS 1A and saves Musa's entry and a rating.
    as_user(db_session, form_class, form_class.bola)
    entry = write_term_entry(
        db_session,
        form_class.gmc,
        form_class.section,
        form_class.musa,
        comment="Musa works hard.",
        times_present=50,
    )
    rating = rate_trait(db_session, form_class.gmc, entry, form_class.traits["Neatness"], 4)

    authors = db_session.execute(
        text(
            "select (select entered_by from student_term_entries where id = :entry),"
            " (select entered_by from student_trait_ratings where id = :rating)"
        ),
        {"entry": entry, "rating": rating},
    ).one()
    assert tuple(authors) == (form_class.bola, form_class.bola)


def test_a_change_keeps_the_first_author_and_records_the_editor(
    form_class: FormClass, db_session: Session
) -> None:
    as_user(db_session, form_class, form_class.bola)
    entry = write_term_entry(
        db_session, form_class.gmc, form_class.section, form_class.musa, comment="Musa works hard."
    )
    as_user(db_session, form_class, form_class.tunde)

    db_session.execute(
        UPDATE_COMMENT, {"comment": "Musa works hard and helps others.", "id": entry}
    )

    authors = db_session.execute(
        text("select entered_by, updated_by from student_term_entries where id = :id"),
        {"id": entry},
    ).one()
    assert tuple(authors) == (form_class.bola, form_class.tunde)


def test_every_entry_and_rating_has_an_author(form_class: FormClass, db_session: Session) -> None:
    entry = fill_chukwuemeka(db_session, form_class)
    use_context(db_session, school_id=form_class.gmc)  # nobody signed in

    with violates(db_session, "student_term_entries_need_an_author"):
        write_term_entry(db_session, form_class.gmc, form_class.section, form_class.musa)
    with violates(db_session, "student_trait_ratings_need_an_author"):
        rate_trait(db_session, form_class.gmc, entry, form_class.traits["Honesty"], 4)


# --- the workflow (SPEC section 8; D-146) --------------------------------------------


@pytest.mark.parametrize("who", ["bola", "grace", "ngozi"])
def test_only_the_form_teacher_submits(
    form_class: FormClass, db_session: Session, who: str
) -> None:
    # F22 rules 8 and 9: Bola assists, Grace is not a form teacher, Ngozi is the principal.
    fill_chukwuemeka(db_session, form_class)
    as_user(db_session, form_class, getattr(form_class, who))

    with violates(db_session, "class_report_sections_submitted_by_form_teacher"):
        move_section(db_session, form_class.section, "submitted")


ACTIONS = text(
    "select from_status, to_status, actor_id, comment, revision_number"
    " from class_section_actions where section_id = :id order by created_at, to_status"
)


def test_the_form_teacher_submits_and_it_is_recorded(
    form_class: FormClass, db_session: Session
) -> None:
    # AT-15.5: the sections become Submitted, and the history says who did it.
    submit_sections(db_session, form_class)

    actions = [tuple(row) for row in db_session.execute(ACTIONS, {"id": form_class.section})]
    assert status_of(db_session, form_class.section) == ("submitted", 1)
    assert actions == [("open", "submitted", form_class.tunde, None, 1)]


def test_submitted_entries_are_locked(form_class: FormClass, db_session: Session) -> None:
    # F22 rule 9: once submitted, comments, ratings and attendance stay as they are.
    entry = submit_sections(db_session, form_class)

    with violates(db_session, "student_term_entries_section_is_locked"):
        db_session.execute(UPDATE_COMMENT, {"comment": "Changed", "id": entry})
    with violates(db_session, "student_term_entries_section_is_locked"):
        write_term_entry(
            db_session, form_class.gmc, form_class.section, form_class.musa, comment="Late."
        )
    with violates(db_session, "student_trait_ratings_section_is_locked"):
        db_session.execute(
            text("update student_trait_ratings set value = 3 where entry_id = :id"), {"id": entry}
        )
    with violates(db_session, "student_trait_ratings_section_is_locked"):
        db_session.execute(
            text("delete from student_trait_ratings where entry_id = :id"), {"id": entry}
        )
    with violates(db_session, "class_report_sections_is_locked"):
        db_session.execute(SET_TIMES_OPENED, {"opened": 61, "id": form_class.section})


def test_a_return_needs_a_comment_and_reopens_the_entries(
    form_class: FormClass, db_session: Session
) -> None:
    # Section 8: Chukwudi returns the sections with a comment; Tunde adds Musa and resubmits.
    submit_sections(db_session, form_class)
    as_user(db_session, form_class, form_class.chukwudi)

    with violates(db_session, "class_report_sections_return_needs_comment"):
        move_section(db_session, form_class.section, "returned")
    move_section(db_session, form_class.section, "returned", comment="Please add Musa's entry.")
    as_user(db_session, form_class, form_class.tunde)
    write_term_entry(
        db_session,
        form_class.gmc,
        form_class.section,
        form_class.musa,
        comment="Musa works hard.",
        times_present=55,
    )
    move_section(db_session, form_class.section, "submitted")

    actions = [tuple(row) for row in db_session.execute(ACTIONS, {"id": form_class.section})]
    assert ("submitted", "returned", form_class.chukwudi, "Please add Musa's entry.", 1) in actions
    assert status_of(db_session, form_class.section) == ("submitted", 1)


@pytest.mark.parametrize(
    ("start", "target"), [("open", "published"), ("open", "returned"), ("submitted", "open")]
)
def test_sections_move_only_along_the_workflow(
    form_class: FormClass, db_session: Session, start: str, target: str
) -> None:
    if start == "submitted":
        submit_sections(db_session, form_class)
    as_user(db_session, form_class, form_class.ngozi)

    with violates(db_session, "class_report_sections_transition_allowed"):
        move_section(db_session, form_class.section, target, comment="Moving on.")


def test_every_move_has_someone_behind_it(form_class: FormClass, db_session: Session) -> None:
    fill_chukwuemeka(db_session, form_class)
    use_context(db_session, school_id=form_class.gmc)  # nobody signed in

    with violates(db_session, "class_report_sections_needs_an_actor"):
        move_section(db_session, form_class.section, "submitted")


def test_a_comment_comes_only_with_a_move(form_class: FormClass, db_session: Session) -> None:
    # The return comment stays as given; nobody rewrites it afterwards.
    submit_sections(db_session, form_class)
    as_user(db_session, form_class, form_class.chukwudi)
    move_section(db_session, form_class.section, "returned", comment="Please add Musa's entry.")
    as_user(db_session, form_class, form_class.tunde)

    with violates(db_session, "class_report_sections_comment_comes_with_a_move"):
        db_session.execute(
            text("update class_report_sections set status_comment = 'Done' where id = :id"),
            {"id": form_class.section},
        )


def test_the_head_comments_until_publication(form_class: FormClass, db_session: Session) -> None:
    # F10: the principal's comments are written on the publish screen, after submission.
    entry = submit_sections(db_session, form_class)
    as_user(db_session, form_class, form_class.ngozi)

    db_session.execute(UPDATE_HEAD_COMMENT, {"comment": "An excellent term.", "id": entry})
    write_term_entry(
        db_session,
        form_class.gmc,
        form_class.section,
        form_class.musa,
        head_comment="Good effort this term.",
    )
    move_section(db_session, form_class.section, "published")

    with violates(db_session, "student_term_entries_section_is_locked"):
        db_session.execute(UPDATE_HEAD_COMMENT, {"comment": "Changed later.", "id": entry})


def test_published_sections_lock_everything(form_class: FormClass, db_session: Session) -> None:
    entry = publish_sections(db_session, form_class)
    as_user(db_session, form_class, form_class.tunde)

    with violates(db_session, "student_term_entries_section_is_locked"):
        db_session.execute(UPDATE_PRESENT, {"present": 58, "id": entry})
    with violates(db_session, "student_trait_ratings_section_is_locked"):
        rate_trait(db_session, form_class.gmc, entry, form_class.traits["Honesty"], 4)
    with violates(db_session, "class_report_sections_is_locked"):
        db_session.execute(SET_TIMES_OPENED, {"opened": 61, "id": form_class.section})


def test_a_reopen_needs_a_reason_and_starts_a_new_revision(
    form_class: FormClass, db_session: Session
) -> None:
    # D-146: like a sheet, the published sections reopen with a reason as revision 2.
    entry = publish_sections(db_session, form_class)

    with violates(db_session, "class_report_sections_reopen_needs_reason"):
        move_section(db_session, form_class.section, "open", reopen=True)
    with violates(db_session, "class_report_sections_revision_changes_on_reopen"):
        move_section(db_session, form_class.section, "open", comment="Attendance recounted")
    move_section(
        db_session, form_class.section, "open", comment="Attendance recounted", reopen=True
    )
    as_user(db_session, form_class, form_class.tunde)
    db_session.execute(UPDATE_PRESENT, {"present": 58, "id": entry})

    actions = [tuple(row) for row in db_session.execute(ACTIONS, {"id": form_class.section})]
    assert status_of(db_session, form_class.section) == ("open", 2)
    assert ("published", "open", form_class.ngozi, "Attendance recounted", 2) in actions


@pytest.mark.parametrize(
    "statement",
    ["update class_section_actions set comment = 'Edited'", "delete from class_section_actions"],
)
def test_the_history_cannot_be_rewritten(
    form_class: FormClass, db_session: Session, statement: str
) -> None:
    # Even the table owner is refused.
    submit_sections(db_session, form_class)

    with violates(db_session, "class_section_actions_append_only"):
        db_session.execute(text(statement))


# --- row-level security and grants ---------------------------------------------------


def test_school_users_see_their_class_sections(form_class: FormClass, db_session: Session) -> None:
    submit_sections(db_session, form_class)

    with acting_as(db_session, "app_user", school_id=form_class.gmc):
        counts = [db_session.scalar(COUNT[table]) for table in TABLES]

    assert all(count >= 1 for count in counts)


@pytest.mark.parametrize("table", TABLES)
def test_another_school_sees_none_of_these(
    form_class: FormClass, db_session: Session, table: str
) -> None:
    submit_sections(db_session, form_class)
    bsa = create_school(
        db_session, code="BSA", name="Bright Stars Academy", school_type="nursery_primary"
    )

    with acting_as(db_session, "app_user", school_id=bsa):
        assert db_session.scalar(COUNT[table]) == 0


@pytest.mark.parametrize(
    "statement",
    [
        "insert into class_section_actions (school_id, section_id, revision_number,"
        " from_status, to_status, actor_id) select school_id, id, 1, 'open', 'published',"
        " :user from class_report_sections limit 1",
        "update class_report_sections set arm_id = arm_id",
        "delete from class_report_sections",
        "update student_term_entries set entered_by = :user",
        "update student_term_entries set enrolment_id = enrolment_id",
        "delete from student_term_entries",
        "update student_trait_ratings set entered_by = :user",
    ],
)
def test_the_app_changes_only_what_it_may(
    form_class: FormClass, db_session: Session, statement: str
) -> None:
    # Moves come only through the workflow; authors come from the signed-in user.
    fill_chukwuemeka(db_session, form_class)

    with (
        acting_as(db_session, "app_user", school_id=form_class.gmc, user_id=form_class.ngozi),
        refused(db_session),
    ):
        db_session.execute(text(statement), {"user": form_class.ngozi})


@pytest.mark.parametrize("role", ["app_platform", "app_verifier"])
@pytest.mark.parametrize("table", TABLES)
def test_platform_and_verification_roles_cannot_read_class_sections(
    form_class: FormClass, db_session: Session, role: str, table: str
) -> None:
    # D-051: the platform never reads pupils' records.
    with acting_as(db_session, role), refused(db_session):
        db_session.execute(COUNT[table])
