"""Teachers, reviewers and what they teach or review (BUILD_PROMPT 9.2e; SPEC F03, F06; D-144).

- Staff accounts: school admins create teachers and reviewers (an activation
  email, or a temporary password slip shown once) and edit their name and
  email. School admins are managed on the admins page; parents and pupils
  with their own pages (next part).
- Assignments (`assignments.manage`): a subject in an arm, a learning area
  in an arm, or the arm's form teacher (optionally "Teaches all subjects");
  class teacher assistants (at most two per arm); reviewer scopes (a
  department, or subjects and/or classes).
- The database enforces the rest (one teacher per subject per arm, only
  subjects the arm takes, one form teacher per arm and per teacher, staff
  only, at most two assistants, reviewers only) and its rule names come back
  as the error `code`. Ids are first looked up in the school, so another
  school's id is not found (404); an arm at a level that is off is refused.
"""

import uuid
from typing import Annotated, Any, Literal, Self

import psycopg
from fastapi import APIRouter, Depends, Query
from pydantic import model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import DbSession, Principal, ensure_level_enabled, found, require
from app.core.errors import ProblemError
from app.core.schemas import ApiModel
from app.core.security import issue_temporary_password
from app.platform.email.queue import queue_email
from app.src.accounts.router import activation_data
from app.src.audit.services import write_audit
from app.src.platform_admin.schemas import Email, Line, Username
from app.src.schools.models import Level
from app.src.schools.schemas import CreatedAdmin

router = APIRouter(prefix="/school", tags=["school"])

Member = Annotated[Principal, Depends(require())]
CreateUsers = Annotated[Principal, Depends(require("users.create"))]
Assign = Annotated[Principal, Depends(require("assignments.manage"))]

TAKEN = {
    "ix_users_username_platform": ("This username is taken.", "username_taken"),
    "uq_users_email": ("This email is already used.", "email_taken"),
}


# --- shapes -------------------------------------------------------------------------------


class NewStaff(ApiModel):
    full_name: Line
    username: Username
    email: Email | None = None
    role: Literal["teacher", "reviewer"]
    login_method: Literal["activation", "temporary_password"]

    @model_validator(mode="after")
    def activation_needs_email(self) -> Self:
        if self.login_method == "activation" and self.email is None:
            raise ValueError("An activation email needs an email address.")
        return self


class EditStaff(ApiModel):
    full_name: Line | None = None
    email: Email | None = None


class StaffRow(ApiModel):
    id: str
    full_name: str
    username: str
    email: str | None
    role: str
    is_active: bool
    activated: bool


class NewAssignment(ApiModel):
    teacher_id: uuid.UUID
    arm_id: uuid.UUID
    subject_id: uuid.UUID | None = None
    learning_area_id: uuid.UUID | None = None
    is_form_teacher: bool = False
    teaches_all_subjects: bool = False

    @model_validator(mode="after")
    def one_kind(self) -> Self:
        kinds = (self.subject_id is not None) + (self.learning_area_id is not None)
        if kinds + self.is_form_teacher != 1:
            raise ValueError("Give a subject, a learning area, or make them the form teacher.")
        if self.teaches_all_subjects and not self.is_form_teacher:
            raise ValueError("Only the form teacher can teach all subjects.")
        return self


class AssignmentRow(ApiModel):
    id: str
    teacher_id: str
    teacher_name: str
    arm_id: str
    subject_id: str | None
    learning_area_id: str | None
    is_form_teacher: bool
    teaches_all_subjects: bool


class NewAssistant(ApiModel):
    user_id: uuid.UUID


class AssistantRow(ApiModel):
    user_id: str
    full_name: str
    username: str


class NewScope(ApiModel):
    department_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    class_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def department_or_subjects(self) -> Self:
        if (self.department_id is not None) == (
            self.subject_id is not None or self.class_id is not None
        ):
            raise ValueError("Give a whole department, or subjects and/or classes.")
        return self


class ScopeRow(ApiModel):
    id: str
    department_id: str | None
    subject_id: str | None
    class_id: str | None


# --- helpers -----------------------------------------------------------------------------


