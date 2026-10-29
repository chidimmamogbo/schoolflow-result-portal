"""Run the email sender once by hand: `uv run python -m app.platform.email.worker` (D-176).

It logs in as app_sender (DATABASE_URL_SENDER) and sends through Resend
(RESEND_API_KEY), batch after batch, each committed on its own, so a crash
loses at most the batch in hand. On Vercel the same run starts after each
request that queues an email and once a day from the cron (trigger.py, D-177);
this command is for your own machine and for emergencies.
"""

import sys

from app.platform.email.trigger import configured_runner


def main() -> int:
    run = configured_runner()
    if run is None:
        print("Set DATABASE_URL_SENDER and RESEND_API_KEY to send emails.", file=sys.stderr)
        return 1
    report = run()
    print(
        f"sent {report.sent}, retrying {report.retried}, failed {report.failed},"
        f" waiting {report.waiting}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
