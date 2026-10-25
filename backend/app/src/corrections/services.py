"""The correction queue (BUILD_PROMPT 9.2n; SPEC F15, section 8; AC15.1; D-151, D-174).

A "Report a problem" request is raised on a Valid report by a parent of the
pupil, or by staff for a class they teach, assist in or review (a school
admin for any class); pupils cannot (no `corrections.create`). It names a
subject or learning area that is on the report (or the whole report), an
issue type and an explanation, and the database numbers it per school
(shown as CR-0001). Only the requester and school admins see a request;
anyone else gets 404, as if it did not exist.

School admins (`corrections.manage`) move a request along SPEC section 8:
Open, Investigating, then Needs more information, Resolved or Rejected; the
requester answers "Needs more information", which returns it to
Investigating. Rejecting, asking, resolving and replying need a message. The
database checks every move again and writes the timeline. When a reopen
names the request (`publication`) and the pupil's corrected report is
republished, the request shows that revision, old against new (AC15.1); the
database stores the link once the request is Resolved, and resolving links
the newest correction whatever prompted it. The requester is emailed at each
step with the request's number and status only: never scores, and never the
school's message, which may quote them.

One attachment per request, added by the requester while it is Open or
Needs more information: an image (checked and re-saved without its metadata)
or a PDF with no scripts, launch actions or embedded files, up to 4 MB. It
is stored under a random key and downloaded, never shown in the page.
"""

import hashlib
import uuid
from typing import Any

from fastapi import UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import Principal, found
from app.core.errors import ProblemError
from app.core.permissions import Role
from app.platform.email.queue import queue_email
from app.platform.images import clean_image, sniff, too_large
from app.platform.storage import FileStorage
from app.src.audit.services import write_audit
from app.src.corrections.schemas import (
    Attachment,
    Average,
    Change,
    Event,
    LinkedReport,
    Move,
    NewRequest,
    RequestDetail,
    RequestRow,
    Requests,
    Score,
)
from app.src.files.models import ATTACHMENT_LIMIT_BYTES

