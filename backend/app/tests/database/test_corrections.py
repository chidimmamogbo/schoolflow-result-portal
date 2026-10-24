"""Correction requests and uploaded files (BUILD_PROMPT 9.1 item 8; SPEC F15, F01, section 8;
AC15.1; AT-04.1, AT-22.1, AT-22.2, AT-23.1; D-055 to D-057, D-151, D-152; approved CHANGE
"The school logo links to the files table").

Behaviour: each uploaded file is recorded once, with a type and size allowed
for its purpose, a storage path inside its school's folder and its uploader;
a school's logo is always one of its own files; the platform role handles
logos only. A correction request is numbered per school, about one Valid
report and optionally a subject on it, sent by a school admin, reviewer,
teacher or parent (a parent only for their own wards) while the school's
Correction queue is on. Its status moves only along SPEC section 8 with the
messages it needs; only the requester replies; resolving may link the
pupil's newer report revision (AC15.1). The timeline is kept by the database
and never changes. One optional attachment per request, added by the
requester while the request is open. All data is fictional.
"""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from app.db.session import use_context
from app.tests.db_support import acting_as, refused, violates
from app.tests.factories import (
    add_arm_subject,
    add_membership,
    add_student_subject,
    assign_teacher,
    attach_file,
    component_ids,
    create_arm,
    create_class,
    create_correction_request,
    create_guardian,
    create_school,
    create_session,
    create_sheet,
    create_structure,
    create_student,
    create_subject,
    create_template,
    create_term,
    create_user,
    enrol,
    enter_score,
    link_ward,
    move_correction,
    move_sheet,
    publish_report,
    store_file,
)

REPORT_ID = "GMC-2627-T1-JSS1A-014"
NEW_CODE = "3HZT-8W2C-KM4R"
TABLES = ("files", "correction_requests", "correction_events", "correction_attachments")
CORRECTION_TABLES = TABLES[1:]
COUNT: dict[str, TextClause] = {table: text(f"select count(*) from {table}") for table in TABLES}  # noqa: S608
TIMELINE = text(
    "select from_status, to_status, actor_id, message from correction_events"
    " where request_id = :id order by created_at"
)
SET_LOGO = text("update schools set logo_file_id = :logo where id = :id")


@dataclass(frozen=True)
class Corrections:
    gmc: uuid.UUID
    first_term: uuid.UUID
    jss1a: uuid.UUID
    mathematics: uuid.UUID
    template: uuid.UUID
    ngozi: uuid.UUID  # principal: manages corrections
    tunde: uuid.UUID  # teaches Mathematics in JSS 1A
    ikenna: uuid.UUID  # parent of Chukwuemeka
    hauwa: uuid.UUID  # parent of Musa
    chukwuemeka_login: uuid.UUID  # the pupil's own login
    chukwuemeka: uuid.UUID  # enrolment in JSS 1A
    chukwuemeka_report: uuid.UUID  # First Term, revision 1, Valid
    musa_report: uuid.UUID  # First Term, revision 1, Valid


