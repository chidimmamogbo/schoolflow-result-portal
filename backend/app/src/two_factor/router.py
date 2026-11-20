"""The two-factor routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.dependencies import DbSession, Principal, SessionDep, require
from app.src.auth.services import LoginByIp
from app.src.two_factor import services
from app.src.two_factor.schemas import (
    CodeRequest,
    CodesLeft,
    NewRecoveryCodes,
    Passed,
    SetUp,
)

router = APIRouter(prefix="/auth/two-factor", tags=["two-factor"])


def get_totp_cipher() -> services.Cipher:
    key = get_settings().totp_encryption_key
    return services.cipher_from(key.get_secret_value() if key else None)


def get_clock() -> services.Clock:
    return services.system_clock


TotpCipher = Annotated[services.Cipher, Depends(get_totp_cipher)]
ClockDep = Annotated[services.Clock, Depends(get_clock)]
SuperAdmin = Annotated[Principal, Depends(require("schools.manage"))]


@router.post("/setup", response_model=SetUp, dependencies=[LoginByIp])
def start_setup(signed_in: SessionDep, session: DbSession, cipher: TotpCipher) -> SetUp:
    return services.start_setup(signed_in=signed_in, session=session, cipher=cipher)


@router.post("/setup/confirm", response_model=NewRecoveryCodes, dependencies=[LoginByIp])
def finish_setup(
    body: CodeRequest,
    signed_in: SessionDep,
    session: DbSession,
    response: Response,
    cipher: TotpCipher,
    clock: ClockDep,
) -> NewRecoveryCodes | JSONResponse:
    return services.finish_setup(
        code=body.code,
        signed_in=signed_in,
        session=session,
        response=response,
        cipher=cipher,
        clock=clock,
    )


@router.post("/verify", response_model=Passed, dependencies=[LoginByIp])
def verify(
    body: CodeRequest,
    signed_in: SessionDep,
    session: DbSession,
    response: Response,
    cipher: TotpCipher,
    clock: ClockDep,
) -> Passed | JSONResponse:
    return services.verify(
        code=body.code,
        signed_in=signed_in,
        session=session,
        response=response,
        cipher=cipher,
        clock=clock,
    )


@router.post("/recovery", response_model=CodesLeft, dependencies=[LoginByIp])
def use_recovery(
    body: CodeRequest, signed_in: SessionDep, session: DbSession, response: Response
) -> CodesLeft | JSONResponse:
    return services.use_recovery(
        code=body.code, signed_in=signed_in, session=session, response=response
    )


@router.get("/recovery-codes", response_model=CodesLeft)
def codes_left(_: SuperAdmin, session: DbSession) -> CodesLeft:
    return services.codes_left(session=session)


@router.post("/recovery-codes", response_model=NewRecoveryCodes)
def replace_codes(
    body: CodeRequest,
    _: SuperAdmin,
    signed_in: SessionDep,
    session: DbSession,
    cipher: TotpCipher,
    clock: ClockDep,
) -> NewRecoveryCodes | JSONResponse:
    return services.replace_codes(
        code=body.code, signed_in=signed_in, session=session, cipher=cipher, clock=clock
    )
