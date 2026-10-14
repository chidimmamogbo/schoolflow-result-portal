"""Report templates, report documents, verification and Students needing attention entries
(BUILD_PROMPT 9.1 item 7; SPEC F11, F12, F13, F23, section 8; AC11.1, AC13.1, AC23.1;
AT-16.2, AT-16.3, AT-21.1, AT-23.1, AT-24.1, AT-24.2; D-058, D-071 to D-077, D-147,
D-149, D-150).

Behaviour: each template save is a new, never-changing version for its level,
numbered by the database, only for levels that are on. A pupil's report is
stored only once every sheet of the class is published, with a template for
the pupil's level; the database numbers its revision, works out the
snapshot's hash and the masked name, and records who published it. A new
revision keeps the report ID and supersedes the previous one; revoking needs
a reason; nothing else changes and reports are never deleted. The school keeps
each report's verification code, the verification table only its hash, and
the public lookup returns only the published facts (never scores), whatever
the school's status; the verification role can use nothing else. Students
needing attention entries are written for a valid report only and never
change. All data is fictional.
"""

import hashlib
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from schoolflow_api.db import use_context
from tests.db_support import acting_as, refused, violates
from tests.factories import (
    add_arm_subject,
    add_attention_entry,
    add_membership,
    add_student_subject,
    assign_teacher,
    component_ids,
    create_arm,
    create_class,
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
    move_sheet,
    publish_report,
)

CHUKWUEMEKA_CODE = "7KQ4-M2XD-P9QA"
NEW_CODE = "3HZT-8W2C-KM4R"
MUSA_CODE = "9VYE-4QPA-6JND"
REPORT_ID = "GMC-2627-T1-JSS1A-014"
SNAPSHOT = {
    "pupil": {"name": "Chukwuemeka Obi", "admission_number": "GMC/2026/014"},
    "subjects": [{"name": "Mathematics", "scores": [16, 15, 47], "total": 78, "grade": "A1"}],
}
SCHOOL_TABLES = ("report_templates", "report_documents", "attention_entries")
TABLES = (*SCHOOL_TABLES, "verification_tokens")
COUNT: dict[str, TextClause] = {table: text(f"select count(*) from {table}") for table in TABLES}  # noqa: S608


@dataclass(frozen=True)
class Published:
    gmc: uuid.UUID
    gmc_session: uuid.UUID
    first_term: uuid.UUID
    jss1: uuid.UUID
    jss1a: uuid.UUID
    mathematics: uuid.UUID
    english_1a: uuid.UUID  # English sheet, JSS 1A, First Term (published)
    template: uuid.UUID  # Junior Secondary template, version 1
    tunde: uuid.UUID  # teaches Mathematics in JSS 1A
    chukwudi: uuid.UUID  # school admin who approves and publishes
    chukwuemeka: uuid.UUID  # enrolment in JSS 1A
    musa: uuid.UUID  # enrolment in JSS 1A: 38 in Mathematics


