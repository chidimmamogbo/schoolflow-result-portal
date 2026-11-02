"""Shared route dependencies: the database session and the rate limiter.

A FastAPI "dependency" is a function a route asks for in its signature; FastAPI
runs it for each request and passes the result in (a little like WordPress
handing `$wpdb` to every plugin, but per request and easy to swap in tests).

Routes take the session as `DbSession`: one transaction per request, committed
before the response is sent (scope="function", FastAPI docs checked
2026-10-15), so a rule PostgreSQL checks at commit still becomes a proper
error response; rolled back on any error. Who the database works for is set
by the auth dependencies with `use_context()` (9.2b and 9.2c). When the route
queued an email, DbSession also starts one email run in the background, after
the response (platform/email/trigger.py, D-177).
"""

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import BackgroundTasks, Depends, Request
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ProblemError
from app.core.permissions import MATRIX, Role, permissions_for
from app.core.rate_limit import RateLimiter
from app.core.security import CSRF_HEADER, SESSION_COOKIE, csrf_matches, token_hash
from app.db.session import make_engine, use_context
from app.platform.email.trigger import get_email_kick, take_queued
from app.src.schools.models import Feature, Level


@lru_cache
def get_engine() -> Engine:
    """The app's connection pool (role app_user, D-026), made on first use."""
    return make_engine(get_settings().database_url.get_secret_value())


def get_db() -> Iterator[Session]:
    session = Session(get_engine())
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session(
    session: Annotated[Session, Depends(get_db, scope="function")],
    background: BackgroundTasks,
    kick: Annotated[Callable[[], None], Depends(get_email_kick)],
) -> Iterator[Session]:
    """get_db, plus: an email queued by a successful route goes out soon after (D-177)."""
    take_queued(session)  # a fresh request starts unmarked
    yield session
    # Not reached when the route fails. The task runs after get_db has committed.
    if take_queued(session):
        background.add_task(kick)


DbSession = Annotated[Session, Depends(get_db_session, scope="function")]


def get_rate_limiter() -> RateLimiter:
    secret = get_settings().app_secret_key.get_secret_value().encode()
    return RateLimiter.for_engine(get_engine(), secret)


# --- authz_deps ------------------------------------------------------------
# The authorization chain every protected route runs (D-018, D-047, D-049 to D-051).
#
# Like WordPress checking is_user_logged_in() and then current_user_can(), but
# as FastAPI dependencies, in this order:
#
# 1. current_session: a live session cookie (and, for a change, the CSRF token
#    and our own Origin); the database now works for this user.
# 2. current_principal: the account is active; its school membership is
#    chosen (a parent in two schools may name one of their own with the
#    X-School-Id header, D-138); the membership and school are active; the
#    database now works for that school.
# 3. require(permission, feature=...): the temporary password is changed, the
#    feature is on (404 `feature_disabled`) and the role has the permission
#    (403 `permission_denied`, matrix in permissions.py).
# 4. In the route: ensure_level_enabled(), found() for ownership and scope
#    (another school's record is simply not found, 404), require_status() for
#    the workflow state and require_someone_else() for separation of duties.
#    The database checks scope, workflow and duties again (D-051).
#
# Only the routes in PUBLIC_ROUTES skip step 1 (the logo route joined by an approved
# CHANGE, 2026-10-22; public verification is F13, D-071); tests/test_authz.py fails if
# any other route does.

PUBLIC_ROUTES = frozenset(
    {
        ("GET", "/api/v1/health"),
        ("GET", "/api/v1/health/ready"),
        ("POST", "/api/v1/auth/login"),
        ("GET", "/api/v1/auth/schools/{code}/public"),
        ("GET", "/api/v1/auth/schools/{code}/logo"),
        ("POST", "/api/v1/auth/activate"),
        ("POST", "/api/v1/auth/password/forgot"),
        ("POST", "/api/v1/auth/password/reset"),
        ("GET", "/api/v1/verify/{code}"),
        # A new parent's link and Vercel's daily email run (CHANGE 2026-10-29, D-177).
        ("POST", "/api/v1/auth/join"),
        ("GET", "/api/v1/cron/emails"),
    }
)
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
SCHOOL_HEADER = "X-School-Id"