def in_school(session: Session, table: str, row_id: uuid.UUID | None) -> uuid.UUID | None:
    """The id if this school can see that row (row-level security), else 404."""
    if row_id is None:
        return None
    return found(
        session.scalar(text(f"select id from {table} where id = :id"), {"id": row_id})  # noqa: S608 (fixed names)
    )


def member_of_school(session: Session, user_id: uuid.UUID) -> uuid.UUID:
    return found(
        session.scalar(
            text(
                "select user_id from school_memberships where user_id = :u"
                " and school_id = app_current_school_id()"
            ),
            {"u": user_id},
        )
    )


def arm_level_on(session: Session, who: Principal, arm_id: uuid.UUID) -> None:
    level = session.scalar(
        text(
            "select c.level from class_arms a join classes c on c.id = a.class_id where a.id = :arm"
        ),
        {"arm": arm_id},
    )
    ensure_level_enabled(session, who, Level(found(level)))


def audit(session: Session, who: Principal, action: str, **details: Any) -> None:
    write_audit(session, who.school_id, who.role.value, action, **details)


# --- staff accounts ----------------------------------------------------------------------


STAFF_SELECT = (
    "select u.id, u.full_name, u.username, u.email, m.role, u.is_active,"
    " u.password_hash is not null as activated"
    " from school_memberships m join users u on u.id = m.user_id"
    " where m.school_id = app_current_school_id() and m.role in ('teacher', 'reviewer')"
)


def staff_row(r: Any) -> StaffRow:
    return StaffRow(
        id=str(r.id),
        full_name=r.full_name,
        username=r.username,
        email=r.email,
        role=r.role,
        is_active=r.is_active,
        activated=r.activated,
    )


@router.get("/staff", response_model=list[StaffRow])
def list_staff(
    _: Member,
    session: DbSession,
    role: Annotated[Literal["teacher", "reviewer"] | None, Query()] = None,
) -> list[StaffRow]:
    rows = session.execute(
        text(
            f"{STAFF_SELECT} and (cast(:role as text) is null or m.role = :role)"
            " order by u.full_name"
        ),
        {"role": role},
    )
    return [staff_row(r) for r in rows]


@router.post("/staff", status_code=201, response_model=CreatedAdmin)
def create_staff(body: NewStaff, who: CreateUsers, session: DbSession) -> CreatedAdmin:
    user_id = uuid.uuid4()
    try:
        with session.begin_nested():
            session.execute(
                text(
                    "insert into users (id, full_name, username, email)"
                    " values (:id, :full_name, :username, :email)"
                ),
                {
                    "id": user_id,
                    "full_name": body.full_name,
                    "username": body.username,
                    "email": body.email,
                },
            )
    except IntegrityError as error:
        original = error.orig
        rule = original.diag.constraint_name if isinstance(original, psycopg.Error) else None
        if rule in TAKEN:
            title, code = TAKEN[rule]
            raise ProblemError(409, title, code=code) from None
        raise
    session.execute(
        text(
            "insert into school_memberships (user_id, school_id, role, status)"
            " values (:u, :s, :role, 'active')"
        ),
        {"u": user_id, "s": who.school_id, "role": body.role},
    )
    temporary = None
    if body.login_method == "activation" and body.email is not None:
        queue_email(
            session, who.school_id, "activation", body.email, activation_data(session, user_id)
        )
    else:
        temporary = issue_temporary_password(session, user_id)
    audit(
        session,
        who,
        "users.create",
        target=("users", user_id),
        new={"username": body.username, "role": body.role, "login_method": body.login_method},
    )
    return CreatedAdmin(id=str(user_id), temporary_password=temporary)