@pytest.fixture
def corrections(db_session: Session) -> Corrections:
    s = db_session
    gmc = create_school(s, code="GMC", name="Greenfield Model College")
    s.execute(
        text(
            "update school_features set enabled = true"
            " where school_id = :id and feature = 'correction_queue'"
        ),
        {"id": gmc},
    )
    gmc_session = create_session(s, gmc)
    first_term = create_term(s, gmc, gmc_session, 1, is_active=True)
    jss1a = create_arm(s, gmc, create_class(s, gmc, "junior_secondary", "JSS 1"), "A")
    mathematics = create_subject(s, gmc, "Mathematics")
    add_arm_subject(s, gmc, jss1a, mathematics)
    structure = create_structure(s, gmc, "junior_secondary", first_term)
    columns = component_ids(s, structure)

    def member(username: str, full_name: str, role: str, principal: bool = False) -> uuid.UUID:
        user = create_user(s, username=username, full_name=full_name)
        add_membership(s, user, gmc, role, is_primary=principal)
        return user

    ngozi = member("ngozi.okeke", "Ngozi Okeke", "school_admin", principal=True)
    tunde = member("tunde.adebayo", "Tunde Adebayo", "teacher")
    ikenna = member("ikenna.obi", "Ikenna Obi", "parent")
    hauwa = member("hauwa.ibrahim", "Hauwa Ibrahim", "parent")
    chukwuemeka_login = create_user(
        s, username="chukwuemeka.obi", full_name="Chukwuemeka Obi", student_school_id=gmc
    )
    add_membership(s, chukwuemeka_login, gmc, "student")
    assign_teacher(s, gmc, tunde, jss1a, mathematics)

    def pupil(
        admission_number: str,
        names: tuple[str, str],
        parent: tuple[uuid.UUID, str, str],
        login: uuid.UUID | None = None,
    ) -> uuid.UUID:
        student = create_student(s, gmc, admission_number, *names, user_id=login)
        parent_id, parent_name, relationship = parent
        guardian = create_guardian(s, gmc, parent_name, user_id=parent_id)
        link_ward(s, gmc, guardian, student, relationship)
        enrolment = enrol(s, gmc, student, gmc_session, jss1a)
        add_student_subject(s, gmc, enrolment, mathematics)
        return enrolment

    chukwuemeka = pupil(
        "GMC/2026/014", ("Obi", "Chukwuemeka"), (ikenna, "Ikenna Obi", "Father"), chukwuemeka_login
    )
    musa = pupil("GMC/2026/015", ("Ibrahim", "Musa"), (hauwa, "Hauwa Ibrahim", "Mother"))

    # Mathematics JSS 1A goes through the workflow and the class is published (D-142).
    sheet = create_sheet(s, gmc, first_term, jss1a, structure, mathematics)
    use_context(s, school_id=gmc, user_id=tunde)
    for enrolment, values in ((chukwuemeka, (16, 15, 47)), (musa, (10, 8, 20))):
        for label, value in zip(("CA1", "CA2", "Exam"), values, strict=True):
            enter_score(s, gmc, sheet, enrolment, columns[label], value)
    move_sheet(s, sheet, "submitted")
    use_context(s, school_id=gmc, user_id=ngozi)
    move_sheet(s, sheet, "approved")
    move_sheet(s, sheet, "published")
    template = create_template(s, gmc, "junior_secondary")

    def report(enrolment: uuid.UUID, report_code: str, code: str) -> uuid.UUID:
        return publish_report(
            s,
            gmc,
            first_term,
            jss1a,
            enrolment,
            template,
            report_code=report_code,
            verification_code=code,
        )

    return Corrections(
        gmc,
        first_term,
        jss1a,
        mathematics,
        template,
        ngozi,
        tunde,
        ikenna,
        hauwa,
        chukwuemeka_login,
        chukwuemeka,
        report(chukwuemeka, REPORT_ID, "7KQ4-M2XD-P9QA"),
        report(musa, "GMC-2627-T1-JSS1A-015", "9VYE-4QPA-6JND"),
    )


def as_user(session: Session, c: Corrections, user: uuid.UUID) -> None:
    use_context(session, school_id=c.gmc, user_id=user)


def ikenna_reports(session: Session, c: Corrections) -> uuid.UUID:
    """AT-22.1: Ikenna reports that Chukwuemeka's Mathematics score looks wrong."""
    as_user(session, c, c.ikenna)
    return create_correction_request(session, c.gmc, c.chukwuemeka_report, subject_id=c.mathematics)


def investigate(session: Session, c: Corrections, request: uuid.UUID) -> None:
    """Ngozi presses "Start investigating"."""
    as_user(session, c, c.ngozi)
    move_correction(session, request, "investigating")


def publish_revision_2(session: Session, c: Corrections) -> uuid.UUID:
    """Chukwuemeka's corrected report, revision 2 (AT-23.1)."""
    as_user(session, c, c.ngozi)
    return publish_report(
        session,
        c.gmc,
        c.first_term,
        c.jss1a,
        c.chukwuemeka,
        c.template,
        report_code=REPORT_ID,
        verification_code=NEW_CODE,
    )


def status_of(session: Session, request: uuid.UUID) -> tuple[str, str | None]:
    status, message = session.execute(
        text("select status, status_message from correction_requests where id = :id"),
        {"id": request},
    ).one()
    return status, message