# Idle limits (D-037): 1 hour for the super admin, 12 hours for everyone else.
IDLE_SECONDS = {True: 3600, False: 12 * 3600}

NOT_SIGNED_IN = ProblemError(401, "Please log in", code="not_signed_in")
SCHOOL_PAUSED_TITLE = "Your school's access is paused. Contact your school admin."


def problem(status: int, title: str, code: str) -> ProblemError:
    return ProblemError(status, title, code=code)


def school_paused() -> ProblemError:
    return problem(403, SCHOOL_PAUSED_TITLE, "school_paused")


@dataclass(frozen=True)
class SignedIn:
    session_id: uuid.UUID
    user_id: uuid.UUID
    token: str
    is_super_admin: bool
    must_change_password: bool


@dataclass(frozen=True)
class Membership:
    school_id: uuid.UUID
    role: Role
    is_primary: bool
    active: bool


@dataclass(frozen=True)
class Principal:
    """Who is asking, in which school, with which permissions."""

    user_id: uuid.UUID
    session_id: uuid.UUID
    is_super_admin: bool
    must_change_password: bool
    school_id: uuid.UUID | None
    role: Role
    is_primary: bool
    memberships: tuple[Membership, ...]
    permissions: frozenset[str]


# --- step 1: the session ----------------------------------------------------------


def check_origin(request: Request) -> None:
    """D-038: a browser's Origin, when sent, must be our own site."""
    origin = request.headers.get("origin")
    if origin is None:
        return
    base = urlsplit(str(get_settings().app_base_url))
    if origin != f"{base.scheme}://{base.netloc}":
        raise problem(
            403,
            "This request could not be checked. Refresh the page and try again.",
            "csrf_failed",
        )


def same_origin(request: Request) -> None:
    """For public routes that change something (login, links, forgot password)."""
    check_origin(request)


_SESSION = text(
    "select s.id, u.is_active, u.is_super_admin, u.must_change_password,"
    " s.last_seen_at < now() - make_interval(secs => case when u.is_super_admin"
    "     then cast(:admin_idle as integer) else cast(:idle as integer) end) as idle,"
    " s.last_seen_at < now() - interval '1 minute' as stale"
    " from user_sessions s join users u on u.id = s.user_id"
    " where s.token_hash = :hash"
)


def current_session(request: Request, session: DbSession) -> SignedIn:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise NOT_SIGNED_IN
    if request.method not in SAFE_METHODS:
        check_origin(request)
        if not csrf_matches(token, request.headers.get(CSRF_HEADER)):
            raise problem(
                403,
                "This request could not be checked. Refresh the page and try again.",
                "csrf_failed",
            )
    hashed = token_hash(token)
    user_id = session.scalar(text("select auth_session_account(:hash)"), {"hash": hashed})
    if user_id is None:
        raise NOT_SIGNED_IN
    use_context(session, user_id=user_id)
    row = session.execute(
        _SESSION, {"hash": hashed, "admin_idle": IDLE_SECONDS[True], "idle": IDLE_SECONDS[False]}
    ).one()
    # A deactivated account or an idle session is refused at once (AC03.3, D-037).
    if not row.is_active or row.idle:
        raise NOT_SIGNED_IN
    if row.stale:
        session.execute(
            text("update user_sessions set last_seen_at = now() where id = :id"), {"id": row.id}
        )
    return SignedIn(row.id, user_id, token, row.is_super_admin, row.must_change_password)


SessionDep = Annotated[SignedIn, Depends(current_session)]


# --- step 2: the school membership ----------------------------------------------------


def memberships_of(session: Session, user_id: uuid.UUID) -> tuple[Membership, ...]:
    rows = session.execute(
        text(
            "select school_id, role, is_primary, status = 'active' as active"
            " from school_memberships where user_id = :id order by created_at, school_id"
        ),
        {"id": user_id},
    )
    return tuple(Membership(r.school_id, Role(r.role), r.is_primary, r.active) for r in rows)


