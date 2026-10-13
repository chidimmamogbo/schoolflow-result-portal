"""Result sheets, scores and the approval workflow (BUILD_PROMPT 9.1 item 6; SPEC F09,
F10, F11, section 8; AC09.1, AC10.1, AC10.2, AC11.1; AT-10.4, AT-11.1, AT-12.1,
AT-12.2, AT-13.1, AT-13.2, AT-14.1 to AT-14.3, AT-16.3, AT-23.1, AT-23.2;
D-029, D-052, D-142, D-143, D-144).

Behaviour: one score sheet per subject, arm and term, using that term's
structure for the arm's level. Scores stay within each column's maximum,
only for pupils who take the subject, each with its author; the first score
locks the structure for the term. Scores change only while a sheet is a
draft or returned for correction, with a reason once the sheet has been
submitted (D-143). The status moves only along SPEC section 8: only the
assigned teacher submits, with every score present; a return needs a
comment; a submitter never reviews or approves (D-052); a sheet a reviewer
covers must be reviewed (D-142); a reopen needs a reason and starts a new
revision. Every move is kept in a history the app cannot edit, and
published scores never change. All data is fictional.
"""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from schoolflow_api.db import use_context
from schoolflow_api.grading.defaults import Component
from tests.db_support import acting_as, refused, violates
from tests.factories import (
    add_arm_subject,
    add_assistant,
    add_membership,
    add_reviewer_scope,
    add_student_subject,
    assign_teacher,
    component_ids,
    create_arm,
    create_class,
    create_department,
    create_school,
    create_session,
    create_sheet,
    create_structure,
    create_student,
    create_subject,
    create_term,
    create_user,
    enrol,
    enter_score,
    move_sheet,
)

TABLES = ("result_sheets", "result_revisions", "approval_actions", "scores")
COUNT: dict[str, TextClause] = {table: text(f"select count(*) from {table}") for table in TABLES}  # noqa: S608
SSS_COMPONENTS = (Component("Test", "Test", 40), Component("Examination", "Exam", 60))


@dataclass(frozen=True)
class Results:
    gmc: uuid.UUID
    first_term: uuid.UUID
    second_term: uuid.UUID
    jss1a: uuid.UUID
    jss1b: uuid.UUID
    jss_structure: uuid.UUID
    sss_structure: uuid.UUID
    components: dict[str, uuid.UUID]  # CA1, CA2, Exam
    mathematics: uuid.UUID
    english: uuid.UUID
    tunde: uuid.UUID  # teaches Mathematics in JSS 1A and 1B
    grace: uuid.UUID  # teaches English in JSS 1A
    bola: uuid.UUID  # assistant in JSS 1A
    emeka: uuid.UUID  # reviewer, Sciences (Mathematics is a Sciences subject)
    ngozi: uuid.UUID  # principal who also teaches English in JSS 1B (D-144)
    chukwudi: uuid.UUID  # additional school admin
    chukwuemeka: uuid.UUID  # enrolment in JSS 1A: Mathematics and English
    musa: uuid.UUID  # enrolment in JSS 1A: Mathematics only
    maths_1a: uuid.UUID
    english_1a: uuid.UUID
    english_1b: uuid.UUID


