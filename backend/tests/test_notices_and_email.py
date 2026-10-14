"""Notices and the email outbox (BUILD_PROMPT 9.1 item 9; SPEC F17, F18; AC17.1, AC17.2,
AC18.1; D-080 to D-086, D-153, D-154).

Behaviour: only a school admin posts or edits a manual notice; system notices
may come with no signed-in author, and their text never changes; archiving is
final. A notice keeps what the admin chose (its audience), the people it
reached (each a member of its school) and who read it (each person marks
only their own reads); none of these change. The outbox holds one email per
recipient per event, never a password, token or score in its data; an email
moves only from Queued to Sent (with proof), Failed or another attempt (at
most 5), Failed can be queued again, Sent is final, and its content never
changes. School users queue their school's emails and see status only; the
platform sees every email's status; only the sender role (app_sender) reads
template data, and it reads nothing else. All data is fictional.
"""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import TextClause, text
from sqlalchemy.orm import Session

from schoolflow_api.db import use_context
from tests.db_support import acting_as, refused, violates
from tests.factories import (
    add_membership,
    add_notice_audience,
    add_notice_recipient,
    create_class,
    create_school,
    create_user,
    mark_notice_read,
    post_notice,
    queue_email,
)

NOTICE_TABLES = ("notices", "notice_audiences", "notice_recipients", "notice_reads")
TABLES = (*NOTICE_TABLES, "email_outbox")
COUNT: dict[str, TextClause] = {table: text(f"select count(*) from {table}") for table in TABLES}  # noqa: S608
SEND = text(
    "update email_outbox set status = :status, attempts = attempts + 1, sent_at = :sent,"
    " provider_message_id = :provider where id = :id"
)


@dataclass(frozen=True)
class Boards:
    gmc: uuid.UUID
    bsa: uuid.UUID
    jss1: uuid.UUID
    ngozi: uuid.UUID  # GMC principal
    tunde: uuid.UUID  # GMC teacher
    ikenna: uuid.UUID  # GMC parent
    chiamaka: uuid.UUID  # BSA head teacher


@pytest.fixture
def boards(db_session: Session) -> Boards:
    s = db_session
    gmc = create_school(s, code="GMC", name="Greenfield Model College")
    bsa = create_school(s, code="BSA", name="Bright Stars Academy", school_type="nursery_primary")

    def member(username: str, school: uuid.UUID, role: str, principal: bool = False) -> uuid.UUID:
        user = create_user(s, username=username, full_name="Test Person")
        add_membership(s, user, school, role, is_primary=principal)
        return user

    return Boards(
        gmc,
        bsa,
        create_class(s, gmc, "junior_secondary", "JSS 1"),
        member("ngozi.okeke", gmc, "school_admin", principal=True),
        member("tunde.adebayo", gmc, "teacher"),
        member("ikenna.obi", gmc, "parent"),
        member("chiamaka.nwafor", bsa, "school_admin", principal=True),
    )


def as_user(session: Session, school: uuid.UUID, user: uuid.UUID) -> None:
    use_context(session, school_id=school, user_id=user)


def ngozi_posts(session: Session, b: Boards, **values: object) -> uuid.UUID:
    as_user(session, b.gmc, b.ngozi)
    return post_notice(session, b.gmc, **values)  # type: ignore[arg-type]


# --- notices (F17, D-084 to D-086) ---------------------------------------------------


def test_a_school_admin_posts_a_notice(boards: Boards, db_session: Session) -> None:
    notice = ngozi_posts(db_session, boards)

    row = db_session.execute(
        text("select author_id, status, pinned, kind from notices where id = :id"), {"id": notice}
    ).one()
    assert tuple(row) == (boards.ngozi, "published", False, "manual")


@pytest.mark.parametrize("who", ["tunde", "ikenna"])
def test_only_school_admins_post_notices(boards: Boards, db_session: Session, who: str) -> None:
    # F17 and D-086: form teachers and parents do not post.
    as_user(db_session, boards.gmc, getattr(boards, who))

    with violates(db_session, "notices_posted_by_school_admin"):
        post_notice(db_session, boards.gmc)


def test_a_system_notice_may_have_no_author(boards: Boards, db_session: Session) -> None:
    # D-085: "invoice paid" comes from a payment webhook, with nobody signed in.
    use_context(db_session, school_id=boards.gmc)

    post_notice(db_session, boards.gmc, kind="system", title="Invoice paid")
    with violates(db_session, "notices_need_an_author"):
        post_notice(db_session, boards.gmc)