@pytest.fixture
def published(db_session: Session) -> Published:
    s = db_session
    gmc = create_school(s, code="GMC", name="Greenfield Model College")
    gmc_session = create_session(s, gmc)
    first_term = create_term(s, gmc, gmc_session, 1, is_active=True)
    jss1 = create_class(s, gmc, "junior_secondary", "JSS 1")
    jss1a = create_arm(s, gmc, jss1, "A")
    mathematics = create_subject(s, gmc, "Mathematics")
    english = create_subject(s, gmc, "English Language")
    for subject in (mathematics, english):
        add_arm_subject(s, gmc, jss1a, subject)
    structure = create_structure(s, gmc, "junior_secondary", first_term)
    columns = component_ids(s, structure)

    def member(username: str, full_name: str, role: str) -> uuid.UUID:
        user = create_user(s, username=username, full_name=full_name)
        add_membership(s, user, gmc, role)
        return user

    tunde = member("tunde.adebayo", "Tunde Adebayo", "teacher")
    grace = member("grace.etim", "Grace Etim", "teacher")
    chukwudi = member("chukwudi.eze", "Chukwudi Eze", "school_admin")
    assign_teacher(s, gmc, tunde, jss1a, mathematics)
    assign_teacher(s, gmc, grace, jss1a, english)

    def pupil(admission_number: str, surname: str, first_name: str) -> uuid.UUID:
        student = create_student(s, gmc, admission_number, surname, first_name)
        enrolment = enrol(s, gmc, student, gmc_session, jss1a)
        for subject in (mathematics, english):
            add_student_subject(s, gmc, enrolment, subject)
        return enrolment

    chukwuemeka = pupil("GMC/2026/014", "Obi", "Chukwuemeka")
    musa = pupil("GMC/2026/015", "Ibrahim", "Musa")

    # Both sheets go through the whole workflow (D-142: no reviewer covers them).
    sheets: dict[uuid.UUID, uuid.UUID] = {}
    for subject, teacher, marks in (
        (mathematics, tunde, {chukwuemeka: (16, 15, 47), musa: (10, 8, 20)}),
        (english, grace, {chukwuemeka: (14, 15, 40), musa: (12, 11, 35)}),
    ):
        sheet = create_sheet(s, gmc, first_term, jss1a, structure, subject)
        use_context(s, school_id=gmc, user_id=teacher)
        for enrolment, values in marks.items():
            for label, value in zip(("CA1", "CA2", "Exam"), values, strict=True):
                enter_score(s, gmc, sheet, enrolment, columns[label], value)
        move_sheet(s, sheet, "submitted")
        use_context(s, school_id=gmc, user_id=chukwudi)
        move_sheet(s, sheet, "approved")
        move_sheet(s, sheet, "published")
        sheets[subject] = sheet

    return Published(
        gmc,
        gmc_session,
        first_term,
        jss1,
        jss1a,
        mathematics,
        sheets[english],
        create_template(s, gmc, "junior_secondary"),
        tunde,
        chukwudi,
        chukwuemeka,
        musa,
    )


def publish_chukwuemeka(
    session: Session,
    p: Published,
    *,
    code: str = CHUKWUEMEKA_CODE,
    report_code: str = REPORT_ID,
    template: uuid.UUID | None = None,
) -> uuid.UUID:
    """Chukwudi publishes Chukwuemeka's First Term report (AT-16.2)."""
    return publish_report(
        session,
        p.gmc,
        p.first_term,
        p.jss1a,
        p.chukwuemeka,
        template or p.template,
        report_code=report_code,
        verification_code=code,
        snapshot=SNAPSHOT,
    )


def publish_musa(session: Session, p: Published, *, code: str = MUSA_CODE) -> uuid.UUID:
    return publish_report(
        session,
        p.gmc,
        p.first_term,
        p.jss1a,
        p.musa,
        p.template,
        report_code="GMC-2627-T1-JSS1A-015",
        verification_code=code,
    )


VERIFY = text("select * from verify_report(:code)")


def verify(session: Session, code: str) -> list[dict[str, Any]]:
    """What the public verify page gets, looked up as the verification role (D-076)."""
    with acting_as(session, "app_verifier"):
        return [dict(row) for row in session.execute(VERIFY, {"code": code}).mappings()]


REVOKE = text(
    "update report_documents set status = 'revoked', revoke_reason = :reason where id = :id"
)
SET_STATUS = text("update report_documents set status = :status where id = :id")


# --- report templates (F12 rule 5) ---------------------------------------------------


def test_each_template_save_is_a_new_version(published: Published, db_session: Session) -> None:
    # "Save as version {n}": the database numbers the versions and records who saved them.
    create_template(db_session, published.gmc, "junior_secondary", style="classic")

    versions = [
        tuple(row)
        for row in db_session.execute(
            text(
                "select version, style, created_by from report_templates"
                " where school_id = :school and level = 'junior_secondary' order by version"
            ),
            {"school": published.gmc},
        )
    ]
    assert versions == [(1, "modern", published.chukwudi), (2, "classic", published.chukwudi)]


@pytest.mark.parametrize(
    "statement", ["update report_templates set style = 'compact'", "delete from report_templates"]
)
def test_a_template_version_never_changes(
    published: Published, db_session: Session, statement: str
) -> None:
    # Published reports keep the version they were issued with.
    with violates(db_session, "report_templates_append_only"):
        db_session.execute(text(statement))


def test_templates_only_for_levels_that_are_on(published: Published, db_session: Session) -> None:
    # GMC is Secondary only, so it has no Nursery template.
    with violates(db_session, "report_templates_level_is_on"):
        create_template(db_session, published.gmc, "nursery")