@pytest.fixture
def results(db_session: Session) -> Results:
    s = db_session
    gmc = create_school(s, code="GMC", name="Greenfield Model College")
    gmc_session = create_session(s, gmc)
    first_term = create_term(s, gmc, gmc_session, 1, is_active=True)
    second_term = create_term(s, gmc, gmc_session, 2)

    jss1 = create_class(s, gmc, "junior_secondary", "JSS 1")
    jss1a, jss1b = create_arm(s, gmc, jss1, "A"), create_arm(s, gmc, jss1, "B")
    sciences = create_department(s, gmc, "Sciences")
    mathematics = create_subject(s, gmc, "Mathematics", department_id=sciences)
    english = create_subject(s, gmc, "English Language")
    for arm in (jss1a, jss1b):
        for subject in (mathematics, english):
            add_arm_subject(s, gmc, arm, subject)
    jss_structure = create_structure(s, gmc, "junior_secondary", first_term)
    sss_structure = create_structure(s, gmc, "senior_secondary", first_term, SSS_COMPONENTS)

    def member(username: str, role: str, principal: bool = False) -> uuid.UUID:
        user = create_user(s, username=username, full_name="Test Person")
        add_membership(s, user, gmc, role, is_primary=principal)
        return user

    tunde, grace, bola = (
        member("tunde.adebayo", "teacher"),
        member("grace.etim", "teacher"),
        member("bola.ige", "teacher"),
    )
    emeka = member("emeka.nwosu", "reviewer")
    ngozi = member("ngozi.okeke", "school_admin", principal=True)
    chukwudi = member("chukwudi.eze", "school_admin")
    for arm in (jss1a, jss1b):
        assign_teacher(s, gmc, tunde, arm, mathematics)
    assign_teacher(s, gmc, grace, jss1a, english)
    assign_teacher(s, gmc, ngozi, jss1b, english)
    add_assistant(s, gmc, jss1a, bola)
    add_reviewer_scope(s, gmc, emeka, department_id=sciences)

    chukwuemeka_record = create_student(s, gmc, "GMC/2026/014", "Obi", "Chukwuemeka")
    musa_record = create_student(s, gmc, "GMC/2026/015", "Ibrahim", "Musa")
    chukwuemeka = enrol(s, gmc, chukwuemeka_record, gmc_session, jss1a)
    musa = enrol(s, gmc, musa_record, gmc_session, jss1a)
    for subject in (mathematics, english):
        add_student_subject(s, gmc, chukwuemeka, subject)
    add_student_subject(s, gmc, musa, mathematics)

    return Results(
        gmc,
        first_term,
        second_term,
        jss1a,
        jss1b,
        jss_structure,
        sss_structure,
        component_ids(s, jss_structure),
        mathematics,
        english,
        tunde,
        grace,
        bola,
        emeka,
        ngozi,
        chukwudi,
        chukwuemeka,
        musa,
        create_sheet(s, gmc, first_term, jss1a, jss_structure, mathematics),
        create_sheet(s, gmc, first_term, jss1a, jss_structure, english),
        create_sheet(s, gmc, first_term, jss1b, jss_structure, english),
    )


def as_user(session: Session, r: Results, user: uuid.UUID) -> None:
    use_context(session, school_id=r.gmc, user_id=user)


def fill(
    session: Session,
    r: Results,
    sheet: uuid.UUID,
    enrolment: uuid.UUID,
    ca1: int,
    ca2: int,
    exam: int,
) -> None:
    for label, value in (("CA1", ca1), ("CA2", ca2), ("Exam", exam)):
        enter_score(session, r.gmc, sheet, enrolment, r.components[label], value)


def complete_maths(session: Session, r: Results) -> None:
    """Tunde enters every Mathematics JSS 1A score (AT-10.4: Chukwuemeka 16, 15, 47)."""
    as_user(session, r, r.tunde)
    fill(session, r, r.maths_1a, r.chukwuemeka, 16, 15, 47)
    fill(session, r, r.maths_1a, r.musa, 10, 12, 30)


def submit_maths(session: Session, r: Results) -> None:
    complete_maths(session, r)
    move_sheet(session, r.maths_1a, "submitted")


def status_of(session: Session, sheet: uuid.UUID) -> tuple[str, int]:
    status, revision = session.execute(
        text("select status, revision from result_sheets where id = :id"), {"id": sheet}
    ).one()
    return status, revision


CHANGE_CA2 = text(
    "update scores set value = :value, change_reason = :reason"
    " where sheet_id = :sheet and enrolment_id = :enrolment and component_id = :component"
)


def change_ca2(session: Session, r: Results, value: int, reason: str | None = None) -> None:
    session.execute(
        CHANGE_CA2,
        {
            "value": value,
            "reason": reason,
            "sheet": r.maths_1a,
            "enrolment": r.musa,
            "component": r.components["CA2"],
        },
    )


# --- sheets ---------------------------------------------------------------------


def test_a_new_sheet_is_a_draft_at_revision_1(results: Results, db_session: Session) -> None:
    revisions = list(
        db_session.scalars(
            text("select revision_number from result_revisions where sheet_id = :id"),
            {"id": results.maths_1a},
        )
    )

    assert status_of(db_session, results.maths_1a) == ("draft", 1)
    assert revisions == [1]


def test_one_sheet_per_subject_per_arm_per_term(results: Results, db_session: Session) -> None:
    with violates(db_session, "ix_result_sheets_one_score_sheet"):
        create_sheet(
            db_session,
            results.gmc,
            results.first_term,
            results.jss1a,
            results.jss_structure,
            results.mathematics,
        )


