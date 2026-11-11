"""Making and resetting the platform's super admin (SPEC section 4; D-046, D-180).

There is no route that makes a super admin: no app database role may set
`users.is_super_admin`, so these run on the owner connection
(`DATABASE_URL_MIGRATIONS`), the same one migrations use. A reset touches
super admins only: school admins are reset by a super admin inside the app,
and everyone else by their school.
"""

import re
import uuid

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    MAX_LENGTH,
    MIN_LENGTH,
    PasswordProblem,
    hash_password,
    password_problem,
)
from app.src.audit.services import write_audit

USERNAME = re.compile(r"^[a-z0-9._-]{3,30}$")

PROBLEMS = {
    PasswordProblem.TOO_SHORT: f"The password needs at least {MIN_LENGTH} characters.",
    PasswordProblem.TOO_LONG: f"The password can have at most {MAX_LENGTH} characters.",
    PasswordProblem.TOO_COMMON: "That password is too common. Choose another.",
}


class RefusedError(Exception):
    """Something the operator asked for that is not allowed; the message says why."""


class BadPasswordError(RefusedError):
    pass


def check_password(password: str) -> None:
    problem = password_problem(password, student=False)
    if problem is not None:
        raise BadPasswordError(PROBLEMS[problem])


def create_super_admin(
    session: Session, *, username: str, full_name: str, email: str | None, password: str
) -> uuid.UUID:
    check_password(password)
    if not USERNAME.match(username):
        raise RefusedError(
            "Usernames use 3 to 30 small letters, numbers, dots, dashes or underscores."
        )
    email = email.strip().lower() if email else None
    taken = session.scalar(
        text("select exists (select 1 from users where username = :u or email = :e)"),
        {"u": username, "e": email},
    )
    if taken:
        raise RefusedError("That username or email is already taken.")
    try:
        with session.begin_nested():
            user_id: uuid.UUID = session.scalar(
                text(
                    "insert into users (username, full_name, email, is_super_admin,"
                    " password_hash, email_verified_at, must_change_password)"
                    " values (:u, :n, :e, true, :h,"
                    " case when cast(:e as text) is null then null else now() end, false)"
                    " returning id"
                ),
                {"u": username, "n": full_name.strip(), "e": email, "h": hash_password(password)},
            )
    except IntegrityError as error:
        raise RefusedError("That account could not be made: check the name and email.") from error
    write_audit(
        session,
        None,
        "system",
        "platform.super_admin_created",
        target=("users", user_id),
        new={"username": username},
    )
    return user_id


def reset_super_admin(session: Session, *, username: str, password: str) -> None:
    check_password(password)
    user_id = session.scalar(
        text("select id from users where username = :u and is_super_admin"), {"u": username}
    )
    if user_id is None:
        raise RefusedError("No super admin has that username.")
    session.execute(
        text(
            "update users set password_hash = :h, must_change_password = false,"
            " temp_password_expires_at = null where id = :id"
        ),
        {"h": hash_password(password), "id": user_id},
    )
    # Every device signs in again with the new password.
    session.execute(text("delete from user_sessions where user_id = :id"), {"id": user_id})
    write_audit(
        session,
        None,
        "system",
        "platform.super_admin_reset",
        target=("users", user_id),
        new={"username": username},
    )