@pytest.mark.parametrize(
    ("style", "settings", "rule"),
    [
        ("glossy", {}, "ck_report_templates_style_allowed"),
        ("modern", ["blocks"], "ck_report_templates_settings_is_object"),
    ],
)
def test_a_template_has_a_known_style_and_settings(
    published: Published, db_session: Session, style: str, settings: object, rule: str
) -> None:
    with violates(db_session, rule):
        create_template(
            db_session, published.gmc, "junior_secondary", style=style, settings=settings
        )


def test_every_template_has_an_author(published: Published, db_session: Session) -> None:
    use_context(db_session, school_id=published.gmc)  # nobody signed in

    with violates(db_session, "report_templates_need_an_author"):
        create_template(db_session, published.gmc, "junior_secondary")


# --- report documents (F11, F12 rule 5, section 8) -----------------------------------


def test_a_published_report_is_revision_1_and_valid(
    published: Published, db_session: Session
) -> None:
    # AT-16.2: revision 1, VALID, its report ID, the masked name and a frozen snapshot.
    report = publish_chukwuemeka(db_session, published)

    row = db_session.execute(
        text(
            "select revision, status, report_code, masked_name, published_by,"
            " snapshot::text as snapshot_text, snapshot_hash from report_documents"
            " where id = :id"
        ),
        {"id": report},
    ).one()
    assert (row.revision, row.status, row.report_code, row.masked_name, row.published_by) == (
        1,
        "valid",
        REPORT_ID,
        "Chuk*** O.",
        published.chukwudi,
    )
    # Anyone holding the stored snapshot can check its hash.
    assert row.snapshot_hash == hashlib.sha256(row.snapshot_text.encode()).digest()


def test_a_report_waits_for_every_sheet_of_the_class(
    published: Published, db_session: Session
) -> None:
    # Only published results: with English JSS 1A reopened, no JSS 1A report is made.
    move_sheet(
        db_session, published.english_1a, "draft", comment="Exam script re-marked", reopen=True
    )

    with violates(db_session, "report_documents_results_published"):
        publish_chukwuemeka(db_session, published)


def test_a_report_uses_a_template_for_the_pupils_level(
    published: Published, db_session: Session
) -> None:
    senior = create_template(db_session, published.gmc, "senior_secondary")

    with violates(db_session, "report_documents_template_matches_level"):
        publish_chukwuemeka(db_session, published, template=senior)


def test_a_report_is_for_a_pupil_of_the_class(published: Published, db_session: Session) -> None:
    # Tobi Lawal is in JSS 1B.
    jss1b = create_arm(db_session, published.gmc, published.jss1, "B")
    tobi = enrol(
        db_session,
        published.gmc,
        create_student(db_session, published.gmc, "GMC/2026/031", "Lawal", "Tobi"),
        published.gmc_session,
        jss1b,
    )

    with violates(db_session, "report_documents_pupil_in_arm"):
        publish_report(
            db_session,
            published.gmc,
            published.first_term,
            published.jss1a,
            tobi,
            published.template,
            report_code="GMC-2627-T1-JSS1A-031",
            verification_code=NEW_CODE,
        )


def test_a_new_revision_supersedes_the_previous_one(
    published: Published, db_session: Session
) -> None:
    # AT-23.1: after a correction, revision 2 is VALID and revision 1 SUPERSEDED.
    publish_chukwuemeka(db_session, published)
    publish_chukwuemeka(db_session, published, code=NEW_CODE)

    revisions = [
        tuple(row)
        for row in db_session.execute(
            text(
                "select revision, status from report_documents where enrolment_id = :enrolment"
                " order by revision"
            ),
            {"enrolment": published.chukwuemeka},
        )
    ]
    assert revisions == [(1, "superseded"), (2, "valid")]


def test_a_report_keeps_its_report_id_across_revisions(
    published: Published, db_session: Session
) -> None:
    publish_chukwuemeka(db_session, published)

    with violates(db_session, "report_documents_keeps_its_report_id"):
        publish_chukwuemeka(
            db_session, published, code=NEW_CODE, report_code="GMC-2627-T1-JSS1A-999"
        )


