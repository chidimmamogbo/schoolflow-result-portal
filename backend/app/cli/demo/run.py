"""The whole demo seed in order, and how the command builds it (D-180).

`seed_demo` runs every step through the app's routes and says what it did.
`real_seed` is what `python -m app.cli seed-demo` runs: the configured app,
the sender's own login for reading the seed's mail (the mail never leaves this
process) and the app's base URL as the browsers' origin.

The seed's emails stay in the outbox marked sent: the outbox is append-only
(a database rule), so they are never deleted, and they never reach Resend.
"""

from collections.abc import Callable
from functools import partial

from app.cli.demo.browser import Demo, SeedError
from app.cli.demo.platform import SUPER_ADMIN, seed_platform
from app.cli.demo.pupils import seed_pupils
from app.cli.demo.results import seed_results
from app.cli.demo.schools import seed_schools

Say = Callable[[str], None]


def seed_billing(demo: Demo) -> None:
    """The term's invoices: GMC's stays unpaid, RCS's is paid by bank transfer."""
    owner = demo.as_(SUPER_ADMIN)
    made = owner.post("/platform/invoices/generate", {})
    by_school = {invoice["school_id"]: invoice for invoice in made["created"]}
    rcs = by_school.get(demo.ids["RCS"])
    if rcs is None or demo.ids["GMC"] not in by_school:
        raise SeedError("The term's invoices for GMC and RCS were not made.")
    owner.post(
        f"/platform/invoices/{rcs['id']}/manual-payment",
        {"reference": "TRF-RCS-2026-0001", "note": "Bank transfer for First Term."},
    )
    demo.read_mail()


STEPS: list[tuple[str, Callable[[Demo], None]]] = [
    ("Price list, schools and principals", seed_platform),
    ("Sessions, classes, subjects and staff", seed_schools),
    ("Pupils and parents", seed_pupils),
    ("Results week and publishing", seed_results),
    ("Invoices", seed_billing),
]


def seed_demo(demo: Demo, say: Say) -> None:
    for title, step in STEPS:
        say(f"{title} ...")
        step(demo)
    say("Done. Every demo account uses the password in SEED_PASSWORD.")


def real_seed(password: str, say: Say) -> None:
    """The configured app, as the command runs it."""
    from app.core.config import get_settings
    from app.main import create_app
    from app.platform.email.trigger import committed_batch, sender_engine

    settings = get_settings()
    if settings.database_url_sender is None or settings.database_url_platform is None:
        raise SeedError(
            "The seed needs DATABASE_URL_PLATFORM and DATABASE_URL_SENDER (the app's own logins)."
        )
    mail = partial(committed_batch, sender_engine(settings.database_url_sender.get_secret_value()))
    demo = Demo(
        create_app(),
        password=password,
        origin=str(settings.app_base_url).rstrip("/"),
        mail=mail,
    )
    seed_demo(demo, say)
