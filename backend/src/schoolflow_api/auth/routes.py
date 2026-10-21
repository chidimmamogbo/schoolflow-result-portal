"""The /auth endpoints: log in and out, sessions, passwords (BUILD_PROMPT 9.2b; SPEC F02).

Like WordPress's wp-login.php, but there is no register action at all (F02
rule 10), every failure gives the same answer (D-034), and the session is
an opaque cookie whose hash alone is stored (D-037).

A failed login is returned as a response rather than raised, so the request
still commits and the failure counts towards the throttle (D-042). A refused
new password is raised, so the activation or reset link stays unused.
"""

import ipaddress
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.auth import passwords, throttle
from schoolflow_api.auth.passwords import PasswordProblem, password_problem
from schoolflow_api.auth.schemas import (
    Accepted,
    ChangePasswordRequest,
    ForgotRequest,
    FormClass,
    LinkRequest,
    LoginRequest,
    LoginResult,
    Me,
    MeSchool,
    MeSchoolLink,
    MeUser,
    SchoolPublic,
)
from schoolflow_api.auth.tokens import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    csrf_token,
    new_token,
    token_hash,
)
from schoolflow_api.authz.deps import (
    PrincipalDep,
    SessionDep,
    choose_membership,
    enter_school,
    memberships_of,
    same_origin,
)
from schoolflow_api.authz.permissions import Role
from schoolflow_api.core.deps import DbSession, get_rate_limiter
from schoolflow_api.core.errors import ProblemError, problem_response
from schoolflow_api.core.ratelimit import RateLimiter, client_ip, limit_by_ip
from schoolflow_api.db import use_context

router = APIRouter(prefix="/auth", tags=["auth"])

# Lifetimes (D-037): 7 days in all, 12 hours for the super admin.
SESSION_SECONDS = {True: 12 * 3600, False: 7 * 24 * 3600}
LOGIN_FAILED = "That login didn't work. Check your details and try again."
FORGOT_SENT = (
    "If that email belongs to an account that can reset its password, "
    "a reset link is on its way. No email on your account? "
    "Ask your school admin to reset your password."
)
LINK_INVALID = ProblemError(
    400,
    "This link has expired or was already used.",
    "Ask your school admin for a new one.",
    code="link_invalid",
)
PASSWORD_TITLES = {
    PasswordProblem.TOO_SHORT: "That password is too short.",
    PasswordProblem.TOO_LONG: "That password is too long (128 characters at most).",
    PasswordProblem.TOO_COMMON: "That password is too common. Try a few unrelated words.",
}

# A whole computer lab can log in from one school IP, so the IP limit is wide;
# the per-account throttle does the real work (D-042).
LoginByIp = Depends(limit_by_ip("login", 300, 900))
LinkByIp = Depends(limit_by_ip("auth-link", 30, 900))
ForgotByIp = Depends(limit_by_ip("forgot", 10, 900))
PublicByIp = Depends(limit_by_ip("school-public", 60, 60))
SameOrigin = Depends(same_origin)
Limiter = Annotated[RateLimiter, Depends(get_rate_limiter)]


# --- helpers ------------------------------------------------------------------------


def device_label(user_agent: str) -> str | None:
    """A rough "Chrome on Android" for the signed-in devices list."""
    agent = user_agent.lower()
    browser = next(
        (
            name
            for key, name in (
                ("edg/", "Edge"),
                ("firefox/", "Firefox"),
                ("chrome/", "Chrome"),
                ("safari/", "Safari"),
            )
            if key in agent
        ),
        None,
    )
    system = next(
        (
            name
            for key, name in (
                ("android", "Android"),
                ("iphone", "iPhone"),
                ("ipad", "iPad"),
                ("windows", "Windows"),
                ("mac os", "Mac"),
                ("linux", "Linux"),
            )
            if key in agent
        ),
        None,
    )
    if browser and system:
        return f"{browser} on {system}"
    return browser or system


def ip_or_none(request: Request) -> str | None:
    try:
        return str(ipaddress.ip_address(client_ip(request)))
    except ValueError:
        return None


