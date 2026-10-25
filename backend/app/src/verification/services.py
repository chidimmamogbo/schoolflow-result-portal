"""Public report verification (BUILD_PROMPT 9.2l; SPEC F13; D-071 to D-077).

Anyone with a report's QR code or verification code can check it is
genuine, without logging in. The lookup runs on its own database login,
app_verifier, which can call `verify_report()` and read nothing else; the
database hashes the code and returns only the school, the masked name
(`Chuk*** O.`), session, term, status, revision, report ID and publication
date, and for an old revision the newest one's number and date (migration
25), never scores, the full name or another revision's code (D-074). Input is forgiving (capitals,
spaces and dashes do not matter). A report verifies even when its level is
switched off or the school is suspended (D-075). Each IP gets 30 lookups a
minute and 10 unknown codes a minute (D-076); answers are never cached or
indexed, and logs keep only the first 4 characters of a code.
"""

import logging
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Path, Response
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ProblemError
from app.core.rate_limit import RateLimiter
from app.db.session import make_engine
from app.src.verification.schemas import Verification

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


Code = Annotated[str, Path(min_length=1, max_length=40)]


def verify(
    code: Code,
    db: Session,
    response: Response,
    ip: str,
    limiter: RateLimiter,
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
        newer_revision=row.newer_revision,
        newer_published_at=row.newer_published_at,
    )