def choose_membership(memberships: tuple[Membership, ...], wanted: str | None) -> Membership | None:
    """The membership named by X-School-Id, else the first active one."""
    if wanted is not None:
        try:
            school_id = uuid.UUID(wanted)
        except ValueError:
            raise problem(404, "Not Found", "school_not_found") from None
        chosen = next((m for m in memberships if m.school_id == school_id), None)
        if chosen is None:
            raise problem(404, "Not Found", "school_not_found")
        return chosen
    return next((m for m in memberships if m.active), memberships[0] if memberships else None)


def enter_school(session: Session, user_id: uuid.UUID, membership: Membership | None) -> Membership:
    """Point the database at the school, refusing a paused link or school."""
    if membership is None or not membership.active:
        raise school_paused()
    use_context(session, school_id=membership.school_id, user_id=user_id)
    status = session.scalar(
        text("select status from schools where id = :id"), {"id": membership.school_id}
    )
    if status != "active":
        raise school_paused()
    return membership


def current_principal(request: Request, signed_in: SessionDep, session: DbSession) -> Principal:
    if signed_in.is_super_admin:
        return Principal(
            signed_in.user_id,
            signed_in.session_id,
            True,
            signed_in.must_change_password,
            None,
            Role.SUPER_ADMIN,
            False,
            (),
            permissions_for(Role.SUPER_ADMIN),
        )
    memberships = memberships_of(session, signed_in.user_id)
    chosen = choose_membership(memberships, request.headers.get(SCHOOL_HEADER))
    chosen = enter_school(session, signed_in.user_id, chosen)
    return Principal(
        signed_in.user_id,
        signed_in.session_id,
        False,
        signed_in.must_change_password,
        chosen.school_id,
        chosen.role,
        chosen.is_primary,
        memberships,
        permissions_for(chosen.role, is_primary=chosen.is_primary),
    )


PrincipalDep = Annotated[Principal, Depends(current_principal)]


# --- step 3: password change, feature and permission ---------------------------------


def require(
    permission: str | None = None, *, feature: Feature | None = None
) -> Callable[..., Principal]:
    """A route dependency: the whole chain, then this permission and feature."""
    if permission is not None and permission not in MATRIX:
        raise ValueError(f"Unknown permission {permission!r}")

    def check(principal: PrincipalDep, session: DbSession) -> Principal:
        if principal.must_change_password:
            raise problem(403, "Change your password to continue.", "password_change_required")
        if feature is not None and principal.school_id is not None:
            enabled = session.scalar(
                text("select enabled from school_features where school_id = :s and feature = :f"),
                {"s": principal.school_id, "f": feature.value},
            )
            if not enabled:
                raise problem(
                    404, "This feature is switched off for your school.", "feature_disabled"
                )
        if permission is not None and permission not in principal.permissions:
            raise problem(403, "You don't have permission to do this.", "permission_denied")
        return principal

    return check


# --- step 4: helpers for the route itself -----------------------------------------------


def ensure_level_enabled(session: Session, principal: Principal, level: Level) -> None:
    """D-050: every level-bound request for a level that is off is refused."""
    enabled = session.scalar(
        text("select enabled from school_levels where school_id = :s and level = :l"),
        {"s": principal.school_id, "l": level.value},
    )
    if not enabled:
        raise problem(404, "Report cards for this level are switched off.", "level_disabled")


def found[T](value: T | None) -> T:
    """A record the caller may not see is answered like one that does not exist."""
    if value is None:
        raise ProblemError(404, "Not Found")
    return value


def require_status(current: str, *allowed: str) -> None:
    if current not in allowed:
        raise problem(409, "This can't be done at the current stage.", "wrong_status")


def require_someone_else(actor: uuid.UUID, earlier_actor: uuid.UUID | None) -> None:
    """D-052: the person who did the earlier step may not do this one."""
    if earlier_actor is not None and actor == earlier_actor:
        raise problem(403, "Someone else must do this step.", "separation_of_duties")