def test_a_sheet_uses_its_terms_structure_for_its_level(
    results: Results, db_session: Session
) -> None:
    # The Senior Secondary structure cannot drive a JSS 1B sheet.
    with violates(db_session, "result_sheets_structure_matches"):
        create_sheet(
            db_session,
            results.gmc,
            results.first_term,
            results.jss1b,
            results.sss_structure,
            results.mathematics,
        )


def test_a_sheet_subject_is_one_the_arm_takes(results: Results, db_session: Session) -> None:
    basic_science = create_subject(db_session, results.gmc, "Basic Science")

    with violates(db_session, "fk_result_sheets_arm_id_arm_subjects"):
        create_sheet(
            db_session,
            results.gmc,
            results.first_term,
            results.jss1a,
            results.jss_structure,
            basic_science,
        )


# --- scores ------------------------------------------------------------------------


def test_a_teacher_enters_marks_with_their_name_on_them(
    results: Results, db_session: Session
) -> None:
    # AT-10.4: CA1 16, CA2 15, Exam 47 make a total of 78; the scores carry Tunde's name.
    complete_maths(db_session, results)

    total, authors = db_session.execute(
        text(
            "select sum(value), array_agg(distinct entered_by) from scores"
            " where sheet_id = :sheet and enrolment_id = :enrolment"
        ),
        {"sheet": results.maths_1a, "enrolment": results.chukwuemeka},
    ).one()
    assert total == 78
    assert authors == [results.tunde]


def test_the_first_score_locks_the_structure(results: Results, db_session: Session) -> None:
    complete_maths(db_session, results)

    locked = db_session.scalar(
        text("select locked_at is not null from assessment_structures where id = :id"),
        {"id": results.jss_structure},
    )
    assert locked is True


def test_a_score_stays_within_the_column_maximum(results: Results, db_session: Session) -> None:
    # AT-11.2: an Exam score of 61 (maximum 60) is never stored.
    as_user(db_session, results, results.tunde)

    with violates(db_session, "scores_within_maximum"):
        enter_score(
            db_session, results.gmc, results.maths_1a, results.musa, results.components["Exam"], 61
        )
    with violates(db_session, "ck_scores_value_not_negative"):
        enter_score(
            db_session, results.gmc, results.maths_1a, results.musa, results.components["CA1"], -1
        )


def test_a_score_uses_a_column_of_the_sheets_structure(
    results: Results, db_session: Session
) -> None:
    sss_test = component_ids(db_session, results.sss_structure)["Test"]
    as_user(db_session, results, results.tunde)

    with violates(db_session, "scores_component_in_structure"):
        enter_score(db_session, results.gmc, results.maths_1a, results.musa, sss_test, 10)


def test_only_pupils_who_take_the_subject_get_scores(results: Results, db_session: Session) -> None:
    # AC05.2: Musa does not take English.
    as_user(db_session, results, results.grace)

    with violates(db_session, "scores_student_takes_subject"):
        enter_score(
            db_session, results.gmc, results.english_1a, results.musa, results.components["CA1"], 10
        )


def test_one_score_per_pupil_per_column(results: Results, db_session: Session) -> None:
    complete_maths(db_session, results)

    with violates(db_session, "uq_scores_sheet_id_enrolment_id_component_id"):
        enter_score(
            db_session, results.gmc, results.maths_1a, results.musa, results.components["CA1"], 11
        )


def test_every_score_has_an_author(results: Results, db_session: Session) -> None:
    use_context(db_session, school_id=results.gmc)  # nobody signed in

    with violates(db_session, "scores_need_an_author"):
        enter_score(
            db_session, results.gmc, results.maths_1a, results.musa, results.components["CA1"], 10
        )


def test_first_draft_changes_need_no_reason(results: Results, db_session: Session) -> None:
    # D-143: Tunde fixes his own typing freely before the first submission.
    complete_maths(db_session, results)

    change_ca2(db_session, results, 13)


def test_scores_are_locked_once_submitted(results: Results, db_session: Session) -> None:
    # AT-12.2: after Submit, nobody changes, adds or removes a score.
    submit_maths(db_session, results)

    with violates(db_session, "scores_sheet_is_locked"):
        change_ca2(db_session, results, 14, "Second look")
    with violates(db_session, "scores_sheet_is_locked"):
        db_session.execute(
            text("delete from scores where sheet_id = :id"), {"id": results.maths_1a}
        )