# --- uploaded files (D-057) ----------------------------------------------------------


def test_a_file_records_who_uploaded_it(corrections: Corrections, db_session: Session) -> None:
    as_user(db_session, corrections, corrections.ikenna)

    photo = store_file(db_session, corrections.gmc)

    uploader = db_session.scalar(
        text("select uploaded_by from files where id = :id"), {"id": photo}
    )
    assert uploader == corrections.ikenna


@pytest.mark.parametrize(
    ("purpose", "content_type"),
    [
        ("correction_attachment", "image/svg+xml"),
        ("logo", "application/pdf"),
        ("logo", "text/html"),
    ],
)
def test_only_allowed_file_types(
    corrections: Corrections, db_session: Session, purpose: str, content_type: str
) -> None:
    # D-057: PNG, JPEG or WebP; PDF only for correction attachments; never SVG.
    as_user(db_session, corrections, corrections.ngozi)

    with violates(db_session, "ck_files_content_type_allowed"):
        store_file(db_session, corrections.gmc, purpose=purpose, content_type=content_type)
    store_file(db_session, corrections.gmc, content_type="application/pdf")


@pytest.mark.parametrize(
    ("purpose", "size"), [("logo", 1_048_577), ("correction_attachment", 4_194_305), ("logo", 0)]
)
def test_files_stay_within_their_size_limit(
    corrections: Corrections, db_session: Session, purpose: str, size: int
) -> None:
    # D-057: up to 1 MB for images such as logos, 4 MB for attachments.
    as_user(db_session, corrections, corrections.ngozi)

    with violates(db_session, "ck_files_size_within_limit"):
        store_file(
            db_session,
            corrections.gmc,
            purpose=purpose,
            content_type="image/png",
            size_bytes=size,
        )


@pytest.mark.parametrize(
    "key", ["schools/{other}/logo/a1b2", "schools/{gmc}/../secrets", "elsewhere/{gmc}/a1b2"]
)
def test_a_file_lives_in_its_schools_folder(
    corrections: Corrections, db_session: Session, key: str
) -> None:
    # D-057: random paths under schools/{school_id}/, nothing outside it.
    as_user(db_session, corrections, corrections.ngozi)

    with violates(db_session, "ck_files_storage_key_format"):
        store_file(
            db_session,
            corrections.gmc,
            storage_key=key.format(gmc=corrections.gmc, other=uuid.uuid4()),
        )


def test_every_file_has_an_uploader(corrections: Corrections, db_session: Session) -> None:
    use_context(db_session, school_id=corrections.gmc)  # nobody signed in

    with violates(db_session, "files_need_an_uploader"):
        store_file(db_session, corrections.gmc)


@pytest.mark.parametrize(
    "statement", ["update files set original_name = 'renamed.jpg'", "delete from files"]
)
def test_a_file_record_never_changes(
    corrections: Corrections, db_session: Session, statement: str
) -> None:
    as_user(db_session, corrections, corrections.ikenna)
    store_file(db_session, corrections.gmc)

    with violates(db_session, "files_append_only"):
        db_session.execute(text(statement))


def test_a_school_logo_is_one_of_its_own_files(
    corrections: Corrections, db_session: Session
) -> None:
    # Approved CHANGE (2026-10-14): GMC's logo cannot be Bright Stars Academy's file.
    bsa = create_school(
        db_session, code="BSA", name="Bright Stars Academy", school_type="nursery_primary"
    )
    as_user(db_session, corrections, corrections.ngozi)
    gmc_logo, bsa_logo = (
        store_file(
            db_session, school, purpose="logo", content_type="image/png", original_name="crest.png"
        )
        for school in (corrections.gmc, bsa)
    )

    db_session.execute(SET_LOGO, {"logo": gmc_logo, "id": corrections.gmc})
    with violates(db_session, "fk_schools_logo_file_id_files"):
        db_session.execute(SET_LOGO, {"logo": bsa_logo, "id": corrections.gmc})


