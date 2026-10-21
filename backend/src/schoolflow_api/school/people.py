"""Additional school admins and login support (BUILD_PROMPT 9.2e; SPEC F03; D-040, D-048, D-138).

- Only the principal adds and removes additional school admins, up to the
  limit in Platform settings (Security, default 2).
- Login support (resend activation, reset link, temporary password, sign out
  of all devices, deactivate, reactivate) reaches the school's own people:
  any school admin for reviewers, teachers, parents and pupils; only the
  principal for additional admins; nobody inside the school for the
  principal (the super admin does that, F03 rule 5). Nobody uses it on their
  own account (Change password is for that).
- An account linked to another school too is managed only by its owner
  (D-138): refused here, and by the database.
- Temporary passwords are shown once and never written to the audit.
"""

import uuid
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from schoolflow_api.audit.log import write_audit
from schoolflow_api.auth.temporary import issue_temporary_password
from schoolflow_api.authz.deps import Principal, found, require
from schoolflow_api.core.deps import DbSession
from schoolflow_api.core.errors import ProblemError
from schoolflow_api.emails.queue import queue_email
from schoolflow_api.platform import settings_model
from schoolflow_api.platform.schemas import Detail, ResetLink, TemporaryPassword
from schoolflow_api.school.schemas import AdminRow, Admins, CreatedAdmin, NewAdmin

router = APIRouter(prefix="/school", tags=["school"])

Member = Annotated[Principal, Depends(require())]
AddAdmins = Annotated[Principal, Depends(require("school_admins.create"))]
RemoveAdmins = Annotated[Principal, Depends(require("school_admins.remove"))]
Support = Annotated[Principal, Depends(require("users.reset_login"))]

TAKEN = {
    "ix_users_username_platform": ("This username is taken.", "username_taken"),
    "uq_users_email": ("This email is already used.", "email_taken"),
}
DENIED = ProblemError(403, "You don't have permission to do this.", code="permission_denied")


def admin_rows(session: Session) -> list[AdminRow]:
    return [
        AdminRow(
            id=str(r.id),
            full_name=r.full_name,
            username=r.username,
            email=r.email,
            is_primary=r.is_primary,
            is_active=r.is_active,
            activated=r.activated,
        )
        for r in session.execute(
            text(
                "select u.id, u.full_name, u.username, u.email, u.is_active,"
                " u.password_hash is not null as activated, m.is_primary"
                " from school_memberships m join users u on u.id = m.user_id"
                " where m.role = 'school_admin' and m.school_id = app_current_school_id()"
                " order by m.is_primary desc, u.full_name"
            )
        )
    ]


@router.get("/admins", response_model=Admins)
def list_admins(who: Member, session: DbSession) -> Admins:
    if who.role.value != "school_admin":
        raise DENIED
    rows = admin_rows(session)
    limit = settings_model.load(session).security.max_additional_admins
    additional = sum(1 for row in rows if not row.is_primary)
    return Admins(admins=rows, places_left=max(0, limit - additional))


def activation_data(session: Session, user_id: uuid.UUID) -> dict[str, Any]:
    row = session.execute(
        text(
            "select u.id, u.full_name, u.username, s.code, s.name from users u, schools s"
            " where u.id = :id and s.id = app_current_school_id()"
        ),
        {"id": user_id},
    ).one()
    return {
        "user_id": str(row.id),
        "full_name": row.full_name,
        "username": row.username,
        "school_code": row.code,
        "school_name": row.name,
    }


@router.post("/admins", status_code=201, response_model=CreatedAdmin)
def add_admin(body: NewAdmin, who: AddAdmins, session: DbSession) -> CreatedAdmin:
    limit = settings_model.load(session).security.max_additional_admins
    additional = sum(1 for row in admin_rows(session) if not row.is_primary)
    if additional >= limit:
        raise ProblemError(409, f"You can add up to {limit} school admins.", code="admin_limit")
    # The id is made here: the school sees the account only once it has a membership.
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
            " values (:u, :s, 'school_admin', 'active')"
        ),
        {"u": user_id, "s": who.school_id},
    )
    temporary = None
    if body.login_method == "activation" and body.email is not None:
        queue_email(
            session, who.school_id, "activation", body.email, activation_data(session, user_id)
        )
    else:
        temporary = issue_temporary_password(session, user_id)
    write_audit(
        session,
        who.school_id,
        who.role.value,
        "school_admins.create",
        target=("users", user_id),
        new={"username": body.username, "login_method": body.login_method},
    )
    return CreatedAdmin(id=str(user_id), temporary_password=temporary)


@router.delete("/admins/{user_id}", status_code=204)
def remove_admin(user_id: uuid.UUID, who: RemoveAdmins, session: DbSession) -> None:
    found(
        session.scalar(
            text(
                "select user_id from school_memberships where user_id = :u"
                " and school_id = app_current_school_id() and role = 'school_admin'"
                " and not is_primary"
            ),
            {"u": user_id},
        )
    )
    # Sessions first: once the link is gone, the school can no longer see the account.
    session.execute(text("delete from user_sessions where user_id = :u"), {"u": user_id})
    session.execute(
        text(
            "delete from school_memberships where user_id = :u"
            " and school_id = app_current_school_id()"
        ),
        {"u": user_id},
    )
    write_audit(
        session, who.school_id, who.role.value, "school_admins.remove", target=("users", user_id)
    )