def set_session_cookies(response: Response, token: str, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE, token, max_age=max_age, path="/", secure=True, httponly=True, samesite="lax"
    )
    # Readable by our own pages, which copy it into X-CSRF-Token (D-038).
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token(token),
        max_age=max_age,
        path="/",
        secure=True,
        httponly=False,
        samesite="lax",
    )


def clear_session_cookies(response: Response) -> None:
    for name, http_only in ((SESSION_COOKIE, True), (CSRF_COOKIE, False)):
        response.delete_cookie(name, path="/", secure=True, httponly=http_only, samesite="lax")


def start_session(
    session: Session, request: Request, response: Response, user_id: Any, super_admin: bool
) -> None:
    """A new session row (hash only) and its cookies; the database works for the user."""
    use_context(session, user_id=user_id)
    token = new_token()
    lifetime = SESSION_SECONDS[super_admin]
    session.execute(
        text(
            "insert into user_sessions (user_id, token_hash, device_label, ip_address,"
            " expires_at) values (:user_id, :hash, :device, cast(:ip as inet),"
            " now() + make_interval(secs => cast(:lifetime as integer)))"
        ),
        {
            "user_id": user_id,
            "hash": token_hash(token),
            "device": device_label(request.headers.get("user-agent", "")),
            "ip": ip_or_none(request),
            "lifetime": lifetime,
        },
    )
    set_session_cookies(response, token, lifetime)


def rotate_session(session: Session, response: Response, session_id: Any) -> None:
    """D-037: a new token for the same session; the old one stops working."""
    token = new_token()
    seconds_left = session.scalar(
        text(
            "update user_sessions set token_hash = :hash where id = :id"
            " returning greatest(1, extract(epoch from expires_at - now()))::integer"
        ),
        {"hash": token_hash(token), "id": session_id},
    )
    set_session_cookies(response, token, int(seconds_left or 1))


def check_new_password(password: str, *, student: bool) -> None:
    found = password_problem(password, student=student)
    if found is not None:
        raise ProblemError(422, PASSWORD_TITLES[found], code=found.value)


def save_password(session: Session, user_id: Any, password: str) -> None:
    session.execute(
        text(
            "update users set password_hash = :hash, must_change_password = false,"
            " temp_password_expires_at = null,"
            " email_verified_at = case when email is null then null"
            "     else coalesce(email_verified_at, now()) end"
            " where id = :id"
        ),
        {"hash": passwords.hash_password(password), "id": user_id},
    )


def login_failed() -> JSONResponse:
    return problem_response(401, LOGIN_FAILED, code="login_failed")


# --- logging in -----------------------------------------------------------------------


@router.post("/login", response_model=LoginResult, dependencies=[LoginByIp, SameOrigin])
def login(
    body: LoginRequest, request: Request, response: Response, session: DbSession
) -> LoginResult | JSONResponse:
    account = session.execute(
        text("select account_id, stored_hash from auth_login_account(:code, :identifier)"),
        {"code": body.school_code, "identifier": body.identifier},
    ).first()
    account_id = account.account_id if account else None
    key = throttle.throttle_key(
        f"account:{account_id}"
        if account_id
        else f"name:{(body.school_code or '').upper()}:{body.identifier.strip().lower()}"
    )
    locked = throttle.seconds_locked(session, key) > 0
    # Always exactly one password check, so every answer takes the same time (D-034).
    matches, new_hash = passwords.verify_password(
        body.password, account.stored_hash if account else None
    )
    if locked:
        return login_failed()
    if not matches or account_id is None:
        throttle.record_failure(session, key)
        return login_failed()

    use_context(session, user_id=account_id)
    user = session.execute(
        text(
            "select is_super_admin, must_change_password,"
            " coalesce(temp_password_expires_at < now(), false) as temp_expired"
            " from users where id = :id"
        ),
        {"id": account_id},
    ).one()
    if user.temp_expired:  # D-040: an unused slip expires after 7 days
        return login_failed()
    throttle.clear(session, key)
    if new_hash is not None:
        session.execute(
            text("update users set password_hash = :hash where id = :id"),
            {"hash": new_hash, "id": account_id},
        )
    if not user.is_super_admin:
        # The paused message comes only after a correct password (D-034).
        try:
            enter_school(
                session, account_id, choose_membership(memberships_of(session, account_id), None)
            )
        except ProblemError as refused:
            return problem_response(refused.status, refused.title, code=refused.code)
    start_session(session, request, response, account_id, user.is_super_admin)
    return LoginResult(must_change_password=user.must_change_password)