def test_the_platform_handles_logos_only(corrections: Corrections, db_session: Session) -> None:
    # D-152: the super admin sets a school's logo; other files stay out of reach.
    as_user(db_session, corrections, corrections.ikenna)
    store_file(db_session, corrections.gmc)  # Ikenna's photo of the exam script
    admin = create_user(
        db_session, username="platform.admin", full_name="Platform Admin", is_super_admin=True
    )

    with acting_as(db_session, "app_platform", user_id=admin):
        store_file(
            db_session,
            corrections.gmc,
            purpose="logo",
            content_type="image/png",
            original_name="crest.png",
        )
        visible = list(db_session.scalars(text("select purpose from files")))
    with acting_as(db_session, "app_platform", user_id=admin), refused(db_session):
        store_file(db_session, corrections.gmc)

    assert visible == ["logo"]


# --- correction requests (F15) -------------------------------------------------------


def test_a_parent_reports_a_problem_on_their_wards_report(
    corrections: Corrections, db_session: Session
) -> None:
    # AT-22.1: request number 1 (CR-0001) is Open, from Ikenna, and starts the timeline.
    request = ikenna_reports(db_session, corrections)

    row = db_session.execute(
        text(
            "select number, status, requested_by, issue_type from correction_requests"
            " where id = :id"
        ),
        {"id": request},
    ).one()
    timeline = [tuple(event) for event in db_session.execute(TIMELINE, {"id": request})]
    assert tuple(row) == (1, "open", corrections.ikenna, "score")
    assert timeline == [(None, "open", corrections.ikenna, None)]


def test_requests_are_numbered_per_school(corrections: Corrections, db_session: Session) -> None:
    ikenna_reports(db_session, corrections)
    as_user(db_session, corrections, corrections.hauwa)
    create_correction_request(
        db_session,
        corrections.gmc,
        corrections.musa_report,
        explanation="Musa's CA2 should be 10, not 8.",
    )

    numbers = list(
        db_session.scalars(
            text("select number from correction_requests where school_id = :id order by number"),
            {"id": corrections.gmc},
        )
    )
    assert numbers == [1, 2]


def test_no_requests_while_the_correction_queue_is_off(
    corrections: Corrections, db_session: Session
) -> None:
    # AT-04.1: a disabled feature rejects requests, in the database too.
    db_session.execute(
        text(
            "update school_features set enabled = false"
            " where school_id = :id and feature = 'correction_queue'"
        ),
        {"id": corrections.gmc},
    )

    with violates(db_session, "correction_requests_feature_is_on"):
        ikenna_reports(db_session, corrections)


def test_a_parent_reports_only_on_their_own_wards(
    corrections: Corrections, db_session: Session
) -> None:
    # AT-22.2: Hauwa Ibrahim is Musa's mother, not Chukwuemeka's.
    as_user(db_session, corrections, corrections.hauwa)

    with violates(db_session, "correction_requests_parent_of_the_pupil"):
        create_correction_request(db_session, corrections.gmc, corrections.chukwuemeka_report)


def test_pupils_do_not_send_requests(corrections: Corrections, db_session: Session) -> None:
    # F15 and the permission matrix: students never create correction requests.
    as_user(db_session, corrections, corrections.chukwuemeka_login)

    with violates(db_session, "correction_requests_requester_role"):
        create_correction_request(db_session, corrections.gmc, corrections.chukwuemeka_report)


def test_a_teacher_can_send_a_request(corrections: Corrections, db_session: Session) -> None:
    # F15: teachers and reviewers create requests too.
    as_user(db_session, corrections, corrections.tunde)

    request = create_correction_request(
        db_session,
        corrections.gmc,
        corrections.musa_report,
        subject_id=corrections.mathematics,
        explanation="Musa's CA2 was entered as 8; his test paper shows 10.",
    )

    assert status_of(db_session, request) == ("open", None)


def test_requests_are_about_a_valid_report(corrections: Corrections, db_session: Session) -> None:
    # Once revision 2 is out, revision 1 is no longer reported on.
    publish_revision_2(db_session, corrections)

    with violates(db_session, "correction_requests_about_a_valid_report"):
        ikenna_reports(db_session, corrections)


