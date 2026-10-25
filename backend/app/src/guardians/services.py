"""Parents as the school knows them: guardians, wards and link requests.

SPEC F03, F07; D-138, D-140.

- The school records a guardian (name, phone, the email it was given) with
  one or more wards and the relationship to each.
- A parent with an email is always added by a link request (D-140). The
  school's side is identical for every email: it never looks the email up,
  so it cannot tell a new person from another school's parent or a teacher
  (option 2A, AC03.7, AC03.10). The emailed link is made by the sender at
  send time (D-081), which also decides what the email says; the stored
  hash is replaced then.
- A slip (temporary password) is only for a parent without an email.
- The school pauses, resumes or removes only its own link; the account
  itself, when shared with another school, is the parent's (D-138).

A parent answers schools' link requests (D-138, D-140; AT-31.4, AT-31.5, AC03.8).

The requests belong to the schools that sent them, so the signed-in parent
reads and answers them through the narrow owner-run functions of migration
24, which match the request's email with the parent's own verified email.
Anyone else, a teacher or a pupil included, sees nothing and gets "not
found". Accepting adds a parent link to that school at once.
"""

import secrets
import uuid
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import Principal, found
from app.core.errors import ProblemError
from app.core.security import issue_temporary_password
from app.platform.email.queue import queue_email
from app.src.audit.services import write_audit
from app.src.guardians.schemas import (
    Accepted,
    EditGuardian,
    GuardianCreated,
    GuardianRow,
    LinkRequestRow,
    NewGuardian,
    WardLink,
    WardRow,
)
from app.src.platform_admin.schemas import Detail

LINK_DAYS = 14  # SPEC section 12


# --- helpers ------------------------------------------------------------------------------
def audit(session: Session, who: Principal, action: str, **details: Any) -> None:
    write_audit(session, who.school_id, who.role.value, action, **details)


def link_ward(session: Session, who: Principal, guardian_id: uuid.UUID, ward: WardLink) -> None:
    found(session.scalar(text("select id from students where id = :s"), {"s": ward.student_id}))
    try:
        with session.begin_nested():
            session.execute(
                text(
                    "insert into guardian_students (school_id, guardian_id, student_id,"
                    " relationship) values (:school, :g, :s, :r)"
                ),
                {
                    "school": who.school_id,
                    "g": guardian_id,
                    "s": ward.student_id,
                    "r": ward.relationship,
                },
            )
    except IntegrityError:
        raise ProblemError(
            409, "This pupil is already linked to this parent.", code="already_linked"
        ) from None


def send_link_request(
    session: Session, who: Principal, guardian_id: uuid.UUID, email: str, name: str
) -> None:
    """A new request and its email; the real link is made at send time (D-081)."""
    request_id: uuid.UUID = session.scalar(
        text(
            "insert into parent_link_requests (school_id, guardian_id, email, token_hash,"
            " expires_at) values (:s, :g, :e, :h, now() + make_interval(days => :days))"
            " returning id"
        ),
        # A placeholder hash nobody holds the token for; the sender replaces it.
        {
            "s": who.school_id,
            "g": guardian_id,
            "e": email,
            "h": secrets.token_bytes(32),
            "days": LINK_DAYS,
        },
    )
    school_name = session.scalar(
        text("select name from schools where id = :s"), {"s": who.school_id}
    )
    queue_email(
        session,
        who.school_id,
        "parent_link_request",
        email,
        {"link_request_id": str(request_id), "school_name": school_name, "guardian_name": name},
    )


GUARDIAN_SELECT = (
    "select g.id, g.full_name, g.phone, g.email, g.user_id, m.status as membership_status,"
    " exists (select 1 from parent_link_requests r where r.guardian_id = g.id"
    "   and r.accepted_at is null and r.declined_at is null and r.cancelled_at is null"
    "   and r.expires_at > now()) as waiting"
    " from guardians g left join school_memberships m"
    "   on m.user_id = g.user_id and m.school_id = g.school_id"
)


def status_of(r: Any) -> Literal["none", "waiting", "linked", "paused"]:
    if r.user_id is not None:
        return "paused" if r.membership_status == "paused" else "linked"
    return "waiting" if r.waiting else "none"