TERM_NAMES = {1: "First Term", 2: "Second Term", 3: "Third Term"}
STEPS = {
    ("open", "investigating"),
    ("investigating", "needs_more_information"),
    ("investigating", "resolved"),
    ("investigating", "rejected"),
    ("needs_more_information", "investigating"),
}
CLOSED = ("resolved", "rejected")
# A PDF holding any of these can run code or carry other files; it is refused.
UNSAFE_PDF = (b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/RichMedia", b"/XFA")

SELECT = """
    select c.id, c.number, c.status, c.issue_type, c.explanation, c.status_message,
           c.requested_by, c.created_at, c.corrected_report_id, c.subject_id,
           c.learning_area_id, c.report_document_id,
           p.first_name || ' ' || p.surname as student_name,
           d.snapshot -> 'class' ->> 'name' as class_name, t.term_number,
           y.name as session_name, s.name as subject, la.name as learning_area,
           d.report_code, d.revision, u.full_name as requested_by_name
      from correction_requests c
      join report_documents d on d.id = c.report_document_id
      join enrolments e on e.id = d.enrolment_id
      join students p on p.id = e.student_id
      join terms t on t.id = d.term_id
      join academic_sessions y on y.id = t.session_id
      left join subjects s on s.id = c.subject_id
      left join learning_areas la on la.id = c.learning_area_id
      left join users u on u.id = c.requested_by
"""


def number(value: int) -> str:
    return f"CR-{value:04d}"


def is_admin(who: Principal) -> bool:
    return who.role is Role.SCHOOL_ADMIN


def as_row(r: Any) -> RequestRow:
    return RequestRow(
        id=str(r.id),
        number=number(r.number),
        status=r.status,
        issue_type=r.issue_type,
        student_name=r.student_name,
        class_name=r.class_name,
        term=f"{TERM_NAMES[r.term_number]} {r.session_name}",
        subject=r.subject,
        learning_area=r.learning_area,
        report_code=r.report_code,
        revision=r.revision,
        requested_by=r.requested_by_name,
        created_at=r.created_at,
    )


def load(session: Session, who: Principal, request_id: uuid.UUID) -> Any:
    """The request, if the signed-in person may see it (the requester or a school admin)."""
    return found(
        session.execute(
            text(f"{SELECT} where c.id = :id and (:admin or c.requested_by = :me)"),
            {"id": request_id, "admin": is_admin(who), "me": who.user_id},
        ).first()
    )


# --- raising a request --------------------------------------------------------------------------

# Staff raise requests for classes they teach, assist in or review.
STAFF_ARM = """(
    exists (select 1 from teacher_assignments ta where ta.arm_id = :arm and ta.teacher_id = :me)
    or exists (select 1 from class_assistants ca where ca.arm_id = :arm and ca.assistant_id = :me)
    or exists (select 1 from reviewer_scopes rs join class_arms a on a.id = :arm
               where rs.reviewer_id = :me
                 and (rs.class_id = a.class_id
                      or rs.subject_id in (select subject_id from arm_subjects where arm_id = :arm)
                      or rs.department_id in (select s.department_id from arm_subjects x
                                              join subjects s on s.id = x.subject_id
                                              where x.arm_id = :arm)))
)"""
WARD = """exists (select 1 from guardian_students gs join guardians g on g.id = gs.guardian_id
                  where gs.student_id = e.student_id and g.user_id = :me)"""


def raise_request(session: Session, who: Principal, body: NewRequest) -> RequestDetail:
    if who.role is Role.PARENT:
        allowed = WARD
    elif is_admin(who):
        allowed = "true"
    else:
        allowed = STAFF_ARM.replace(":arm", "d.arm_id")
    report = found(
        session.execute(
            text(
                "select d.id, d.status, d.snapshot from report_documents d"  # noqa: S608
                " join enrolments e on e.id = d.enrolment_id"
                f" where d.id = :r and {allowed}"
            ),
            {"r": body.report_id, "me": who.user_id},
        ).first()
    )
    if report.status != "valid":
        raise ProblemError(
            409, "Problems are reported on the current report.", code="report_not_valid"
        )
    snapshot = report.snapshot
    on_report_subjects = {s["subject_id"] for s in snapshot.get("subjects", [])}
    on_report_areas = {a["learning_area_id"] for a in snapshot.get("areas", [])}
    if (body.subject_id is not None and str(body.subject_id) not in on_report_subjects) or (
        body.learning_area_id is not None and str(body.learning_area_id) not in on_report_areas
    ):
        raise ProblemError(
            422, "That subject or learning area is not on this report.", code="not_on_report"
        )
    request_id = session.scalar(
        text(
            "insert into correction_requests (school_id, report_document_id, subject_id,"
            " learning_area_id, issue_type, explanation) values (:s, :r, :subject, :area,"
            " :issue, :why) returning id"
        ),
        {
            "s": who.school_id,
            "r": report.id,
            "subject": body.subject_id,
            "area": body.learning_area_id,
            "issue": body.issue_type,
            "why": body.explanation,
        },
    )
    write_audit(
        session,
        who.school_id,
        who.role.value,
        "corrections.create",
        target=("correction_requests", request_id),
        new={"report_id": str(report.id), "issue_type": body.issue_type},
    )
    return detail(session, who, request_id)


# --- reading ----------------------------------------------------------------------------------


def list_requests(session: Session, who: Principal, status: str | None) -> Requests:
    rows = session.execute(
        text(
            f"{SELECT} where (:admin or c.requested_by = :me)"
            " and (cast(:status as text) is null or c.status = :status)"
            " order by c.number desc"
        ),
        {"admin": is_admin(who), "me": who.user_id, "status": status},
    )
    requests = [as_row(r) for r in rows]
    still_open = session.scalar(
        text(
            "select count(*) from correction_requests where status not in ('resolved', 'rejected')"
            " and (:admin or requested_by = :me)"
        ),
        {"admin": is_admin(who), "me": who.user_id},
    )
    return Requests(open=int(still_open or 0), requests=requests)


def change_between(before: dict[str, Any], after: dict[str, Any], subject_id: Any) -> Change:
    def total(snapshot: dict[str, Any]) -> tuple[str, int | None] | None:
        for row in snapshot.get("subjects", []):
            if row["subject_id"] == str(subject_id):
                return row["name"], row["total"]
        return None

    subject = None
    if subject_id is not None:
        old, new = total(before), total(after)
        if old is not None:
            subject = Score(name=old[0], before=old[1], after=new[1] if new else None)

    def mean(snapshot: dict[str, Any]) -> str | None:
        summary: dict[str, Any] = snapshot.get("summary") or {}
        value: str | None = summary.get("average")
        return value

    average = Average(before=mean(before), after=mean(after))
    return Change(subject=subject, average=average)


def detail(session: Session, who: Principal, request_id: uuid.UUID) -> RequestDetail:
    r = load(session, who, request_id)
    events = [
        Event(
            from_status=e.from_status,
            to_status=e.to_status,
            actor_name=e.actor_name,
            message=e.message,
            created_at=e.created_at,
        )
        for e in session.execute(
            text(
                "select ev.from_status, ev.to_status, u.full_name as actor_name, ev.message,"
                " ev.created_at from correction_events ev left join users u on u.id = ev.actor_id"
                " where ev.request_id = :id order by ev.created_at, ev.id"
            ),
            {"id": r.id},
        )
    ]
    file = session.execute(
        text(
            "select f.content_type, f.size_bytes, f.original_name from correction_attachments a"
            " join files f on f.id = a.file_id where a.request_id = :id"
        ),
        {"id": r.id},
    ).first()
    linked = change = None
    if r.corrected_report_id is not None:
        fixed = session.execute(
            text(
                "select id, report_code, revision, status, published_at, snapshot"
                " from report_documents where id = :id"
            ),
            {"id": r.corrected_report_id},
        ).one()
    else:
        fixed = newer_revision(session, r, named_only=True)
    if fixed is not None:
        linked = LinkedReport(
            id=str(fixed.id),
            report_code=fixed.report_code,
            revision=fixed.revision,
            status=fixed.status,
            published_at=fixed.published_at,
        )
        original = session.scalar(
            text("select snapshot from report_documents where id = :id"),
            {"id": r.report_document_id},
        )
        change = change_between(original, fixed.snapshot, r.subject_id)
    return RequestDetail(
        **as_row(r).model_dump(),
        explanation=r.explanation,
        status_message=r.status_message,
        events=events,
        attachment=Attachment(
            content_type=file.content_type,
            size_bytes=file.size_bytes,
            original_name=file.original_name,
        )
        if file
        else None,
        corrected_report=linked,
        change=change,
    )


# --- moving a request ---------------------------------------------------------------------------


def move_request(
    session: Session, who: Principal, request_id: uuid.UUID, body: Move
) -> RequestDetail:
    r = load(session, who, request_id)
    reply = r.status == "needs_more_information" and body.status == "investigating"
    if reply and r.requested_by != who.user_id:
        raise ProblemError(
            403, "Only the person who sent the request replies.", code="requester_replies"
        )
    if not reply and "corrections.manage" not in who.permissions:
        raise ProblemError(403, "You don't have permission to do this.", code="permission_denied")
    if (r.status, body.status) not in STEPS:
        raise ProblemError(
            409, f"A request cannot move from {r.status} to {body.status}.", code="wrong_status"
        )
    needs_message = body.status in ("needs_more_information", "resolved", "rejected") or reply
    if needs_message and body.message is None:
        raise ProblemError(422, "This step needs a message.", code="message_required")
    fix = newer_revision(session, r, named_only=False) if body.status == "resolved" else None
    session.execute(
        text(
            "update correction_requests set status = :to, status_message = :m,"
            " corrected_report_id = :fix where id = :id"
        ),
        {"to": body.status, "m": body.message, "fix": fix.id if fix else None, "id": r.id},
    )
    write_audit(
        session,
        who.school_id,
        who.role.value,
        f"corrections.{body.status}",
        target=("correction_requests", r.id),
        old={"status": r.status},
        new={"status": body.status},
        reason=body.message,
    )
    tell_the_requester(session, who, r, body.status)
    return detail(session, who, request_id)


def tell_the_requester(session: Session, who: Principal, r: Any, status: str) -> None:
    """The requester's email: the number and the new status, never scores or the message."""
    if r.requested_by == who.user_id:
        return
    on = session.scalar(
        text("select enabled from school_features where feature = 'email_notifications'")
    )
    person = session.execute(
        text("select full_name, email from users where id = :u and email is not null"),
        {"u": r.requested_by},
    ).first()
    if not on or person is None:
        return
    school_name = session.scalar(
        text("select name from schools where id = :s"), {"s": who.school_id}
    )
    queue_email(
        session,
        who.school_id,
        "correction_updated",
        person.email,
        {
            "full_name": person.full_name,
            "school_name": school_name,
            "number": number(r.number),
            "status": status,
            "login_path": "/login",
        },
        priority=5,
    )


def newer_revision(session: Session, r: Any, *, named_only: bool) -> Any:
    """The pupil's newest Valid revision after the reported one, for that term.

    While a request is open it counts only when a reopen named the request
    (AC15.1); when the request is resolved, the newest correction is linked
    whatever prompted it. The database allows the stored link only once the
    request is Resolved.
    """
    return session.execute(
        text(
            "select n.id, n.report_code, n.revision, n.status, n.published_at, n.snapshot"
            " from report_documents n join report_documents o on o.id = :original"
            " where n.enrolment_id = o.enrolment_id and n.term_id = o.term_id"
            " and n.revision > o.revision and n.status = 'valid'"
            " and (not :named or exists (select 1 from audit_events a"
            "   where a.action = 'results.reopen'"
            "   and a.new_values ->> 'correction_request_id' = :request))"
            " order by n.revision desc limit 1"
        ),
        {"original": r.report_document_id, "named": named_only, "request": str(r.id)},
    ).first()


# --- the attachment -----------------------------------------------------------------------------


def checked_pdf(data: bytes) -> bytes:
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-1024:]:
        raise unsupported_attachment()
    if any(token in data for token in UNSAFE_PDF):
        raise ProblemError(
            415, "This PDF holds scripts or other files. Save it again as plain PDF.",
            code="unsafe_pdf",
        )  # fmt: skip
    return data