@router.get("/schools/{code}/public", response_model=SchoolPublic, dependencies=[PublicByIp])
def school_public(code: str, session: DbSession) -> SchoolPublic:
    row = session.execute(
        text("select school_code, school_name, school_colour from auth_school_public(:code)"),
        {"code": code[:20]},
    ).first()
    if row is None:
        raise ProblemError(404, "Not Found")
    return SchoolPublic(
        code=row.school_code, name=row.school_name, colour=row.school_colour, logo_url=None
    )


# --- the session ----------------------------------------------------------------------


@router.post("/logout", status_code=204)
def logout(signed_in: SessionDep, response: Response, session: DbSession) -> None:
    session.execute(text("delete from user_sessions where id = :id"), {"id": signed_in.session_id})
    clear_session_cookies(response)


@router.post("/logout-all", status_code=204)
def logout_all(signed_in: SessionDep, response: Response, session: DbSession) -> None:
    session.execute(
        text("delete from user_sessions where user_id = :id"), {"id": signed_in.user_id}
    )
    clear_session_cookies(response)


@router.post("/refresh", response_model=LoginResult)
def refresh(principal: PrincipalDep, response: Response, session: DbSession) -> LoginResult:
    if principal.must_change_password:
        raise ProblemError(
            403, "Change your password to continue.", code="password_change_required"
        )
    rotate_session(session, response, principal.session_id)
    return LoginResult(must_change_password=False)


@router.get("/me", response_model=Me)
def me(principal: PrincipalDep, session: DbSession) -> Me:
    user = session.execute(
        text("select id, full_name, username, email from users where id = :id"),
        {"id": principal.user_id},
    ).one()
    school = None
    features: list[str] = []
    form_class = None
    unread = 0
    if principal.school_id is not None:
        row = session.execute(
            text("select id, code, name, colour from schools where id = :id"),
            {"id": principal.school_id},
        ).one()
        school = MeSchool(id=str(row.id), code=row.code, name=row.name, colour=row.colour)
        features = list(
            session.scalars(
                text("select feature from school_features where enabled order by feature")
            )
        )
        arm = session.execute(
            text(
                "select a.id, btrim(c.name || ' ' || a.name) as name"
                " from teacher_assignments t"
                " join class_arms a on a.id = t.arm_id join classes c on c.id = a.class_id"
                " where t.teacher_id = :id and t.is_form_teacher"
            ),
            {"id": principal.user_id},
        ).first()
        if arm is not None:
            form_class = FormClass(arm_id=str(arm.id), name=arm.name)
        unread = int(
            session.scalar(
                text(
                    "select count(*) from notice_recipients r"
                    " join notices n on n.id = r.notice_id"
                    " where r.user_id = :id and n.status = 'published'"
                    " and not exists (select 1 from notice_reads d"
                    "     where d.notice_id = r.notice_id and d.user_id = r.user_id)"
                ),
                {"id": principal.user_id},
            )
            or 0
        )
    # Each school's name is read with the database pointed at that school (D-138).
    links: list[MeSchoolLink] = []
    for membership in principal.memberships:
        if not membership.active:
            continue
        use_context(session, school_id=membership.school_id, user_id=principal.user_id)
        name = session.scalar(
            text("select name from schools where id = :id"), {"id": membership.school_id}
        )
        links.append(
            MeSchoolLink(id=str(membership.school_id), name=str(name), role=membership.role.value)
        )
    use_context(session, school_id=principal.school_id, user_id=principal.user_id)
    return Me(
        user=MeUser(
            id=str(user.id), full_name=user.full_name, username=user.username, email=user.email
        ),
        school=school,
        schools=links,
        role=principal.role.value,
        is_primary=principal.is_primary,
        is_super_admin=principal.is_super_admin,
        must_change_password=principal.must_change_password,
        permissions=sorted(principal.permissions),
        features=features,
        form_class=form_class,
        unread_notices=unread,
    )


