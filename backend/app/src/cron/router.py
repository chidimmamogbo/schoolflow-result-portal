"""Scheduled runs that Vercel starts (D-177, D-178): the daily email and payment runs.

Vercel's cron calls GET /api/v1/cron/emails once a day on production, with the
header "Authorization: Bearer <CRON_SECRET>" (Vercel docs, cron jobs, checked
2026-10-29). Like a WordPress cron hook, but started from outside by a call
that must carry the secret. Without the right secret, or with no secret set,
the call is refused before anything else; without the sender's settings it
answers 503. It sends whatever the background runs left (trigger.py).
"""

import secrets
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.errors import ProblemError
from app.core.schemas import ApiModel
from app.platform.email import trigger
from app.platform.payments.gateway import PaymentGateway
from app.src.billing import processing

router = APIRouter(prefix="/cron", tags=["cron"])

REFUSED = ProblemError(401, "Not allowed", code="cron_refused")
NOT_SET_UP = ProblemError(
    503, "Service unavailable", "This run is not set up.", code="email_not_set_up"
)


class EmailRun(ApiModel):
    sent: int
    retried: int
    failed: int
    waiting: int


class PaymentRun(ApiModel):
    processed: int
    ignored: int
    failed: int
    waiting: int
    subscriptions_refreshed: int


def get_cron_secret() -> SecretStr | None:
    return get_settings().cron_secret


def get_email_runner() -> trigger.Runner | None:
    return trigger.configured_runner()


def payment_run(batches: processing.Batches, gateway: PaymentGateway | None) -> PaymentRun:
    """Events a background run missed, then D-092's daily status refresh."""
    report = processing.ProcessReport(0, 0, 0, 0)
    if gateway is not None:
        report = processing.process_pending(batches, gateway)
    return PaymentRun(
        processed=report.processed,
        ignored=report.ignored,
        failed=report.failed,
        waiting=report.waiting,
        subscriptions_refreshed=processing.refresh_all_subscriptions(batches),
    )


def get_payment_runner() -> Callable[[], PaymentRun] | None:
    batches = processing.real_batches()
    if batches is None:
        return None
    ready = batches
    return lambda: payment_run(ready, processing.real_gateway())


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


@router.get("/payments", response_model=PaymentRun)
def payments(
    response: Response,
    secret: Annotated[SecretStr | None, Depends(get_cron_secret)],
    run: Annotated[Callable[[], PaymentRun] | None, Depends(get_payment_runner)],
    authorization: Annotated[str | None, Header()] = None,
) -> PaymentRun:
    response.headers["Cache-Control"] = "no-store"
    if not allowed(authorization, secret):
        raise REFUSED
    if run is None:
        raise NOT_SET_UP
    return run()
