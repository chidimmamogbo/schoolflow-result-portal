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
"""

import secrets
import uuid
from typing import Annotated, Any, Literal, Self

from fastapi import APIRouter, Depends
from pydantic import Field, StringConstraints, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import DbSession, Principal, found, require
from app.core.errors import ProblemError
from app.core.schemas import ApiModel
from app.core.security import issue_temporary_password
from app.platform.email.queue import queue_email
from app.src.audit.services import write_audit
from app.src.platform_admin.schemas import Detail, Email, Line, Username

router = APIRouter(prefix="/school", tags=["school"])

Member = Annotated[Principal, Depends(require())]
Admin = Annotated[Principal, Depends(require("guardian_links.manage"))]

Relationship = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Phone = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9][0-9 ()-]{5,19}$")
]
LINK_DAYS = 14  # SPEC section 12


class WardLink(ApiModel):
    student_id: uuid.UUID
    relationship: Relationship


class NewGuardian(ApiModel):
    full_name: Line
    phone: Phone | None = None
    email: Email | None = None
    wards: Annotated[list[WardLink], Field(min_length=1, max_length=20)]
    login: Literal["link_request", "temporary_password", "none"]
    username: Username | None = None

    @model_validator(mode="after")
    def login_fits_the_email(self) -> Self:
        if self.email is not None and self.login != "link_request":
            raise ValueError("A parent with an email is added by a link request (D-140).")
        if self.email is None and self.login == "link_request":
            raise ValueError("A link request needs an email.")
        if self.login == "temporary_password" and self.username is None:
            raise ValueError("A login slip needs a username.")
        return self


class EditGuardian(ApiModel):
    full_name: Line | None = None
    phone: Phone | None = None
    privacy_consent: bool | None = None


class WardRow(ApiModel):
    student_id: str
    name: str
    relationship: str


class GuardianRow(ApiModel):
    id: str
    full_name: str
    phone: str | None
    email: str | None
    login_status: Literal["none", "waiting", "linked", "paused"]
    wards: list[WardRow]


class GuardianCreated(ApiModel):
    id: str
    login_status: str
    # Shown once, only for a parent without an email (D-140).
    temporary_password: str | None


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


# --- routes -----------------------------------------------------------------------------


@router.get("/guardians", response_model=list[GuardianRow])
def list_guardians(_: Member, session: DbSession) -> list[GuardianRow]:
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


@router.post("/guardians", status_code=201, response_model=GuardianCreated)
def create_guardian(body: NewGuardian, who: Admin, session: DbSession) -> GuardianCreated:
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


@router.patch("/guardians/{guardian_id}", response_model=GuardianRow)
def edit_guardian(
    guardian_id: uuid.UUID, body: EditGuardian, who: Admin, session: DbSession
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


@router.post("/guardians/{guardian_id}/wards", status_code=201, response_model=Detail)
def add_ward(guardian_id: uuid.UUID, body: WardLink, who: Admin, session: DbSession) -> Detail:
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


@router.delete("/guardians/{guardian_id}/wards/{student_id}", status_code=204)
def remove_ward(
    guardian_id: uuid.UUID, student_id: uuid.UUID, who: Admin, session: DbSession
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


@router.post("/guardians/{guardian_id}/link-request/resend", status_code=202, response_model=Detail)
def resend_link_request(guardian_id: uuid.UUID, who: Admin, session: DbSession) -> Detail:
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


@router.delete("/guardians/{guardian_id}/link-request", status_code=204)
def cancel_link_request(guardian_id: uuid.UUID, who: Admin, session: DbSession) -> None:
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


@router.post("/guardians/{guardian_id}/pause", status_code=204)
def pause_link(guardian_id: uuid.UUID, who: Admin, session: DbSession) -> None:
    set_link_status(session, who, guardian_id, "paused")


@router.post("/guardians/{guardian_id}/resume", status_code=204)
def resume_link(guardian_id: uuid.UUID, who: Admin, session: DbSession) -> None:
    set_link_status(session, who, guardian_id, "active")


@router.delete("/guardians/{guardian_id}/login", status_code=204)
def remove_link(guardian_id: uuid.UUID, who: Admin, session: DbSession) -> None:
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