@pytest.mark.parametrize(
    ("values", "rule"),
    [
        ({"title": " "}, "ck_notices_title_valid"),
        ({"body": "x" * 5001}, "ck_notices_body_valid"),
        ({"kind": "banner"}, "ck_notices_kind_allowed"),
    ],
)
def test_a_notice_has_a_title_body_and_kind(
    boards: Boards, db_session: Session, values: dict[str, object], rule: str
) -> None:
    with violates(db_session, rule):
        ngozi_posts(db_session, boards, **values)


def test_a_manual_notice_can_be_edited_pinned_and_archived(
    boards: Boards, db_session: Session
) -> None:
    notice = ngozi_posts(db_session, boards)

    db_session.execute(
        text("update notices set title = 'Mid-term break moved', pinned = true where id = :id"),
        {"id": notice},
    )
    db_session.execute(
        text("update notices set status = 'archived' where id = :id"), {"id": notice}
    )

    assert db_session.execute(
        text("select title, pinned, status from notices where id = :id"), {"id": notice}
    ).one() == ("Mid-term break moved", True, "archived")


def test_a_system_notices_text_never_changes(boards: Boards, db_session: Session) -> None:
    # "First Term results for JSS 1 are now available" stays as the system wrote it.
    notice = ngozi_posts(
        db_session, boards, kind="system", title="First Term results for JSS 1 are now available"
    )

    with violates(db_session, "notices_system_text_kept"):
        db_session.execute(
            text("update notices set title = 'Edited' where id = :id"), {"id": notice}
        )


def test_archiving_is_final(boards: Boards, db_session: Session) -> None:
    notice = ngozi_posts(db_session, boards)
    db_session.execute(
        text("update notices set status = 'archived' where id = :id"), {"id": notice}
    )

    with violates(db_session, "notices_archive_is_final"):
        db_session.execute(
            text("update notices set status = 'published' where id = :id"), {"id": notice}
        )


def test_only_school_admins_edit_notices(boards: Boards, db_session: Session) -> None:
    notice = ngozi_posts(db_session, boards)
    as_user(db_session, boards.gmc, boards.tunde)

    with violates(db_session, "notices_posted_by_school_admin"):
        db_session.execute(text("update notices set pinned = true where id = :id"), {"id": notice})


def test_an_audience_is_a_known_role_or_a_class(boards: Boards, db_session: Session) -> None:
    # F17: everyone, selected roles, optionally selected classes (AC17.1: JSS 1 parents).
    notice = ngozi_posts(db_session, boards)

    add_notice_audience(db_session, boards.gmc, notice, role="parent", class_id=boards.jss1)
    with violates(db_session, "ck_notice_audiences_role_allowed"):
        add_notice_audience(db_session, boards.gmc, notice, role="visitor")
    with violates(db_session, "ix_notice_audiences_unique_choice"):
        add_notice_audience(db_session, boards.gmc, notice, role="parent", class_id=boards.jss1)


def test_recipients_are_members_of_the_notices_school(boards: Boards, db_session: Session) -> None:
    # AC17.2: a GMC notice never reaches a BSA user.
    notice = ngozi_posts(db_session, boards)
    add_notice_recipient(db_session, boards.gmc, notice, boards.ikenna)

    with violates(db_session, "fk_notice_recipients_user_id_school_memberships"):
        add_notice_recipient(db_session, boards.gmc, notice, boards.chiamaka)
    with violates(db_session, "uq_notice_recipients_notice_id_user_id"):
        add_notice_recipient(db_session, boards.gmc, notice, boards.ikenna)


def test_people_mark_only_their_own_reads(boards: Boards, db_session: Session) -> None:
    notice = ngozi_posts(db_session, boards)
    as_user(db_session, boards.gmc, boards.ikenna)

    mark_notice_read(db_session, boards.gmc, notice, boards.ikenna)
    with violates(db_session, "notice_reads_by_the_reader"):
        mark_notice_read(db_session, boards.gmc, notice, boards.tunde)
    with violates(db_session, "uq_notice_reads_notice_id_user_id"):
        mark_notice_read(db_session, boards.gmc, notice, boards.ikenna)


@pytest.mark.parametrize(
    ("statement", "rule"),
    [
        ("update notice_audiences set role = 'teacher'", "notice_audiences_append_only"),
        ("delete from notice_recipients", "notice_recipients_append_only"),
        ("delete from notice_reads", "notice_reads_append_only"),
    ],
)
def test_who_was_told_and_who_read_never_change(
    boards: Boards, db_session: Session, statement: str, rule: str
) -> None:
    notice = ngozi_posts(db_session, boards)
    add_notice_audience(db_session, boards.gmc, notice, role="parent")
    add_notice_recipient(db_session, boards.gmc, notice, boards.ikenna)
    as_user(db_session, boards.gmc, boards.ikenna)
    mark_notice_read(db_session, boards.gmc, notice, boards.ikenna)

    with violates(db_session, rule):
        db_session.execute(text(statement))