def test_the_subject_is_one_on_the_report(corrections: Corrections, db_session: Session) -> None:
    # Chukwuemeka does not take Basic Science.
    basic_science = create_subject(db_session, corrections.gmc, "Basic Science")
    as_user(db_session, corrections, corrections.ikenna)

    with violates(db_session, "correction_requests_on_the_report"):
        create_correction_request(
            db_session, corrections.gmc, corrections.chukwuemeka_report, subject_id=basic_science
        )


@pytest.mark.parametrize(
    ("issue_type", "explanation", "rule"),
    [
        ("wrong", "Something looks off.", "ck_correction_requests_issue_type_allowed"),
        ("score", " ", "ck_correction_requests_explanation_valid"),
        ("score", "x" * 1001, "ck_correction_requests_explanation_valid"),
    ],
)
def test_a_request_has_a_known_issue_and_an_explanation(
    corrections: Corrections, db_session: Session, issue_type: str, explanation: str, rule: str
) -> None:
    # "What looks wrong?" and "Tell us more".
    as_user(db_session, corrections, corrections.ikenna)

    with violates(db_session, rule):
        create_correction_request(
            db_session,
            corrections.gmc,
            corrections.chukwuemeka_report,
            issue_type=issue_type,
            explanation=explanation,
        )


def test_every_request_has_a_requester(corrections: Corrections, db_session: Session) -> None:
    use_context(db_session, school_id=corrections.gmc)  # nobody signed in

    with violates(db_session, "correction_requests_need_a_requester"):
        create_correction_request(db_session, corrections.gmc, corrections.chukwuemeka_report)


# --- the request workflow (SPEC section 8; D-151) ------------------------------------


def test_the_school_works_a_request_through_to_resolved(
    corrections: Corrections, db_session: Session
) -> None:
    # AT-22.1 to AT-23.1 and AC15.1: the timeline, Ikenna's reply, and the linked revision 2.
    request = ikenna_reports(db_session, corrections)
    investigate(db_session, corrections, request)
    move_correction(
        db_session,
        request,
        "needs_more_information",
        message="Please send a photo of the exam script.",
    )
    as_user(db_session, corrections, corrections.ikenna)
    move_correction(db_session, request, "investigating", message="Photo sent to the school.")
    revision_2 = publish_revision_2(db_session, corrections)
    move_correction(
        db_session,
        request,
        "resolved",
        message="You were right. The exam score was corrected from 47 to 51.",
        corrected_report_id=revision_2,
    )

    timeline = [tuple(event)[:2] for event in db_session.execute(TIMELINE, {"id": request})]
    linked = db_session.scalar(
        text("select corrected_report_id from correction_requests where id = :id"),
        {"id": request},
    )
    assert timeline == [
        (None, "open"),
        ("open", "investigating"),
        ("investigating", "needs_more_information"),
        ("needs_more_information", "investigating"),
        ("investigating", "resolved"),
    ]
    assert linked == revision_2


@pytest.mark.parametrize(
    ("start", "target"),
    [("open", "resolved"), ("open", "rejected"), ("resolved", "investigating")],
)
def test_requests_move_only_along_the_workflow(
    corrections: Corrections, db_session: Session, start: str, target: str
) -> None:
    request = ikenna_reports(db_session, corrections)
    as_user(db_session, corrections, corrections.ngozi)
    if start == "resolved":
        move_correction(db_session, request, "investigating")
        move_correction(db_session, request, "resolved", message="Checked: the score is right.")

    with violates(db_session, "correction_requests_transition_allowed"):
        move_correction(db_session, request, target, message="Moving on.")


@pytest.mark.parametrize("target", ["rejected", "needs_more_information", "resolved"])
def test_the_schools_answers_need_a_message(
    corrections: Corrections, db_session: Session, target: str
) -> None:
    # "Reject with reason", "Ask for more information", and the response when resolving.
    request = ikenna_reports(db_session, corrections)
    investigate(db_session, corrections, request)

    with violates(db_session, "correction_requests_needs_a_message"):
        move_correction(db_session, request, target)