def load_guardian(session: Session, guardian_id: uuid.UUID) -> Any:
    return found(
        session.execute(text(f"{GUARDIAN_SELECT} where g.id = :id"), {"id": guardian_id}).first()
    )


def list_guardians(
    _: Principal,
    session: Session,
) -> list[GuardianRow]:
    wards: dict[uuid.UUID, list[WardRow]] = {}
    for w in session.execute(
        text(
            "select gs.guardian_id, gs.student_id, gs.relationship,"
            " s.first_name || ' ' || s.surname as name from guardian_students gs"
            " join students s on s.id = gs.student_id order by s.surname, s.first_name"
        )
    ):
        wards.setdefault(w.guardian_id, []).append(
            WardRow(student_id=str(w.student_id), name=w.name, relationship=w.relationship)
        )
    return [
        GuardianRow(
            id=str(r.id),
            full_name=r.full_name,
            phone=r.phone,
            email=r.email,
            login_status=status_of(r),
            wards=wards.get(r.id, []),
        )
        for r in session.execute(text(f"{GUARDIAN_SELECT} order by g.full_name, g.id"))
    ]


def create_guardian(
    body: NewGuardian,
    who: Principal,
    session: Session,
) -> GuardianCreated:
    guardian_id: uuid.UUID = session.scalar(
        text(
            "insert into guardians (school_id, full_name, phone, email)"
            " values (:s, :n, :p, :e) returning id"
        ),
        {"s": who.school_id, "n": body.full_name, "p": body.phone, "e": body.email},
    )
    for ward in body.wards:
        link_ward(session, who, guardian_id, ward)
    temporary = None
    if body.login == "link_request" and body.email is not None:
        send_link_request(session, who, guardian_id, body.email, body.full_name)
    elif body.login == "temporary_password":
        user_id = uuid.uuid4()
        try:
            with session.begin_nested():
                session.execute(
                    text("insert into users (id, full_name, username) values (:id, :n, :u)"),
                    {"id": user_id, "n": body.full_name, "u": body.username},
                )
        except IntegrityError:
            raise ProblemError(409, "This username is taken.", code="username_taken") from None
        session.execute(
            text(
                "insert into school_memberships (user_id, school_id, role, status)"
                " values (:u, :s, 'parent', 'active')"
            ),
            {"u": user_id, "s": who.school_id},
        )
        session.execute(
            text("update guardians set user_id = :u where id = :g"),
            {"u": user_id, "g": guardian_id},
        )
        temporary = issue_temporary_password(session, user_id)
    audit(
        session,
        who,
        "guardians.create",
        target=("guardians", guardian_id),
        new={"login": body.login, "wards": len(body.wards)},
    )
    return GuardianCreated(
        id=str(guardian_id),
        login_status=status_of(load_guardian(session, guardian_id)),
        temporary_password=temporary,
    )


def edit_guardian(
    guardian_id: uuid.UUID,
    body: EditGuardian,
    who: Principal,
    session: Session,
) -> GuardianRow:
    current = load_guardian(session, guardian_id)
    changes: dict[str, Any] = body.model_dump(exclude_unset=True, exclude={"privacy_consent"})
    if changes:
        assignments = ", ".join(f"{field} = :{field}" for field in changes)
        session.execute(
            text(f"update guardians set {assignments} where id = :id"),  # noqa: S608
            {**changes, "id": guardian_id},
        )
    if body.privacy_consent is not None:
        session.execute(
            text(
                "update guardians set privacy_consent_at = case when :c then now() end"
                " where id = :id"
            ),
            {"c": body.privacy_consent, "id": guardian_id},
        )
    audit(
        session,
        who,
        "guardians.update",
        target=("guardians", guardian_id),
        old={k: getattr(current, k) for k in changes},
        new=body.model_dump(exclude_unset=True),
    )
    return next(g for g in list_guardians(who, session) if g.id == str(guardian_id))


def add_ward(
    guardian_id: uuid.UUID,
    body: WardLink,
    who: Principal,
    session: Session,
) -> Detail:
    load_guardian(session, guardian_id)
    link_ward(session, who, guardian_id, body)
    audit(
        session,
        who,
        "guardian_links.create",
        target=("guardians", guardian_id),
        new={"student_id": str(body.student_id), "relationship": body.relationship},
    )
    return Detail(detail="Linked.")


