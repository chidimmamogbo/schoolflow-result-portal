"""When emails go out (SPEC F18; D-176, D-177).

Both ways run the same sender (sender.py) as app_sender:

1. Right after a request. Anything that queues an email marks the request's
   database session (note_queued: queue_email() does it, and so do the
   routes whose database functions queue one). After the route, DbSession
   adds one background run, which FastAPI starts once the response has gone
   and the transaction has committed. So an activation or reset email leaves
   within seconds. A failed request rolls back and starts nothing.
2. Once a day. Vercel's cron calls GET /api/v1/cron/emails (src/cron) to send
   what is left: retries, and anything a busy run missed. Vercel Hobby runs
   cron jobs once a day, on production only.

Each batch takes the sender's turn (an advisory lock, sender.py), so two runs
at once never go past the daily limit together. Without DATABASE_URL_SENDER
and RESEND_API_KEY nothing runs and the emails stay Queued.
"""

import logging
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from functools import lru_cache, partial

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import make_engine
from app.platform.email.provider import EmailProvider, ResendProvider
from app.platform.email.sender import SendReport, send_due

logger = logging.getLogger(__name__)

QUEUED = "email_queued"
# The platform's session points at the request's own session (platform_db),
# so emails queued there count for the request too.
FORWARD_TO = "email_queued_on"

Runner = Callable[[], SendReport]


def note_queued(session: Session) -> None:
    """This request queued an email: send soon after it commits."""
    target: Session = session.info.get(FORWARD_TO, session)
    target.info[QUEUED] = True


def take_queued(session: Session) -> bool:
    return bool(session.info.pop(QUEUED, False))


def send_all(
    batches: Callable[[], AbstractContextManager[Session]],
    provider: EmailProvider,
    *,
    base_url: str,
    from_domain: str,
    daily_limit: int,
    batch: int = 50,
) -> SendReport:
    """Batch after batch, each in its own transaction, until nothing is due."""
    sent = retried = failed = 0
    while True:
        with batches() as session:
            report = send_due(
                session, provider, base_url=base_url, from_domain=from_domain,
                daily_limit=daily_limit, batch=batch,
            )  # fmt: skip
        sent, retried, failed = sent + report.sent, retried + report.retried, failed + report.failed
        if report.sent + report.retried + report.failed == 0:
            return SendReport(sent=sent, retried=retried, failed=failed, waiting=report.waiting)


@contextmanager
def committed_batch(engine: Engine) -> Generator[Session]:
    with Session(engine) as session:
        yield session
        session.commit()


@lru_cache
def sender_engine(url: str) -> Engine:
    return make_engine(url)


def runner_for(settings: Settings) -> Runner | None:
    """The real run, or None until the sender's login and the Resend key are set."""
    if settings.database_url_sender is None or settings.resend_api_key is None:
        return None
    engine = sender_engine(settings.database_url_sender.get_secret_value())
    return partial(
        send_all,
        partial(committed_batch, engine),
        ResendProvider(settings.resend_api_key.get_secret_value()),
        base_url=str(settings.app_base_url),
        from_domain=settings.email_from_domain,
        daily_limit=settings.email_daily_limit,
    )


def configured_runner() -> Runner | None:
    return runner_for(get_settings())


def send_soon() -> None:
    """The background run after a request. It must never break the app."""
    try:
        run = configured_runner()
        if run is not None:
            run()
    except Exception as error:  # logged; the daily run tries again
        # Only the kind of error: its text can hold an address or database values.
        logger.warning("email run failed", extra={"fields": {"error": type(error).__name__}})


def get_email_kick() -> Callable[[], None]:
    """What DbSession starts after a request that queued an email (tests replace it)."""
    return send_soon