# --- the email outbox (F18, D-080 to D-083) ------------------------------------------


def test_an_email_waits_in_the_outbox(boards: Boards, db_session: Session) -> None:
    email = queue_email(db_session, boards.gmc)

    row = db_session.execute(
        text("select status, attempts, priority from email_outbox where id = :id"),
        {"id": email},
    ).one()
    assert tuple(row) == ("queued", 0, 5)


def test_one_email_per_recipient_per_event(boards: Boards, db_session: Session) -> None:
    # AC18.1: publishing JSS 1A twice in a retry never queues Ikenna's email twice.
    key = "results_published:jss1a:first-term:ikenna"
    queue_email(db_session, boards.gmc, idempotency_key=key)

    with violates(db_session, "uq_email_outbox_idempotency_key"):
        queue_email(db_session, boards.gmc, idempotency_key=key)


@pytest.mark.parametrize("key", ["password", "temporary_password", "token", "scores", "grade"])
def test_no_secrets_or_scores_in_email_data(boards: Boards, db_session: Session, key: str) -> None:
    # F18 and D-081, D-083: links are made at send time; emails never carry scores.
    with violates(db_session, "ck_email_outbox_no_secrets_or_scores"):
        queue_email(db_session, boards.gmc, template_data={key: "x"})


@pytest.mark.parametrize(
    ("values", "rule"),
    [
        ({"to_address": "not-an-email"}, "ck_email_outbox_to_address_format"),
        ({"priority": 0}, "ck_email_outbox_priority_range"),
        ({"email_type": "Results Published"}, "ck_email_outbox_type_format"),
        ({"template": "Results Published"}, "ck_email_outbox_template_format"),
    ],
)
def test_an_email_is_well_formed(
    boards: Boards, db_session: Session, values: dict[str, object], rule: str
) -> None:
    with violates(db_session, rule):
        queue_email(db_session, boards.gmc, **values)  # type: ignore[arg-type]


def test_a_sent_email_records_its_proof_and_stays_sent(boards: Boards, db_session: Session) -> None:
    email = queue_email(db_session, boards.gmc)

    with violates(db_session, "ck_email_outbox_sent_with_proof"):
        db_session.execute(SEND, {"status": "sent", "sent": None, "provider": None, "id": email})
    db_session.execute(
        text(
            "update email_outbox set status = 'sent', attempts = 1, sent_at = now(),"
            " provider_message_id = 'msg_fictional_1' where id = :id"
        ),
        {"id": email},
    )
    with violates(db_session, "email_outbox_status_change_allowed"):
        db_session.execute(
            text("update email_outbox set status = 'queued' where id = :id"), {"id": email}
        )


def test_retries_count_up_to_five(boards: Boards, db_session: Session) -> None:
    # D-082: a temporary failure is tried again later; after 5 attempts it is Failed.
    email = queue_email(db_session, boards.gmc)
    retry = text(
        "update email_outbox set attempts = attempts + :step,"
        " next_attempt_at = now() + interval '5 minutes', last_error = 'Timeout' where id = :id"
    )

    with violates(db_session, "email_outbox_attempts_count_up"):
        db_session.execute(retry, {"step": 2, "id": email})
    for _ in range(5):
        db_session.execute(retry, {"step": 1, "id": email})
    with violates(db_session, "ck_email_outbox_attempts_range"):
        db_session.execute(retry, {"step": 1, "id": email})
    db_session.execute(
        text("update email_outbox set status = 'failed' where id = :id"), {"id": email}
    )


def test_a_failed_email_can_be_queued_again(boards: Boards, db_session: Session) -> None:
    # D-082: the super admin's Retry starts the attempts again.
    email = queue_email(db_session, boards.gmc)
    db_session.execute(
        text("update email_outbox set status = 'failed', attempts = 1 where id = :id"),
        {"id": email},
    )

    db_session.execute(
        text("update email_outbox set status = 'queued', attempts = 0 where id = :id"),
        {"id": email},
    )

    assert (
        db_session.scalar(text("select status from email_outbox where id = :id"), {"id": email})
        == "queued"
    )


@pytest.mark.parametrize(
    "change",
    [
        "to_address = 'someone.else@example.com'",
        "template_data = '{}'::jsonb",
        "idempotency_key = 'changed'",
    ],
)
def test_an_emails_content_never_changes(boards: Boards, db_session: Session, change: str) -> None:
    email = queue_email(db_session, boards.gmc)

    with violates(db_session, "email_outbox_content_kept"):
        db_session.execute(text(f"update email_outbox set {change} where id = :id"), {"id": email})  # noqa: S608


# --- row-level security and the four roles (D-137, D-153) -------------------------