def test_only_the_requester_replies(corrections: Corrections, db_session: Session) -> None:
    # Section 8: back to Investigating when the requester replies, with a reply.
    request = ikenna_reports(db_session, corrections)
    investigate(db_session, corrections, request)
    move_correction(db_session, request, "needs_more_information", message="Please send a photo.")

    with violates(db_session, "correction_requests_reply_by_requester"):
        move_correction(db_session, request, "investigating", message="Replying for him.")
    as_user(db_session, corrections, corrections.ikenna)
    with violates(db_session, "correction_requests_needs_a_message"):
        move_correction(db_session, request, "investigating")
    move_correction(db_session, request, "investigating", message="Photo sent to the school.")

    assert status_of(db_session, request) == ("investigating", "Photo sent to the school.")


def test_a_message_comes_only_with_a_move(corrections: Corrections, db_session: Session) -> None:
    # The school's answer stays as given.
    request = ikenna_reports(db_session, corrections)
    investigate(db_session, corrections, request)
    move_correction(
        db_session, request, "rejected", message="Positions were correct. Ties explained."
    )

    with violates(db_session, "correction_requests_message_comes_with_a_move"):
        db_session.execute(
            text("update correction_requests set status_message = 'Changed' where id = :id"),
            {"id": request},
        )


def test_every_move_has_someone_behind_it(corrections: Corrections, db_session: Session) -> None:
    request = ikenna_reports(db_session, corrections)
    use_context(db_session, school_id=corrections.gmc)  # nobody signed in

    with violates(db_session, "correction_requests_needs_an_actor"):
        move_correction(db_session, request, "investigating")


@pytest.mark.parametrize("which", ["same revision", "another pupil"])
def test_the_fix_is_a_newer_revision_of_the_same_report(
    corrections: Corrections, db_session: Session, which: str
) -> None:
    # D-151: a resolved request links the pupil's newer, Valid revision for that term.
    request = ikenna_reports(db_session, corrections)
    investigate(db_session, corrections, request)
    linked = corrections.chukwuemeka_report if which == "same revision" else corrections.musa_report

    with violates(db_session, "correction_requests_corrected_by_a_newer_revision"):
        move_correction(
            db_session, request, "resolved", message="Corrected.", corrected_report_id=linked
        )


def test_the_fix_is_linked_only_when_resolving(
    corrections: Corrections, db_session: Session
) -> None:
    request = ikenna_reports(db_session, corrections)
    investigate(db_session, corrections, request)
    revision_2 = publish_revision_2(db_session, corrections)

    with violates(db_session, "ck_correction_requests_corrected_only_when_resolved"):
        move_correction(
            db_session,
            request,
            "needs_more_information",
            message="Please check the new report.",
            corrected_report_id=revision_2,
        )


@pytest.mark.parametrize(
    "statement",
    ["update correction_events set message = 'Edited'", "delete from correction_events"],
)
def test_the_timeline_cannot_be_rewritten(
    corrections: Corrections, db_session: Session, statement: str
) -> None:
    # Even the table owner is refused.
    ikenna_reports(db_session, corrections)

    with violates(db_session, "correction_events_append_only"):
        db_session.execute(text(statement))


# --- attachments (F15, D-057) --------------------------------------------------------


def test_the_requester_attaches_one_file(corrections: Corrections, db_session: Session) -> None:
    # AT-22.1: Ikenna adds a photo of the exam script; one attachment per request (D-152).
    request = ikenna_reports(db_session, corrections)
    attach_file(db_session, corrections.gmc, request, store_file(db_session, corrections.gmc))

    with violates(db_session, "uq_correction_attachments_request_id"):
        attach_file(
            db_session,
            corrections.gmc,
            request,
            store_file(db_session, corrections.gmc, original_name="second-page.jpg"),
        )


def test_only_the_requester_attaches(corrections: Corrections, db_session: Session) -> None:
    request = ikenna_reports(db_session, corrections)
    as_user(db_session, corrections, corrections.ngozi)

    with violates(db_session, "correction_attachments_by_the_requester"):
        attach_file(db_session, corrections.gmc, request, store_file(db_session, corrections.gmc))


def test_only_attachment_files_are_attached(corrections: Corrections, db_session: Session) -> None:
    request = ikenna_reports(db_session, corrections)
    crest = store_file(
        db_session,
        corrections.gmc,
        purpose="logo",
        content_type="image/png",
        original_name="crest.png",
    )

    with violates(db_session, "correction_attachments_file_is_an_attachment"):
        attach_file(db_session, corrections.gmc, request, crest)