@router.patch("/staff/{user_id}", response_model=StaffRow)
def edit_staff(
    user_id: uuid.UUID, body: EditStaff, who: CreateUsers, session: DbSession
) -> StaffRow:
    current = found(
        session.execute(text(f"{STAFF_SELECT} and u.id = :id"), {"id": user_id}).first()
    )
    changes = body.model_dump(exclude_none=True)
    changes = {k: v for k, v in changes.items() if getattr(current, k) != v}
    if changes:
        try:
            with session.begin_nested():
                session.execute(
                    text(
                        "update users set full_name = coalesce(:full_name, full_name),"
                        " email = coalesce(:email, email),"
                        " email_verified_at = case when cast(:email as text) is null"
                        "     then email_verified_at else null end"
                        " where id = :id"
                    ),
                    {
                        "full_name": changes.get("full_name"),
                        "email": changes.get("email"),
                        "id": user_id,
                    },
                )
        except IntegrityError:
            # The email belongs to another account (perhaps in a school we cannot see).
            raise ProblemError(409, "This email is already used.", code="email_taken") from None
        audit(
            session,
            who,
            "users.update",
            target=("users", user_id),
            old={k: getattr(current, k) for k in changes},
            new=changes,
        )
    return staff_row(session.execute(text(f"{STAFF_SELECT} and u.id = :id"), {"id": user_id}).one())


# --- assignments -------------------------------------------------------------------------


ASSIGNMENT_SELECT = (
    "select t.id, t.teacher_id, u.full_name as teacher_name, t.arm_id, t.subject_id,"
    " t.learning_area_id, t.is_form_teacher, t.teaches_all_subjects"
    " from teacher_assignments t join users u on u.id = t.teacher_id"
)


def assignment_row(r: Any) -> AssignmentRow:
    return AssignmentRow(
        id=str(r.id),
        teacher_id=str(r.teacher_id),
        teacher_name=r.teacher_name,
        arm_id=str(r.arm_id),
        subject_id=str(r.subject_id) if r.subject_id else None,
        learning_area_id=str(r.learning_area_id) if r.learning_area_id else None,
        is_form_teacher=r.is_form_teacher,
        teaches_all_subjects=r.teaches_all_subjects,
    )


@router.get("/assignments", response_model=list[AssignmentRow])
def list_assignments(
    _: Member,
    session: DbSession,
    arm_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
) -> list[AssignmentRow]:
    rows = session.execute(
        text(
            f"{ASSIGNMENT_SELECT}"
            " where (cast(:arm as uuid) is null or t.arm_id = :arm)"
            " and (cast(:teacher as uuid) is null or t.teacher_id = :teacher)"
            " order by u.full_name, t.id"
        ),
        {"arm": arm_id, "teacher": teacher_id},
    )
    return [assignment_row(r) for r in rows]


@router.post("/assignments", status_code=201, response_model=AssignmentRow)
def create_assignment(body: NewAssignment, who: Assign, session: DbSession) -> AssignmentRow:
    arm = found(in_school(session, "class_arms", body.arm_id))
    member_of_school(session, body.teacher_id)
    in_school(session, "subjects", body.subject_id)
    in_school(session, "learning_areas", body.learning_area_id)
    arm_level_on(session, who, arm)
    assignment_id: uuid.UUID = session.scalar(
        text(
            "insert into teacher_assignments (school_id, teacher_id, arm_id, subject_id,"
            " learning_area_id, is_form_teacher, teaches_all_subjects) values (:s, :t, :a,"
            " :subject, :area, :form, :all) returning id"
        ),
        {
            "s": who.school_id,
            "t": body.teacher_id,
            "a": arm,
            "subject": body.subject_id,
            "area": body.learning_area_id,
            "form": body.is_form_teacher,
            "all": body.teaches_all_subjects,
        },
    )
    audit(
        session,
        who,
        "assignments.create",
        target=("teacher_assignments", assignment_id),
        new=body.model_dump(mode="json"),
    )
    return assignment_row(
        session.execute(text(f"{ASSIGNMENT_SELECT} where t.id = :id"), {"id": assignment_id}).one()
    )


