"""The verification routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_rate_limiter
from app.core.rate_limit import RateLimiter, client_ip, limit_by_ip
from app.src.verification import services
from app.src.verification.schemas import Verification
from app.src.verification.services import Code, get_verifier_db

router = APIRouter(tags=["verification"])

VerifierDb = Annotated[Session, Depends(get_verifier_db)]


@router.get(
    "/verify/{code}",
    response_model=Verification,
    dependencies=[Depends(limit_by_ip("verify", 30, 60))],
)
def verify(
    code: Code,
    db: VerifierDb,
    response: Response,
    ip: Annotated[str, Depends(client_ip)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> Verification:
    return services.verify(code=code, db=db, response=response, ip=ip, limiter=limiter)