def fill(session: Session, b: Boards) -> None:
    notice = ngozi_posts(session, b)
    add_notice_audience(session, b.gmc, notice)
    add_notice_recipient(session, b.gmc, notice, b.ikenna)
    as_user(session, b.gmc, b.ikenna)
    mark_notice_read(session, b.gmc, notice, b.ikenna)
    queue_email(session, b.gmc)
    queue_email(session, None, to_address="principal@example.com", email_type="account_activation")


def test_school_users_see_their_board(boards: Boards, db_session: Session) -> None:
    fill(db_session, boards)

    with acting_as(db_session, "app_user", school_id=boards.gmc):
        counts = {table: db_session.scalar(COUNT[table]) for table in NOTICE_TABLES}
        emails = db_session.scalar(text("select count(status) from email_outbox"))

    assert all(count >= 1 for count in counts.values())
    assert emails == 1  # the platform email is not GMC's


@pytest.mark.parametrize("table", NOTICE_TABLES)
def test_another_school_sees_none_of_these(boards: Boards, db_session: Session, table: str) -> None:
    # AC17.2.
    fill(db_session, boards)

    with acting_as(db_session, "app_user", school_id=boards.bsa):
        assert db_session.scalar(COUNT[table]) == 0


@pytest.mark.parametrize(
    "statement",
    [
        "select template_data from email_outbox",
        "update email_outbox set status = 'sent'",
        "delete from email_outbox",
        "delete from notices",
        "update notices set author_id = :user",
    ],
)
def test_school_users_see_email_status_only(
    boards: Boards, db_session: Session, statement: str
) -> None:
    # D-083: logs show status, never what an email says; sending is the sender's job.
    fill(db_session, boards)

    with (
        acting_as(db_session, "app_user", school_id=boards.gmc, user_id=boards.ngozi),
        refused(db_session),
    ):
        db_session.execute(text(statement), {"user": boards.ngozi})


def test_the_sender_reads_and_sends_every_schools_email(
    boards: Boards, db_session: Session
) -> None:
    # D-153: app_sender writes each email from its template data and marks it sent.
    fill(db_session, boards)
    as_user(db_session, boards.bsa, boards.chiamaka)
    queue_email(db_session, boards.bsa, to_address="kosi.parent@example.com")

    with acting_as(db_session, "app_sender"):
        queued = db_session.execute(
            text("select id, template_data from email_outbox where status = 'queued'")
        ).all()
        db_session.execute(
            SEND,
            {"status": "sent", "sent": "2026-10-14 12:00", "provider": "msg_1", "id": queued[0].id},
        )

    sent = db_session.scalar(
        text("select status from email_outbox where id = :id"), {"id": queued[0].id}
    )
    assert len(queued) == 3
    assert all(row.template_data for row in queued)
    assert sent == "sent"


@pytest.mark.parametrize(
    "statement",
    [
        "select count(*) from notices",
        "select count(*) from students",
        "select count(*) from report_documents",
        "update email_outbox set to_address = 'x@example.com'",
        "insert into email_outbox (type, to_address, template, template_data, idempotency_key)"
        " values ('x_y', 'a@example.com', 'x_y', '{}', 'k')",
    ],
)
def test_the_sender_does_nothing_else(boards: Boards, db_session: Session, statement: str) -> None:
    fill(db_session, boards)

    with acting_as(db_session, "app_sender"), refused(db_session):
        db_session.execute(text(statement))


def test_the_platform_sees_every_emails_status_only(boards: Boards, db_session: Session) -> None:
    # D-083: /platform/emails lists all emails, never their contents.
    fill(db_session, boards)
    admin = create_user(
        db_session, username="platform.admin", full_name="Platform Admin", is_super_admin=True
    )

    with acting_as(db_session, "app_platform", user_id=admin):
        statuses = list(db_session.scalars(text("select status from email_outbox")))
        queue_email(db_session, None, to_address="new.principal@example.com")
    with acting_as(db_session, "app_platform"), refused(db_session):
        db_session.execute(text("select template_data from email_outbox"))

    assert statuses == ["queued", "queued"]


@pytest.mark.parametrize("role", ["app_platform", "app_verifier"])
@pytest.mark.parametrize("table", NOTICE_TABLES)
def test_platform_and_verification_roles_cannot_read_notices(
    boards: Boards, db_session: Session, role: str, table: str
) -> None:
    fill(db_session, boards)

    with acting_as(db_session, role), refused(db_session):
        db_session.execute(COUNT[table])


def test_the_verification_role_cannot_read_emails(boards: Boards, db_session: Session) -> None:
    fill(db_session, boards)

    with acting_as(db_session, "app_verifier"), refused(db_session):
        db_session.execute(text("select count(*) from email_outbox"))
