"""The auth routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.core.dependencies import (
    DbSession,
    PrincipalDep,
    SessionDep,
    get_rate_limiter,
)
from app.core.rate_limit import RateLimiter
from app.platform.storage import FileStorage, get_file_storage
from app.src.auth import services
from app.src.auth.schemas import (
    Accepted,
    ChangePasswordRequest,
    ForgotRequest,
    LinkRequest,
    LoginRequest,
    LoginResult,
    Me,
    SchoolPublic,
)
from app.src.auth.services import ForgotByIp, LinkByIp, LoginByIp, PublicByIp, SameOrigin

router = APIRouter(prefix="/auth", tags=["auth"])

Limiter = Annotated[RateLimiter, Depends(get_rate_limiter)]

Storage = Annotated[FileStorage, Depends(get_file_storage)]


# --- logging in -----------------------------------------------------------------------
@router.post("/login", response_model=LoginResult, dependencies=[LoginByIp, SameOrigin])
def login(
    body: LoginRequest, request: Request, response: Response, session: DbSession
) -> LoginResult | JSONResponse:
    return services.login(body=body, request=request, response=response, session=session)


@router.get("/schools/{code}/public", response_model=SchoolPublic, dependencies=[PublicByIp])
def school_public(code: str, session: DbSession) -> SchoolPublic:
    return services.school_public(code=code, session=session)


@router.get("/schools/{code}/logo", dependencies=[PublicByIp])
def school_logo_image(
    code: str, request: Request, session: DbSession, storage: Storage
) -> Response:
    return services.school_logo_image(code=code, request=request, session=session, storage=storage)


# --- the session ----------------------------------------------------------------------
@router.post("/logout", status_code=204)
def logout(signed_in: SessionDep, response: Response, session: DbSession) -> None:
    return services.logout(signed_in=signed_in, response=response, session=session)


@router.post("/logout-all", status_code=204)
def logout_all(signed_in: SessionDep, response: Response, session: DbSession) -> None:
    return services.logout_all(signed_in=signed_in, response=response, session=session)


@router.post("/refresh", response_model=LoginResult)
def refresh(principal: PrincipalDep, response: Response, session: DbSession) -> LoginResult:
    return services.refresh(principal=principal, response=response, session=session)


@router.get("/me", response_model=Me)
def me(principal: PrincipalDep, session: DbSession) -> Me:
    return services.me(principal=principal, session=session)


@router.post("/change-password", status_code=204)
def change_password(
    body: ChangePasswordRequest, principal: PrincipalDep, response: Response, session: DbSession
) -> None:
    return services.change_password(
        body=body, principal=principal, response=response, session=session
    )


@router.post("/activate", response_model=LoginResult, dependencies=[LinkByIp, SameOrigin])
def activate(
    body: LinkRequest, request: Request, response: Response, session: DbSession
) -> LoginResult:
    return services.activate(body=body, request=request, response=response, session=session)


@router.post("/password/reset", response_model=LoginResult, dependencies=[LinkByIp, SameOrigin])
def reset_password(
    body: LinkRequest, request: Request, response: Response, session: DbSession
) -> LoginResult:
    return services.reset_password(body=body, request=request, response=response, session=session)


@router.post("/join", response_model=LoginResult, dependencies=[LinkByIp, SameOrigin])
def join(
    body: LinkRequest, request: Request, response: Response, session: DbSession
) -> LoginResult:
    # A new parent's link from a school's request (CHANGE 2026-10-29, D-177).
    return services.join(body=body, request=request, response=response, session=session)


@router.post(
    "/password/forgot",
    status_code=202,
    response_model=Accepted,
    dependencies=[ForgotByIp, SameOrigin],
)
def forgot_password(body: ForgotRequest, session: DbSession, limiter: Limiter) -> Accepted:
    # At most 3 emails an hour per address; over that, the same answer and no email.
    return services.forgot_password(body=body, session=session, limiter=limiter)