# --- login support ----------------------------------------------------------------------


def person(session: Session, who: Principal, user_id: uuid.UUID) -> Any:
    """The school's own person, if this admin may support them (D-048)."""
    row = found(
        session.execute(
            text(
                "select u.id, u.full_name, u.email, u.is_active,"
                " u.password_hash is not null as activated, m.role, m.is_primary,"
                " app_account_is_shared(u.id) as shared"
                " from school_memberships m join users u on u.id = m.user_id"
                " where m.user_id = :u and m.school_id = app_current_school_id()"
            ),
            {"u": user_id},
        ).first()
    )
    if row.role == "school_admin" and "school_admins.reset_login" not in who.permissions:
        raise DENIED
    if row.id == who.user_id or row.is_primary:
        # Only the principal gets this far with the principal: their own account.
        raise ProblemError(409, "Use Change password for your own account.", code="own_account")
    if row.shared:
        raise ProblemError(
            403,
            "This account is linked to another school too. Only its owner can change it.",
            code="shared_account",
        )
    return row


def action_name(row: Any, action: str) -> str:
    return f"{'school_admins' if row.role == 'school_admin' else 'users'}.{action}"


def end_sessions(session: Session, user_id: uuid.UUID) -> None:
    session.execute(text("delete from user_sessions where user_id = :u"), {"u": user_id})


@router.post("/people/{user_id}/resend-activation", status_code=202, response_model=Detail)
def resend_activation(user_id: uuid.UUID, who: Support, session: DbSession) -> Detail:
    row = person(session, who, user_id)
    if row.activated:
        raise ProblemError(409, "This account is already activated.", code="already_activated")
    if row.email is None:
        raise ProblemError(409, "This account has no email.", code="no_email")
    queue_email(session, who.school_id, "activation", row.email, activation_data(session, user_id))
    write_audit(
        session,
        who.school_id,
        who.role.value,
        action_name(row, "resend_activation"),
        target=("users", user_id),
    )
    return Detail(detail="Activation email queued.")


@router.post("/people/{user_id}/send-reset-link", status_code=202, response_model=Detail)
def send_reset_link(
    user_id: uuid.UUID, body: ResetLink, who: Support, session: DbSession
) -> Detail:
    row = person(session, who, user_id)
    if row.email is None:
        raise ProblemError(409, "This account has no email.", code="no_email")
    queue_email(
        session,
        who.school_id,
        "password_reset",
        row.email,
        {"user_id": str(row.id), "full_name": row.full_name},
    )
    if body.sign_out_all:
        end_sessions(session, user_id)
    write_audit(
        session,
        who.school_id,
        who.role.value,
        action_name(row, "reset_link"),
        target=("users", user_id),
        new={"sign_out_all": body.sign_out_all},
    )
    return Detail(detail="Reset link queued.")


@router.post(
    "/people/{user_id}/temporary-password", status_code=201, response_model=TemporaryPassword
)
def temporary_password(user_id: uuid.UUID, who: Support, session: DbSession) -> TemporaryPassword:
    row = person(session, who, user_id)
    password = issue_temporary_password(session, user_id)
    write_audit(
        session,
        who.school_id,
        who.role.value,
        action_name(row, "temporary_password"),
        target=("users", user_id),
        new={"must_change_password": True},
    )
    return TemporaryPassword(temporary_password=password)


@router.post("/people/{user_id}/sign-out-all", status_code=204)
def sign_out_all(user_id: uuid.UUID, who: Support, session: DbSession) -> None:
    row = person(session, who, user_id)
    end_sessions(session, user_id)
    write_audit(
        session,
        who.school_id,
        who.role.value,
        action_name(row, "sign_out_all"),
        target=("users", user_id),
    )


@router.post("/people/{user_id}/deactivate", status_code=204)
def deactivate(user_id: uuid.UUID, who: Support, session: DbSession) -> None:
    row = person(session, who, user_id)
    session.execute(text("update users set is_active = false where id = :u"), {"u": user_id})
    end_sessions(session, user_id)
    write_audit(
        session,
        who.school_id,
        who.role.value,
        action_name(row, "deactivate"),
        target=("users", user_id),
        old={"is_active": True},
        new={"is_active": False},
    )


@router.post("/people/{user_id}/reactivate", status_code=204)
def reactivate(user_id: uuid.UUID, who: Support, session: DbSession) -> None:
    row = person(session, who, user_id)
    session.execute(text("update users set is_active = true where id = :u"), {"u": user_id})
    write_audit(
        session,
        who.school_id,
        who.role.value,
        action_name(row, "reactivate"),
        target=("users", user_id),
        old={"is_active": False},
        new={"is_active": True},
    )