def test_no_attachments_once_the_school_is_investigating(
    corrections: Corrections, db_session: Session
) -> None:
    request = ikenna_reports(db_session, corrections)
    photo = store_file(db_session, corrections.gmc)
    investigate(db_session, corrections, request)
    as_user(db_session, corrections, corrections.ikenna)

    with violates(db_session, "correction_attachments_while_open"):
        attach_file(db_session, corrections.gmc, request, photo)


def test_an_attachment_from_another_school_is_refused(
    corrections: Corrections, db_session: Session
) -> None:
    bsa = create_school(
        db_session, code="BSA", name="Bright Stars Academy", school_type="nursery_primary"
    )
    request = ikenna_reports(db_session, corrections)
    bsa_file = store_file(db_session, bsa)

    with violates(db_session, "fk_correction_attachments_file_id_files"):
        attach_file(db_session, corrections.gmc, request, bsa_file)


@pytest.mark.parametrize(
    "statement",
    [
        "update correction_attachments set file_id = file_id",
        "delete from correction_attachments",
    ],
)
def test_an_attachment_never_changes(
    corrections: Corrections, db_session: Session, statement: str
) -> None:
    # The evidence stays as sent.
    request = ikenna_reports(db_session, corrections)
    attach_file(db_session, corrections.gmc, request, store_file(db_session, corrections.gmc))

    with violates(db_session, "correction_attachments_append_only"):
        db_session.execute(text(statement))


# --- row-level security and grants ---------------------------------------------------


def send_with_photo(session: Session, c: Corrections) -> None:
    request = ikenna_reports(session, c)
    attach_file(session, c.gmc, request, store_file(session, c.gmc))


def test_school_users_see_their_corrections(corrections: Corrections, db_session: Session) -> None:
    send_with_photo(db_session, corrections)

    with acting_as(db_session, "app_user", school_id=corrections.gmc):
        counts = [db_session.scalar(COUNT[table]) for table in TABLES]

    assert all(count >= 1 for count in counts)


@pytest.mark.parametrize("table", TABLES)
def test_another_school_sees_none_of_these(
    corrections: Corrections, db_session: Session, table: str
) -> None:
    send_with_photo(db_session, corrections)
    bsa = create_school(
        db_session, code="BSA", name="Bright Stars Academy", school_type="nursery_primary"
    )

    with acting_as(db_session, "app_user", school_id=bsa):
        assert db_session.scalar(COUNT[table]) == 0


@pytest.mark.parametrize(
    "statement",
    [
        "update correction_requests set explanation = 'Edited'",
        "update correction_requests set requested_by = :user",
        "delete from correction_requests",
        "insert into correction_events (school_id, request_id, to_status, actor_id)"
        " select school_id, id, 'resolved', :user from correction_requests limit 1",
        "update files set size_bytes = 1",
        "delete from files",
    ],
)
def test_the_app_changes_only_what_it_may(
    corrections: Corrections, db_session: Session, statement: str
) -> None:
    # Requests change only through their workflow; the timeline and files never change.
    send_with_photo(db_session, corrections)

    with (
        acting_as(db_session, "app_user", school_id=corrections.gmc, user_id=corrections.ngozi),
        refused(db_session),
    ):
        db_session.execute(text(statement), {"user": corrections.ngozi})


@pytest.mark.parametrize("role", ["app_platform", "app_verifier"])
@pytest.mark.parametrize("table", CORRECTION_TABLES)
def test_platform_and_verification_roles_cannot_read_corrections(
    corrections: Corrections, db_session: Session, role: str, table: str
) -> None:
    # D-051: correction requests are about pupils' results.
    send_with_photo(db_session, corrections)

    with acting_as(db_session, role), refused(db_session):
        db_session.execute(COUNT[table])


def test_the_verification_role_cannot_read_files(
    corrections: Corrections, db_session: Session
) -> None:
    send_with_photo(db_session, corrections)

    with acting_as(db_session, "app_verifier"), refused(db_session):
        db_session.execute(COUNT["files"])