def remove_ward(
    guardian_id: uuid.UUID,
    student_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> None:
    found(
        session.scalar(
            text(
                "delete from guardian_students where guardian_id = :g and student_id = :s"
                " returning id"
            ),
            {"g": guardian_id, "s": student_id},
        )
    )
    audit(
        session,
        who,
        "guardian_links.delete",
        target=("guardians", guardian_id),
        old={"student_id": str(student_id)},
    )


def open_request(session: Session, guardian_id: uuid.UUID) -> uuid.UUID | None:
    return session.scalar(
        text(
            "select id from parent_link_requests where guardian_id = :g and accepted_at is null"
            " and declined_at is null and cancelled_at is null"
        ),
        {"g": guardian_id},
    )


def resend_link_request(
    guardian_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> Detail:
    current = load_guardian(session, guardian_id)
    if current.user_id is not None or current.email is None:
        raise ProblemError(409, "This parent has no link request to send.", code="no_link_request")
    waiting = open_request(session, guardian_id)
    if waiting is not None:
        session.execute(
            text("update parent_link_requests set cancelled_at = now() where id = :r"),
            {"r": waiting},
        )
    send_link_request(session, who, guardian_id, current.email, current.full_name)
    audit(session, who, "guardians.link_request", target=("guardians", guardian_id))
    return Detail(detail="Link request sent again.")


def cancel_link_request(
    guardian_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> None:
    load_guardian(session, guardian_id)
    waiting = found(open_request(session, guardian_id))
    session.execute(
        text("update parent_link_requests set cancelled_at = now() where id = :r"), {"r": waiting}
    )
    audit(session, who, "guardians.cancel_link_request", target=("guardians", guardian_id))


def linked_user(session: Session, guardian_id: uuid.UUID) -> uuid.UUID:
    current = load_guardian(session, guardian_id)
    if current.user_id is None:
        raise ProblemError(409, "This parent has no login linked to the school.", code="no_login")
    return current.user_id


def set_link_status(session: Session, who: Principal, guardian_id: uuid.UUID, status: str) -> None:
    user_id = linked_user(session, guardian_id)
    session.execute(
        text(
            "update school_memberships set status = :st where user_id = :u"
            " and school_id = app_current_school_id() and role = 'parent'"
        ),
        {"st": status, "u": user_id},
    )
    audit(
        session,
        who,
        f"guardians.{'pause' if status == 'paused' else 'resume'}",
        target=("guardians", guardian_id),
    )


def pause_link(
    guardian_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> None:
    set_link_status(session, who, guardian_id, "paused")


def resume_link(
    guardian_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> None:
    set_link_status(session, who, guardian_id, "active")


def remove_link(
    guardian_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> None:
    """Ends this school's link only; the parent's account and other schools' links stay."""
    user_id = linked_user(session, guardian_id)
    session.execute(text("update guardians set user_id = null where id = :g"), {"g": guardian_id})
    session.execute(
        text(
            "delete from school_memberships where user_id = :u"
            " and school_id = app_current_school_id() and role = 'parent'"
        ),
        {"u": user_id},
    )
    audit(session, who, "guardians.remove_login", target=("guardians", guardian_id))


def my_link_requests(
    _: Principal,
    session: Session,
) -> list[LinkRequestRow]:
    return [
        LinkRequestRow(
            id=str(r.id),
            school_id=str(r.school_id),
            school_name=r.school_name,
            school_code=r.school_code,
            guardian_name=r.guardian_name,
            created_at=r.created_at,
            expires_at=r.expires_at,
        )
        for r in session.execute(text("select * from my_parent_link_requests()"))
    ]


def accept(
    request_id: uuid.UUID,
    _: Principal,
    session: Session,
) -> Accepted:
    school_id = found(
        session.scalar(text("select accept_parent_link_request(:r)"), {"r": request_id})
    )
    return Accepted(school_id=str(school_id))


def decline(
    request_id: uuid.UUID,
    _: Principal,
    session: Session,
) -> None:
    if not session.scalar(text("select decline_parent_link_request(:r)"), {"r": request_id}):
        found(None)
