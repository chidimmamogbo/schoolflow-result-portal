"""Scheduled runs that Vercel starts (D-177): the daily email run.

Vercel's cron calls GET /api/v1/cron/emails once a day on production, with the
header "Authorization: Bearer <CRON_SECRET>" (Vercel docs, cron jobs, checked
2026-10-29). Like a WordPress cron hook, but started from outside by a call
that must carry the secret. Without the right secret, or with no secret set,
the call is refused before anything else; without the sender's settings it
answers 503. It sends whatever the background runs left (trigger.py).
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.errors import ProblemError
from app.core.schemas import ApiModel
from app.platform.email import trigger

router = APIRouter(prefix="/cron", tags=["cron"])

REFUSED = ProblemError(401, "Not allowed", code="cron_refused")
NOT_SET_UP = ProblemError(
    503, "Service unavailable", "Email sending is not set up.", code="email_not_set_up"
)


class EmailRun(ApiModel):
    sent: int
    retried: int
    failed: int
    waiting: int


def get_cron_secret() -> SecretStr | None:
    return get_settings().cron_secret


def get_email_runner() -> trigger.Runner | None:
    return trigger.configured_runner()


def allowed(authorization: str | None, secret: SecretStr | None) -> bool:
    if secret is None or authorization is None:
        return False
    expected = f"Bearer {secret.get_secret_value()}"
    # Constant time, so the answer's speed says nothing about the secret.
    return secrets.compare_digest(authorization.encode(), expected.encode())


@router.get("/emails", response_model=EmailRun)
def emails(
    response: Response,
    secret: Annotated[SecretStr | None, Depends(get_cron_secret)],
    run: Annotated[trigger.Runner | None, Depends(get_email_runner)],
    authorization: Annotated[str | None, Header()] = None,
) -> EmailRun:
    response.headers["Cache-Control"] = "no-store"
    if not allowed(authorization, secret):
        raise REFUSED
    if run is None:
        raise NOT_SET_UP
    report = run()
    return EmailRun(
        sent=report.sent, retried=report.retried, failed=report.failed, waiting=report.waiting
    )