def test_every_report_has_a_publisher(published: Published, db_session: Session) -> None:
    use_context(db_session, school_id=published.gmc)  # nobody signed in

    with violates(db_session, "report_documents_need_a_publisher"):
        publish_chukwuemeka(db_session, published)


@pytest.mark.parametrize(
    ("report_code", "code", "rule"),
    [
        ("gmc 2627 t1", CHUKWUEMEKA_CODE, "ck_report_documents_report_code_format"),
        (REPORT_ID, "7KQ4M2XDP9QA", "ck_report_documents_verification_code_format"),
        (REPORT_ID, "7KQ4-M2XD-P9QI", "ck_report_documents_verification_code_format"),
    ],
)
def test_report_ids_and_codes_have_their_shapes(
    published: Published, db_session: Session, report_code: str, code: str, rule: str
) -> None:
    # D-072: codes are three groups of four Crockford Base32 characters (no I, L, O or U).
    with violates(db_session, rule):
        publish_chukwuemeka(db_session, published, code=code, report_code=report_code)


def test_each_code_is_used_once(published: Published, db_session: Session) -> None:
    publish_chukwuemeka(db_session, published)

    with violates(db_session, "uq_report_documents_verification_code"):
        publish_musa(db_session, published, code=CHUKWUEMEKA_CODE)


@pytest.mark.parametrize(
    "statement",
    [
        "update report_documents set snapshot = '{}'::jsonb",
        "update report_documents set report_code = 'GMC-2627-T1-JSS1A-999'",
        "delete from report_documents",
    ],
)
def test_a_published_report_never_changes(
    published: Published, db_session: Session, statement: str
) -> None:
    # AC11.1 and AT-16.3: even the table owner is refused.
    publish_chukwuemeka(db_session, published)

    with violates(db_session, "report_documents_kept"):
        db_session.execute(text(statement))


def test_revoking_needs_a_reason(published: Published, db_session: Session) -> None:
    # AT-24.2: Chukwudi revokes with a reason; the database records who did it.
    report = publish_chukwuemeka(db_session, published)

    with violates(db_session, "report_documents_revoke_needs_reason"):
        db_session.execute(REVOKE, {"reason": None, "id": report})
    db_session.execute(REVOKE, {"reason": "Issued for the wrong pupil", "id": report})

    revoked = db_session.execute(
        text("select status, revoked_by, revoke_reason from report_documents where id = :id"),
        {"id": report},
    ).one()
    assert tuple(revoked) == ("revoked", published.chukwudi, "Issued for the wrong pupil")


@pytest.mark.parametrize(
    ("start", "target", "rule"),
    [
        ("valid", "superseded", "report_documents_superseded_only_by_a_new_revision"),
        ("revoked", "valid", "report_documents_status_change_allowed"),
        ("superseded", "valid", "report_documents_status_change_allowed"),
    ],
)
def test_report_status_moves_only_one_way(
    published: Published, db_session: Session, start: str, target: str, rule: str
) -> None:
    report = publish_chukwuemeka(db_session, published)
    if start == "revoked":
        db_session.execute(REVOKE, {"reason": "Issued for the wrong pupil", "id": report})
    if start == "superseded":
        publish_chukwuemeka(db_session, published, code=NEW_CODE)

    with violates(db_session, rule):
        db_session.execute(SET_STATUS, {"status": target, "id": report})


# --- verification (F13, D-071 to D-077, D-149) ---------------------------------------


def test_a_valid_code_shows_only_the_published_facts(
    published: Published, db_session: Session
) -> None:
    # AT-21.1: VALID, the school, "Chuk*** O.", 2026/2027, First Term, revision 1; no scores.
    publish_chukwuemeka(db_session, published)

    [found] = verify(db_session, CHUKWUEMEKA_CODE)

    assert set(found) == {
        "school_name",
        "masked_name",
        "session_name",
        "term_number",
        "status",
        "revision",
        "report_code",
        "published_at",
        "has_newer_revision",
    }
    assert {key: value for key, value in found.items() if key != "published_at"} == {
        "school_name": "Greenfield Model College",
        "masked_name": "Chuk*** O.",
        "session_name": "2026/2027",
        "term_number": 1,
        "status": "valid",
        "revision": 1,
        "report_code": REPORT_ID,
        "has_newer_revision": False,
    }