# --- passwords -------------------------------------------------------------------------


def is_student(session: Session, user_id: Any) -> bool:
    return bool(
        session.scalar(
            text("select student_school_id is not null from users where id = :id"),
            {"id": user_id},
        )
    )


@router.post("/change-password", status_code=204)
def change_password(
    body: ChangePasswordRequest, principal: PrincipalDep, response: Response, session: DbSession
) -> None:
    stored = session.scalar(
        text("select password_hash from users where id = :id"), {"id": principal.user_id}
    )
    matches, _ = passwords.verify_password(body.current_password, stored)
    if not matches:
        raise ProblemError(
            400, "Your current password is not right.", code="current_password_wrong"
        )
    if body.new_password == body.current_password:
        raise ProblemError(
            422, "Choose a password different from your current one.", code="password_unchanged"
        )
    check_new_password(body.new_password, student=principal.role is Role.STUDENT)
    save_password(session, principal.user_id, body.new_password)
    session.execute(
        text("delete from user_sessions where user_id = :user_id and id <> :id"),
        {"user_id": principal.user_id, "id": principal.session_id},
    )
    rotate_session(session, response, principal.session_id)
    session.execute(text("select auth_password_changed_email()"))
    if principal.school_id is not None:
        session.execute(
            text(
                "insert into audit_events (school_id, actor_role, action, target_table,"
                " target_id) values (:school, :role, 'accounts.password_change', 'users', :id)"
            ),
            {"school": principal.school_id, "role": principal.role.value, "id": principal.user_id},
        )


def use_link(
    session: Session, request: Request, response: Response, body: LinkRequest, purpose: str
) -> None:
    user_id = session.scalar(
        text("select auth_use_link(:hash, :purpose)"),
        {"hash": token_hash(body.token), "purpose": purpose},
    )
    if user_id is None:
        raise LINK_INVALID
    use_context(session, user_id=user_id)
    # Raised, so the transaction rolls back and the link stays usable (AT-06.3).
    check_new_password(body.password, student=is_student(session, user_id))
    save_password(session, user_id, body.password)
    session.execute(text("delete from user_sessions where user_id = :id"), {"id": user_id})
    super_admin = bool(
        session.scalar(text("select is_super_admin from users where id = :id"), {"id": user_id})
    )
    start_session(session, request, response, user_id, super_admin)


@router.post("/activate", response_model=LoginResult, dependencies=[LinkByIp, SameOrigin])
def activate(
    body: LinkRequest, request: Request, response: Response, session: DbSession
) -> LoginResult:
    use_link(session, request, response, body, "activation")
    return LoginResult(must_change_password=False)


@router.post("/password/reset", response_model=LoginResult, dependencies=[LinkByIp, SameOrigin])
def reset_password(
    body: LinkRequest, request: Request, response: Response, session: DbSession
) -> LoginResult:
    use_link(session, request, response, body, "reset")
    session.execute(text("select auth_password_changed_email()"))
    return LoginResult(must_change_password=False)


@router.post(
    "/password/forgot",
    status_code=202,
    response_model=Accepted,
    dependencies=[ForgotByIp, SameOrigin],
)
def forgot_password(body: ForgotRequest, session: DbSession, limiter: Limiter) -> Accepted:
    # At most 3 emails an hour per address; over that, the same answer and no email.
    email = body.email.strip().lower()
    if limiter.hit(f"forgot:email:{email}", 3, 3600) == 0:
        session.execute(text("select auth_request_password_reset(:email)"), {"email": email})
    return Accepted(detail=FORGOT_SENT)