def test_changes_after_a_return_need_a_reason(results: Results, db_session: Session) -> None:
    # AT-14.1: CA2 from 12 to 14 is refused without a reason, saved with one.
    submit_maths(db_session, results)
    as_user(db_session, results, results.emeka)
    move_sheet(
        db_session, results.maths_1a, "returned_for_correction", comment="Please check Musa's CA2."
    )
    as_user(db_session, results, results.tunde)

    with violates(db_session, "scores_change_needs_reason"):
        change_ca2(db_session, results, 14)
    change_ca2(db_session, results, 14, "Corrected transcription error")

    value, reason, by = db_session.execute(
        text(
            "select value, change_reason, updated_by from scores where sheet_id = :sheet"
            " and enrolment_id = :enrolment and component_id = :component"
        ),
        {
            "sheet": results.maths_1a,
            "enrolment": results.musa,
            "component": results.components["CA2"],
        },
    ).one()
    assert (value, reason, by) == (14, "Corrected transcription error", results.tunde)


def test_scores_are_removed_only_in_the_first_draft(results: Results, db_session: Session) -> None:
    submit_maths(db_session, results)
    as_user(db_session, results, results.emeka)
    move_sheet(db_session, results.maths_1a, "returned_for_correction", comment="Please check.")
    as_user(db_session, results, results.tunde)

    with violates(db_session, "scores_removed_only_in_first_draft"):
        db_session.execute(
            text("delete from scores where sheet_id = :id"), {"id": results.maths_1a}
        )


# --- the workflow (SPEC section 8) -------------------------------------------------


def test_submitting_needs_every_score(results: Results, db_session: Session) -> None:
    # AT-11.1 and AC09.1: Musa's CA2 is missing, so the sheet cannot be submitted.
    as_user(db_session, results, results.tunde)
    fill(db_session, results, results.maths_1a, results.chukwuemeka, 16, 15, 47)
    enter_score(
        db_session, results.gmc, results.maths_1a, results.musa, results.components["CA1"], 10
    )
    enter_score(
        db_session, results.gmc, results.maths_1a, results.musa, results.components["Exam"], 30
    )

    with violates(db_session, "result_sheets_scores_missing"):
        move_sheet(db_session, results.maths_1a, "submitted")


@pytest.mark.parametrize("who", ["grace", "bola"])
def test_only_the_assigned_teacher_submits(results: Results, db_session: Session, who: str) -> None:
    # Grace teaches English, not Mathematics; Bola assists in JSS 1A and never submits.
    complete_maths(db_session, results)
    as_user(db_session, results, getattr(results, who))

    with violates(db_session, "result_sheets_submitted_by_assigned_teacher"):
        move_sheet(db_session, results.maths_1a, "submitted")


def test_a_return_keeps_the_reviewers_comment(results: Results, db_session: Session) -> None:
    # AT-13.1: Emeka returns the sheet; Tunde sees the comment.
    submit_maths(db_session, results)
    as_user(db_session, results, results.emeka)
    move_sheet(
        db_session, results.maths_1a, "returned_for_correction", comment="Please check Musa's CA2."
    )

    comment, last_action = db_session.execute(
        text(
            "select s.status_comment, (select to_status || ' by ' || a.actor_id"
            " from approval_actions a where a.sheet_id = s.id"
            " order by a.created_at desc, a.to_status limit 1)"
            " from result_sheets s where s.id = :id"
        ),
        {"id": results.maths_1a},
    ).one()
    assert comment == "Please check Musa's CA2."
    assert last_action == f"returned_for_correction by {results.emeka}"


def test_a_comment_cannot_be_rewritten_later(results: Results, db_session: Session) -> None:
    # The reviewer's comment stays as given; it arrives only with a move.
    submit_maths(db_session, results)
    as_user(db_session, results, results.emeka)
    move_sheet(db_session, results.maths_1a, "returned_for_correction", comment="Please check.")
    as_user(db_session, results, results.tunde)

    with violates(db_session, "result_sheets_comment_comes_with_a_move"):
        db_session.execute(
            text("update result_sheets set status_comment = 'All fine' where id = :id"),
            {"id": results.maths_1a},
        )


def test_a_return_needs_a_comment(results: Results, db_session: Session) -> None:
    # AT-13.2.
    submit_maths(db_session, results)
    as_user(db_session, results, results.emeka)

    with violates(db_session, "result_sheets_return_needs_comment"):
        move_sheet(db_session, results.maths_1a, "returned_for_correction")