@pytest.mark.parametrize("typed", ["7kq4-m2xd-p9qa", "7KQ4M2XDP9QA", " 7KQ4 M2XD P9QA "])
def test_codes_are_forgiving_to_type(published: Published, db_session: Session, typed: str) -> None:
    # D-072: lowercase, missing dashes and spaces are accepted.
    publish_chukwuemeka(db_session, published)

    assert [row["status"] for row in verify(db_session, typed)] == ["valid"]


def test_an_old_code_shows_superseded(published: Published, db_session: Session) -> None:
    # AT-24.1 and AC13.1: revision 1's QR now says a newer version exists.
    publish_chukwuemeka(db_session, published)
    publish_chukwuemeka(db_session, published, code=NEW_CODE)

    [old] = verify(db_session, CHUKWUEMEKA_CODE)
    [new] = verify(db_session, NEW_CODE)

    assert (old["status"], old["revision"], old["has_newer_revision"]) == ("superseded", 1, True)
    assert (new["status"], new["revision"], new["has_newer_revision"]) == ("valid", 2, False)


def test_a_revoked_report_shows_revoked(published: Published, db_session: Session) -> None:
    # AT-24.2.
    report = publish_chukwuemeka(db_session, published)
    db_session.execute(REVOKE, {"reason": "Issued for the wrong pupil", "id": report})

    [found] = verify(db_session, CHUKWUEMEKA_CODE)

    assert found["status"] == "revoked"


@pytest.mark.parametrize("typed", ["AAAA-BBBB-CCCC", "7KQ4-M2XD", ""])
def test_an_unknown_code_finds_nothing(
    published: Published, db_session: Session, typed: str
) -> None:
    publish_chukwuemeka(db_session, published)

    assert verify(db_session, typed) == []


def test_a_report_still_verifies_when_the_school_is_suspended(
    published: Published, db_session: Session
) -> None:
    # D-075: a report already issued remains a real record.
    publish_chukwuemeka(db_session, published)
    db_session.execute(
        text("update schools set status = 'suspended' where id = :id"), {"id": published.gmc}
    )

    assert [row["status"] for row in verify(db_session, CHUKWUEMEKA_CODE)] == ["valid"]


def test_the_lookup_table_keeps_only_hashes(published: Published, db_session: Session) -> None:
    # D-073 and D-149: the verification table holds the code's SHA-256 hash, never the code.
    report = publish_chukwuemeka(db_session, published)

    columns = set(
        db_session.scalars(
            text(
                "select column_name from information_schema.columns"
                " where table_name = 'verification_tokens'"
            )
        )
    )
    code_hash = db_session.scalar(
        text("select code_hash from verification_tokens where report_document_id = :id"),
        {"id": report},
    )
    assert columns == {"id", "school_id", "report_document_id", "code_hash", "created_at"}
    assert code_hash == hashlib.sha256(CHUKWUEMEKA_CODE.encode()).digest()


# --- Students needing attention entries (F23, D-147) ---------------------------------


def add_musas_maths(
    session: Session, p: Published, report: uuid.UUID, score: int = 38
) -> uuid.UUID:
    """AC23.1: Musa scored 38 in Mathematics; the pass mark is 40."""
    return add_attention_entry(
        session,
        p.gmc,
        report,
        "subject",
        subject_id=p.mathematics,
        teacher_id=p.tunde,
        score=score,
        grade="F9",
        pass_mark=40,
    )


def test_a_score_below_the_pass_mark_becomes_an_entry(
    published: Published, db_session: Session
) -> None:
    # AC23.1, with Musa's row for the By student view (1 failed subject, average 48).
    report = publish_musa(db_session, published)

    add_musas_maths(db_session, published, report)
    add_attention_entry(
        db_session,
        published.gmc,
        report,
        "student",
        pass_mark=40,
        failed_count=1,
        average=Decimal("48.00"),
    )

    kinds = sorted(
        db_session.scalars(
            text("select kind from attention_entries where report_document_id = :id"),
            {"id": report},
        )
    )
    assert kinds == ["student", "subject"]


