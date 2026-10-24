"""Public report verification (BUILD_PROMPT 9.2l; SPEC F13; D-071 to D-077).

Anyone with a report's QR code or verification code can check it is
genuine, without logging in. The lookup runs on its own database login,
app_verifier, which can call `verify_report()` and read nothing else; the
database hashes the code and returns only the school, the masked name
(`Chuk*** O.`), session, term, status, revision, report ID and publication
date, never scores or the full name (D-074). Input is forgiving (capitals,
spaces and dashes do not matter). A report verifies even when its level is
switched off or the school is suspended (D-075). Each IP gets 30 lookups a
minute and 10 unknown codes a minute (D-076); answers are never cached or
indexed, and logs keep only the first 4 characters of a code.
"""

import datetime as dt
import logging
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Response
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from schoolflow_api.core.deps import get_rate_limiter
from schoolflow_api.core.errors import ProblemError
from schoolflow_api.core.ratelimit import RateLimiter, client_ip, limit_by_ip
from schoolflow_api.core.schemas import ApiModel
from schoolflow_api.db import make_engine
from schoolflow_api.settings import get_settings

router = APIRouter(tags=["verification"])
log = logging.getLogger("schoolflow.verify")

TERM_NAMES = {1: "First Term", 2: "Second Term", 3: "Third Term"}
PRIVATE = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
}


@lru_cache
def get_verifier_engine() -> Engine:
    url = get_settings().database_url_verifier
    if url is None:
        raise ProblemError(503, "Service unavailable", "Verification is not set up yet.")
    return make_engine(url.get_secret_value())


def get_verifier_db() -> Iterator[Session]:
    session = Session(get_verifier_engine())
    try:
        yield session
        session.commit()
    finally:
        session.close()


VerifierDb = Annotated[Session, Depends(get_verifier_db)]
Code = Annotated[str, Path(min_length=1, max_length=40)]


class Verification(ApiModel):
    status: Literal["valid", "superseded", "revoked"]
    school: str
    student: str
    session: str
    term: str
    report_id: str
    revision: int
    published_at: dt.datetime | None
    has_newer_revision: bool


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
    response.headers.update(PRIVATE)
    row = db.execute(text("select * from verify_report(:code)"), {"code": code}).first()
    log.info("verify", extra={"fields": {"code_start": code[:4], "found": row is not None}})
    if row is None:
        wait = limiter.hit(f"verify-unknown:ip:{ip}", 10, 60)
        if wait:
            raise ProblemError(
                429,
                "Too many attempts",
                "Please wait a little and try again.",
                headers={"Retry-After": str(wait), **PRIVATE},
            )
        raise ProblemError(
            404,
            "Not Found",
            "We couldn't find that code. Check it and try again.",
            code="not_found",
            headers=PRIVATE,
        )
    return Verification(
        status=row.status,
        school=row.school_name,
        student=row.masked_name,
        session=row.session_name,
        term=TERM_NAMES[row.term_number],
        report_id=row.report_code,
        revision=row.revision,
        published_at=row.published_at,
        has_newer_revision=row.has_newer_revision,
    )