@router.delete("/assignments/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: uuid.UUID, who: Assign, session: DbSession) -> None:
    in_school(session, "teacher_assignments", assignment_id)
    session.execute(text("delete from teacher_assignments where id = :id"), {"id": assignment_id})
    audit(session, who, "assignments.delete", target=("teacher_assignments", assignment_id))


# --- class teacher assistants (F06 rule 3) -------------------------------------------------


@router.get("/arms/{arm_id}/assistants", response_model=list[AssistantRow])
def list_assistants(arm_id: uuid.UUID, _: Member, session: DbSession) -> list[AssistantRow]:
    in_school(session, "class_arms", arm_id)
    return [
        AssistantRow(user_id=str(r.id), full_name=r.full_name, username=r.username)
        for r in session.execute(
            text(
                "select u.id, u.full_name, u.username from class_assistants c"
                " join users u on u.id = c.assistant_id where c.arm_id = :arm"
                " order by u.full_name"
            ),
            {"arm": arm_id},
        )
    ]


@router.post("/arms/{arm_id}/assistants", status_code=201, response_model=AssistantRow)
def add_assistant(
    arm_id: uuid.UUID, body: NewAssistant, who: Assign, session: DbSession
) -> AssistantRow:
    arm = found(in_school(session, "class_arms", arm_id))
    member_of_school(session, body.user_id)
    arm_level_on(session, who, arm)
    session.execute(
        text("insert into class_assistants (school_id, arm_id, assistant_id) values (:s, :a, :u)"),
        {"s": who.school_id, "a": arm, "u": body.user_id},
    )
    audit(
        session,
        who,
        "assistants.create",
        target=("class_arms", arm),
        new={"assistant_id": str(body.user_id)},
    )
    row = session.execute(
        text("select id, full_name, username from users where id = :id"), {"id": body.user_id}
    ).one()
    return AssistantRow(user_id=str(row.id), full_name=row.full_name, username=row.username)


@router.delete("/arms/{arm_id}/assistants/{user_id}", status_code=204)
def remove_assistant(
    arm_id: uuid.UUID, user_id: uuid.UUID, who: Assign, session: DbSession
) -> None:
    found(
        session.scalar(
            text(
                "delete from class_assistants where arm_id = :a and assistant_id = :u returning id"
            ),
            {"a": arm_id, "u": user_id},
        )
    )
    audit(
        session,
        who,
        "assistants.delete",
        target=("class_arms", arm_id),
        old={"assistant_id": str(user_id)},
    )


# --- reviewer scopes (F06 rule 1) ----------------------------------------------------------


def scope_row(r: Any) -> ScopeRow:
    return ScopeRow(
        id=str(r.id),
        department_id=str(r.department_id) if r.department_id else None,
        subject_id=str(r.subject_id) if r.subject_id else None,
        class_id=str(r.class_id) if r.class_id else None,
    )


@router.get("/reviewers/{user_id}/scopes", response_model=list[ScopeRow])
def list_scopes(user_id: uuid.UUID, _: Member, session: DbSession) -> list[ScopeRow]:
    member_of_school(session, user_id)
    return [
        scope_row(r)
        for r in session.execute(
            text(
                "select id, department_id, subject_id, class_id from reviewer_scopes"
                " where reviewer_id = :u order by created_at, id"
            ),
            {"u": user_id},
        )
    ]


@router.post("/reviewers/{user_id}/scopes", status_code=201, response_model=ScopeRow)
def add_scope(user_id: uuid.UUID, body: NewScope, who: Assign, session: DbSession) -> ScopeRow:
    member_of_school(session, user_id)
    in_school(session, "departments", body.department_id)
    in_school(session, "subjects", body.subject_id)
    in_school(session, "classes", body.class_id)
    row = session.execute(
        text(
            "insert into reviewer_scopes (school_id, reviewer_id, department_id, subject_id,"
            " class_id) values (:s, :u, :d, :subject, :c)"
            " returning id, department_id, subject_id, class_id"
        ),
        {
            "s": who.school_id,
            "u": user_id,
            "d": body.department_id,
            "subject": body.subject_id,
            "c": body.class_id,
        },
    ).one()
    audit(
        session,
        who,
        "reviewer_scopes.create",
        target=("reviewer_scopes", row.id),
        new=body.model_dump(mode="json"),
    )
    return scope_row(row)


@router.delete("/reviewer-scopes/{scope_id}", status_code=204)
def delete_scope(scope_id: uuid.UUID, who: Assign, session: DbSession) -> None:
    in_school(session, "reviewer_scopes", scope_id)
    session.execute(text("delete from reviewer_scopes where id = :id"), {"id": scope_id})
    audit(session, who, "reviewer_scopes.delete", target=("reviewer_scopes", scope_id))