def test_the_workflow_runs_to_published(results: Results, db_session: Session) -> None:
    submit_maths(db_session, results)
    as_user(db_session, results, results.emeka)
    move_sheet(db_session, results.maths_1a, "returned_for_correction", comment="Please check.")
    as_user(db_session, results, results.tunde)
    move_sheet(db_session, results.maths_1a, "resubmitted")
    as_user(db_session, results, results.emeka)
    move_sheet(db_session, results.maths_1a, "reviewed")
    as_user(db_session, results, results.chukwudi)
    move_sheet(db_session, results.maths_1a, "approved")
    move_sheet(db_session, results.maths_1a, "published")

    steps = list(
        db_session.scalars(
            text(
                "select to_status from approval_actions where sheet_id = :id"
                " order by created_at, id"
            ),
            {"id": results.maths_1a},
        )
    )
    published = db_session.scalar(
        text("select published_at is not null from result_revisions where sheet_id = :id"),
        {"id": results.maths_1a},
    )
    assert set(steps) == {
        "submitted",
        "returned_for_correction",
        "resubmitted",
        "reviewed",
        "approved",
        "published",
    }
    assert len(steps) == 6
    assert published is True


@pytest.mark.parametrize("target", ["approved", "published", "reviewed"])
def test_a_draft_cannot_skip_ahead(results: Results, db_session: Session, target: str) -> None:
    complete_maths(db_session, results)
    as_user(db_session, results, results.chukwudi)

    with violates(db_session, "result_sheets_transition_allowed"):
        move_sheet(db_session, results.maths_1a, target)


def test_a_submitter_never_reviews_or_approves(results: Results, db_session: Session) -> None:
    # AT-14.3 and AC10.1: Ngozi teaches English in JSS 1B (D-144), submits, and cannot approve it.
    as_user(db_session, results, results.ngozi)
    move_sheet(db_session, results.english_1b, "submitted")  # JSS 1B has no pupils yet

    with violates(db_session, "result_sheets_separation_of_duties"):
        move_sheet(db_session, results.english_1b, "approved")


def test_a_covered_sheet_must_be_reviewed(results: Results, db_session: Session) -> None:
    # D-142: Mathematics is in Emeka's Sciences scope, so the admin cannot skip review.
    submit_maths(db_session, results)
    as_user(db_session, results, results.chukwudi)

    with violates(db_session, "result_sheets_needs_review"):
        move_sheet(db_session, results.maths_1a, "approved")


def test_an_uncovered_sheet_can_be_approved_straight_away(
    results: Results, db_session: Session
) -> None:
    # D-142: no reviewer covers English, so Chukwudi approves the submitted sheet.
    as_user(db_session, results, results.grace)
    for component in ("CA1", "CA2", "Exam"):
        enter_score(
            db_session,
            results.gmc,
            results.english_1a,
            results.chukwuemeka,
            results.components[component],
            10,
        )
    move_sheet(db_session, results.english_1a, "submitted")
    as_user(db_session, results, results.chukwudi)

    move_sheet(db_session, results.english_1a, "approved")

    assert status_of(db_session, results.english_1a) == ("approved", 1)


def publish_maths(session: Session, r: Results) -> None:
    submit_maths(session, r)
    as_user(session, r, r.emeka)
    move_sheet(session, r.maths_1a, "reviewed")
    as_user(session, r, r.chukwudi)
    move_sheet(session, r.maths_1a, "approved")
    move_sheet(session, r.maths_1a, "published")


def test_published_scores_never_change(results: Results, db_session: Session) -> None:
    # AT-16.3 and AC11.1: the database refuses, whoever asks.
    publish_maths(db_session, results)
    as_user(db_session, results, results.ngozi)

    with violates(db_session, "scores_sheet_is_locked"):
        change_ca2(db_session, results, 14, "Late correction")


def test_a_reopen_needs_a_reason(results: Results, db_session: Session) -> None:
    # AT-23.2.
    publish_maths(db_session, results)

    with violates(db_session, "result_sheets_reopen_needs_reason"):
        move_sheet(db_session, results.maths_1a, "draft", reopen=True)