def unsupported_attachment() -> ProblemError:
    return ProblemError(415, "Attach a PNG, JPEG or WebP image or a PDF.", code="unsupported_file")


def add_attachment(
    session: Session, who: Principal, request_id: uuid.UUID, file: UploadFile, storage: FileStorage
) -> Attachment:
    r = load(session, who, request_id)
    if r.requested_by != who.user_id:
        raise ProblemError(
            403, "Only the person who sent the request adds an attachment.",
            code="requester_attaches",
        )  # fmt: skip
    if r.status not in ("open", "needs_more_information"):
        raise ProblemError(
            409, "Attachments are added while the request is open.", code="wrong_status"
        )
    if session.scalar(
        text("select exists (select 1 from correction_attachments where request_id = :id)"),
        {"id": r.id},
    ):
        raise ProblemError(409, "This request already has an attachment.", code="already_attached")
    data = file.file.read(ATTACHMENT_LIMIT_BYTES + 1)
    if len(data) > ATTACHMENT_LIMIT_BYTES:
        raise too_large(ATTACHMENT_LIMIT_BYTES)
    if data.startswith(b"%PDF-"):
        content, content_type, extension = checked_pdf(data), "application/pdf", "pdf"
    elif sniff(data) is not None:
        try:
            image = clean_image(data, ATTACHMENT_LIMIT_BYTES)
        except ProblemError as error:
            if error.code == "unsupported_file":
                raise unsupported_attachment() from None
            raise
        content, content_type, extension = image.data, image.content_type, image.extension
    else:
        raise unsupported_attachment()
    name = (file.filename or "attachment").strip()[:200] or "attachment"
    key = f"schools/{who.school_id}/correction_attachment/{uuid.uuid4().hex}.{extension}"
    storage.put(key, content, content_type)
    file_id = session.scalar(
        text(
            "insert into files (school_id, purpose, storage_key, content_type, size_bytes,"
            " sha256, original_name) values (:s, 'correction_attachment', :key, :type, :size,"
            " :sha, :name) returning id"
        ),
        {
            "s": who.school_id,
            "key": key,
            "type": content_type,
            "size": len(content),
            "sha": hashlib.sha256(content).digest(),
            "name": name,
        },
    )
    session.execute(
        text(
            "insert into correction_attachments (school_id, request_id, file_id)"
            " values (:s, :r, :f)"
        ),
        {"s": who.school_id, "r": r.id, "f": file_id},
    )
    write_audit(
        session,
        who.school_id,
        who.role.value,
        "corrections.attach",
        target=("correction_requests", r.id),
        new={"content_type": content_type, "size_bytes": len(content)},
    )
    return Attachment(content_type=content_type, size_bytes=len(content), original_name=name)


def attachment_file(
    session: Session, who: Principal, request_id: uuid.UUID, storage: FileStorage
) -> tuple[bytes, str, str]:
    """(bytes, content type, download name) for the requester or a school admin."""
    r = load(session, who, request_id)
    row = found(
        session.execute(
            text(
                "select f.storage_key, f.content_type from correction_attachments a"
                " join files f on f.id = a.file_id where a.request_id = :id"
            ),
            {"id": r.id},
        ).first()
    )
    extension = row.storage_key.rsplit(".", 1)[-1]
    return (
        storage.get(row.storage_key),
        row.content_type,
        f"{number(r.number)}-attachment.{extension}",
    )