@pytest.mark.parametrize(
    ("kind", "values", "rule"),
    [
        ("subject", {"score": 45}, "ck_attention_entries_below_pass_mark"),
        ("subject", {"subject_id": None}, "ck_attention_entries_subject_fields"),
        ("skill", {}, "ck_attention_entries_skill_fields"),
        ("student", {"failed_count": 0, "score": None}, "ck_attention_entries_student_fields"),
    ],
)
def test_each_kind_of_entry_carries_its_own_facts(
    published: Published,
    db_session: Session,
    kind: str,
    values: dict[str, Any],
    rule: str,
) -> None:
    report = publish_musa(db_session, published)
    entry: dict[str, Any] = {
        "subject_id": published.mathematics,
        "teacher_id": published.tunde,
        "score": 38,
        "grade": "F9",
        "pass_mark": 40,
    }
    entry.update(values)

    with violates(db_session, rule):
        add_attention_entry(db_session, published.gmc, report, kind, **entry)


def test_entries_only_for_a_valid_report(published: Published, db_session: Session) -> None:
    # AT-23.1: entries come from the current revision; a superseded report gets none.
    first = publish_musa(db_session, published)
    publish_musa(db_session, published, code=NEW_CODE)

    with violates(db_session, "attention_entries_for_a_valid_report"):
        add_musas_maths(db_session, published, first)


def test_one_entry_per_subject_per_report(published: Published, db_session: Session) -> None:
    report = publish_musa(db_session, published)
    add_musas_maths(db_session, published, report)

    with violates(db_session, "ix_attention_entries_one_per_subject"):
        add_musas_maths(db_session, published, report, score=30)


@pytest.mark.parametrize(
    "statement", ["update attention_entries set score = 39", "delete from attention_entries"]
)
def test_entries_never_change(published: Published, db_session: Session, statement: str) -> None:
    report = publish_musa(db_session, published)
    add_musas_maths(db_session, published, report)

    with violates(db_session, "attention_entries_append_only"):
        db_session.execute(text(statement))


# --- row-level security and grants ---------------------------------------------------


def publish_all(session: Session, p: Published) -> None:
    publish_chukwuemeka(session, p)
    add_musas_maths(session, p, publish_musa(session, p))


def test_school_users_see_their_reports(published: Published, db_session: Session) -> None:
    publish_all(db_session, published)

    with acting_as(db_session, "app_user", school_id=published.gmc):
        counts = [db_session.scalar(COUNT[table]) for table in SCHOOL_TABLES]

    assert all(count >= 1 for count in counts)


@pytest.mark.parametrize("table", SCHOOL_TABLES)
def test_another_school_sees_none_of_these(
    published: Published, db_session: Session, table: str
) -> None:
    publish_all(db_session, published)
    bsa = create_school(
        db_session, code="BSA", name="Bright Stars Academy", school_type="nursery_primary"
    )

    with acting_as(db_session, "app_user", school_id=bsa):
        assert db_session.scalar(COUNT[table]) == 0


@pytest.mark.parametrize(
    "statement",
    [
        "update report_documents set snapshot = '{}'::jsonb",
        "update report_documents set revision = 9",
        "delete from report_documents",
        "select count(*) from verification_tokens",
        "insert into verification_tokens (school_id, report_document_id, code_hash)"
        " select school_id, id, sha256('x') from report_documents limit 1",
        "update attention_entries set score = 39",
        "delete from report_templates",
        "select * from verify_report('7KQ4-M2XD-P9QA')",
    ],
)
def test_the_app_changes_only_what_it_may(
    published: Published, db_session: Session, statement: str
) -> None:
    # Snapshots, history and the lookup table are out of the app's reach.
    publish_all(db_session, published)

    with (
        acting_as(db_session, "app_user", school_id=published.gmc, user_id=published.chukwudi),
        refused(db_session),
    ):
        db_session.execute(text(statement))


@pytest.mark.parametrize("role", ["app_platform", "app_verifier"])
@pytest.mark.parametrize("table", [*TABLES, "scores", "students"])
def test_platform_and_verification_roles_read_no_tables(
    published: Published, db_session: Session, role: str, table: str
) -> None:
    # D-051 and D-076: the verification role only calls verify_report().
    publish_all(db_session, published)

    with acting_as(db_session, role), refused(db_session):
        db_session.execute(text(f"select count(*) from {table}"))  # noqa: S608