def test_a_reopen_starts_a_new_revision(results: Results, db_session: Session) -> None:
    # AT-23.1: revision 2 opens with the reason; its score changes need reasons too (D-143).
    publish_maths(db_session, results)
    move_sheet(db_session, results.maths_1a, "draft", comment="Exam script re-marked", reopen=True)
    as_user(db_session, results, results.tunde)

    with violates(db_session, "scores_change_needs_reason"):
        change_ca2(db_session, results, 14)
    change_ca2(db_session, results, 14, "Exam script re-marked")

    reason = db_session.scalar(
        text("select reason from result_revisions where sheet_id = :id and revision_number = 2"),
        {"id": results.maths_1a},
    )
    assert status_of(db_session, results.maths_1a) == ("draft", 2)
    assert reason == "Exam script re-marked"


def test_the_submitter_of_any_revision_never_approves(
    results: Results, db_session: Session
) -> None:
    # D-052: "anyone who submitted any revision of a sheet".
    publish_maths(db_session, results)
    move_sheet(db_session, results.maths_1a, "draft", comment="Exam script re-marked", reopen=True)
    as_user(db_session, results, results.tunde)
    move_sheet(db_session, results.maths_1a, "submitted")

    with violates(db_session, "result_sheets_separation_of_duties"):
        move_sheet(db_session, results.maths_1a, "reviewed")


def test_the_revision_changes_only_on_a_reopen(results: Results, db_session: Session) -> None:
    complete_maths(db_session, results)

    with violates(db_session, "result_sheets_revision_changes_on_reopen"):
        db_session.execute(
            text("update result_sheets set revision = 5 where id = :id"), {"id": results.maths_1a}
        )


def test_every_move_has_someone_behind_it(results: Results, db_session: Session) -> None:
    complete_maths(db_session, results)
    use_context(db_session, school_id=results.gmc)  # nobody signed in

    with violates(db_session, "result_sheets_needs_an_actor"):
        move_sheet(db_session, results.maths_1a, "submitted")


@pytest.mark.parametrize(
    ("statement", "rule"),
    [
        ("update approval_actions set comment = 'Edited'", "approval_actions_append_only"),
        ("delete from approval_actions", "approval_actions_append_only"),
        ("delete from result_revisions", "result_revisions_kept"),
        ("update result_revisions set reason = 'Edited'", "result_revisions_kept"),
    ],
)
def test_the_history_cannot_be_rewritten(
    results: Results, db_session: Session, statement: str, rule: str
) -> None:
    # Even the table owner is refused: the workflow history is kept as it happened.
    submit_maths(db_session, results)

    with violates(db_session, rule):
        db_session.execute(text(statement))


# --- row-level security ----------------------------------------------------------


def test_school_users_see_their_results(results: Results, db_session: Session) -> None:
    submit_maths(db_session, results)

    with acting_as(db_session, "app_user", school_id=results.gmc):
        counts = [db_session.scalar(COUNT[table]) for table in TABLES]

    assert all(count >= 1 for count in counts)


@pytest.mark.parametrize("table", TABLES)
def test_another_school_sees_none_of_these_results(
    results: Results, db_session: Session, table: str
) -> None:
    submit_maths(db_session, results)
    bsa = create_school(
        db_session, code="BSA", name="Bright Stars Academy", school_type="nursery_primary"
    )

    with acting_as(db_session, "app_user", school_id=bsa):
        assert db_session.scalar(COUNT[table]) == 0


@pytest.mark.parametrize(
    "statement",
    [
        "insert into approval_actions (school_id, sheet_id, revision_number, from_status,"
        " to_status, actor_id) select school_id, id, 1, 'draft', 'approved', :user"
        " from result_sheets limit 1",
        "insert into result_revisions (school_id, sheet_id, revision_number)"
        " select school_id, id, 9 from result_sheets limit 1",
        "delete from result_sheets",
        "update result_sheets set subject_id = null",
    ],
)
def test_the_app_writes_history_only_through_the_workflow(
    results: Results, db_session: Session, statement: str
) -> None:
    with (
        acting_as(db_session, "app_user", school_id=results.gmc, user_id=results.chukwudi),
        refused(db_session),
    ):
        db_session.execute(text(statement), {"user": results.chukwudi})


@pytest.mark.parametrize("role", ["app_platform", "app_verifier"])
@pytest.mark.parametrize("table", TABLES)
def test_platform_and_verification_roles_cannot_read_results(
    results: Results, db_session: Session, role: str, table: str
) -> None:
    # D-051: the platform never reads pupils' scores.
    with acting_as(db_session, role), refused(db_session):
        db_session.execute(COUNT[table])
