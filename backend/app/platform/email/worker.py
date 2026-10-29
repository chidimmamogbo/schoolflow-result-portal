"""Run the email sender once: `uv run python -m app.platform.email.worker` (D-176).

It logs in as app_sender (DATABASE_URL_SENDER) and sends through Resend
(RESEND_API_KEY). Each batch is committed on its own, so a crash loses at
most the batch in hand, and the next run carries on. Without a Resend key
nothing is sent and the emails stay Queued. How this runs on Vercel (a cron
route, Vercel Queues, or both) is decided separately.
"""

import sys

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import make_engine
from app.platform.email.provider import ResendProvider
from app.platform.email.sender import send_due


def main() -> int:
    settings = get_settings()
    if settings.database_url_sender is None or settings.resend_api_key is None:
        print("Set DATABASE_URL_SENDER and RESEND_API_KEY to send emails.", file=sys.stderr)
        return 1
    engine = make_engine(settings.database_url_sender.get_secret_value())
    provider = ResendProvider(settings.resend_api_key.get_secret_value())
    total = 0
    while True:
        with Session(engine) as session:
            report = send_due(
                session,
                provider,
                base_url=str(settings.app_base_url),
                from_domain=settings.email_from_domain,
                daily_limit=settings.email_daily_limit,
            )
            session.commit()
        total += report.sent
        print(
            f"sent {report.sent}, retrying {report.retried}, failed {report.failed},"
            f" waiting {report.waiting}"
        )
        if report.sent + report.retried + report.failed == 0:
            break
    print(f"done: {total} sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
