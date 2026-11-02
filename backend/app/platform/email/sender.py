"""The background email sender (BUILD_PROMPT 9.2; SPEC F18; D-078 to D-083, D-153, D-176).

It runs as app_sender, the database login that reads the outbox and changes
only its sending columns. Each run:

1. counts what was sent today (Lagos time) and stops at the daily limit
   (95, under Resend Free's 100, D-082);
2. takes the due Queued emails, account emails first (priority 1 before 5),
   then the oldest, locking each so two runs never send the same one;
3. for each, asks the database to prepare it (`email_prepare`, migration 26):
   the school's name and email for the sender name and Reply-To (D-079), and,
   for an activation, reset or new-parent link, stores the hash of a link
   made here and now (D-081; the link itself is only ever in the email);
4. writes the email from its template, plain words in HTML and text, never
   scores, passwords or report contents (D-083), and sends it;
5. records Sent with the provider's id; or, for a temporary failure, tries
   again after 1 min, 5 min, 30 min, 2 h and 12 h, then marks it Failed; a
   permanent failure is Failed at once. Error notes are cut short and lose
   any email address.

The caller commits. Links put the token after "#", so it never reaches a
server log: the page reads it and posts it.
"""

import datetime as dt
import re
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import formataddr
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import new_token, token_hash
from app.platform.email.provider import EmailProvider, OutgoingEmail, SendError

RETRY_GAPS = (
    dt.timedelta(minutes=1),
    dt.timedelta(minutes=5),
    dt.timedelta(minutes=30),
    dt.timedelta(hours=2),
    dt.timedelta(hours=12),
)
MAX_ATTEMPTS = len(RETRY_GAPS)
# The advisory lock number that gives one run the sender's turn (any fixed number).
SENDER_LOCK = 7_176_001
LINKED = ("activation", "password_reset", "parent_link_request")
ADDRESS = re.compile(r"[^\s@<>()\"']+@[^\s@<>()\"']+")
STATUS_WORDS = {
    "open": "Open",
    "investigating": "Investigating",
    "needs_more_information": "Needs more information",
    "resolved": "Resolved",
    "rejected": "Rejected",
}

environment = Environment(
    loader=PackageLoader("app.platform.email", "templates"),
    autoescape=select_autoescape(default=True, default_for_string=True),
    undefined=StrictUndefined,
)


@dataclass(frozen=True)
class Content:
    subject: str
    paragraphs: list[str]
    button: tuple[str, str] | None = None  # (label, address)


@dataclass(frozen=True)
class SendReport:
    sent: int
    retried: int
    failed: int
    waiting: int  # due now but left for the next run (the daily limit or the batch size)


@dataclass(frozen=True)
class Prepared:
    school_name: str | None
    reply_to: str | None
    address_kind: str | None
    base_url: str
    token: str | None


def link(prepared: Prepared, path: str) -> str:
    return f"{prepared.base_url}{path}#token={prepared.token}"


def activation(d: dict[str, Any], p: Prepared) -> Content:
    where = d.get("school_name") or "SchoolFlow"
    code = f" and your school code is {d['school_code']}" if d.get("school_code") else ""
    return Content(
        f"Set up your {where} account",
        [
            f"Hello {d['full_name']},",
            f"{where} has made a SchoolFlow account for you. Your username is "
            f"{d['username']}{code}.",
            "Set your password with the button below. The link works once, for 72 hours.",
        ],
        ("Set your password", link(p, "/activate")),
    )


def password_reset(d: dict[str, Any], p: Prepared) -> Content:
    return Content(
        "Reset your SchoolFlow password",
        [
            f"Hello {d['full_name']},",
            "We had a request to reset your password. The link works once, for one hour.",
            "If you did not ask for this, ignore this email and your password stays the same.",
        ],
        ("Reset your password", link(p, "/reset-password")),
    )


def password_changed(d: dict[str, Any], p: Prepared) -> Content:
    return Content(
        "Your SchoolFlow password was changed",
        [
            f"Hello {d['full_name']},",
            "Your password was just changed. If this was not you, contact your school admin"
            " straight away.",
        ],
        ("Log in", f"{p.base_url}/login"),
    )


def school_setup(d: dict[str, Any], p: Prepared) -> Content:
    return Content(
        f"{d['school_name']} is set up on SchoolFlow",
        [
            f"{d['school_name']} is ready on SchoolFlow. Your school code is {d['school_code']}.",
            "Students log in on the school's own login page.",
        ],
        ("Open the login page", f"{p.base_url}{d['login_path']}"),
    )


def parent_link_request(d: dict[str, Any], p: Prepared) -> Content:
    subject = f"{d['school_name']} would like to link your account"
    added = f"{d['school_name']} has added you as the parent or guardian {d['guardian_name']}."
    if p.address_kind == "parent":
        return Content(
            subject,
            ["Hello,", added, "Log in to accept or decline the link."],
            ("Log in", f"{p.base_url}/login"),
        )
    if p.address_kind == "staff_or_pupil":
        return Content(
            subject,
            [
                "Hello,",
                f"{d['school_name']} tried to add this email address for the parent or guardian"
                f" {d['guardian_name']}.",
                "This address already belongs to a staff or pupil account, so it cannot be used"
                " for a parent. Please ask the school to use another email address.",
            ],
        )
    return Content(
        subject,
        [
            "Hello,",
            added,
            "Set a password to see your child's results. The link works once, for 14 days.",
        ],
        ("Set your password", link(p, "/join")),
    )


def results_published(d: dict[str, Any], p: Prepared) -> Content:
    updated = bool(d.get("updated"))
    lead = "Updated " if updated else ""
    word = "have been updated" if updated else "are published"
    return Content(
        f"{lead}{d['term_name']} results for {d['class_name']} are ready",
        [
            f"Hello {d['full_name']},",
            f"{d['term_name']} {d['session_name']} results for {d['class_name']} at"
            f" {d['school_name']} {word}.",
            "Log in to view the report.",
        ],
        ("Log in", f"{p.base_url}{d['login_path']}"),
    )


def correction_updated(d: dict[str, Any], p: Prepared) -> Content:
    status = STATUS_WORDS.get(d["status"], d["status"])
    return Content(
        f"Update on your correction request {d['number']}",
        [
            f"Hello {d['full_name']},",
            f"Your correction request {d['number']} at {d['school_name']} is now: {status}.",
            "Log in to see the details.",
        ],
        ("Log in", f"{p.base_url}{d['login_path']}"),
    )


TEMPLATES: dict[str, Callable[[dict[str, Any], Prepared], Content]] = {
    "activation": activation,
    "password_reset": password_reset,
    "password_changed": password_changed,
    "school_setup": school_setup,
    "parent_link_request": parent_link_request,
    "results_published": results_published,
    "correction_updated": correction_updated,
}


def clean(detail: str) -> str:
    """An error note without addresses, short enough to show in the Email log."""
    return ADDRESS.sub("[address]", detail)[:300]


def render(template: str, data: dict[str, Any], prepared: Prepared) -> Content:
    write = TEMPLATES.get(template)
    if write is None:
        raise SendError(f"No email template called {template}", temporary=False)
    return write(data, prepared)


def as_email(row: Any, content: Content, prepared: Prepared, from_domain: str) -> OutgoingEmail:
    html = environment.get_template("email.html").render(content=content)
    text_body = "\n\n".join(content.paragraphs)
    if content.button:
        text_body += f"\n\n{content.button[0]}: {content.button[1]}"
    text_body += "\n\nSent by SchoolFlow. Please do not reply to this address."
    if prepared.reply_to:
        text_body = text_body.replace(
            "Please do not reply to this address.", "Replies go to the school."
        )
    return OutgoingEmail(
        sender=formataddr((prepared.school_name or "SchoolFlow", f"no-reply@{from_domain}")),
        to=row.to_address,
        subject=content.subject,
        html=html,
        text=text_body,
        reply_to=prepared.reply_to,
        idempotency_key=f"{row.idempotency_key}:{row.attempts + 1}",
    )


def send_due(
    session: Session,
    provider: EmailProvider,
    *,
    base_url: str,
    from_domain: str,
    daily_limit: int,
    batch: int = 50,
) -> SendReport:
    base = base_url.rstrip("/")
    # One run at a time counts and sends (D-177); a second run sends nothing and
    # leaves the rest to the run that has the turn (or the next one).
    if not session.scalar(text("select pg_try_advisory_xact_lock(:k)"), {"k": SENDER_LOCK}):
        return SendReport(sent=0, retried=0, failed=0, waiting=0)
    sent_today = int(
        session.scalar(
            text(
                "select count(*) from email_outbox where status = 'sent' and sent_at >="
                " (date_trunc('day', now() at time zone 'Africa/Lagos')"
                " at time zone 'Africa/Lagos')"
            )
        )
        or 0
    )
    room = max(0, min(batch, daily_limit - sent_today))
    rows = list(
        session.execute(
            text(
                "select id, template, template_data, to_address, idempotency_key, attempts"
                " from email_outbox where status = 'queued' and next_attempt_at <= now()"
                " order by priority, created_at, id limit :n for update skip locked"
            ),
            {"n": room},
        )
    )
    sent = retried = failed = 0
    for row in rows:
        token = new_token() if row.template in LINKED else None
        found = session.execute(
            text("select * from email_prepare(:id, :hash)"),
            {"id": row.id, "hash": token_hash(token) if token else None},
        ).first()
        if found is None:
            continue
        prepared = Prepared(found.school_name, found.reply_to, found.address_kind, base, token)
        try:
            email = as_email(
                row, render(row.template, row.template_data, prepared), prepared, from_domain
            )
            message_id = provider.send(email)
        except SendError as failure:
            attempts = row.attempts + 1
            again = failure.temporary and attempts < MAX_ATTEMPTS
            session.execute(
                text(
                    "update email_outbox set status = :status, attempts = :attempts,"
                    " next_attempt_at = now() + :gap, last_error = :error where id = :id"
                ),
                {
                    "status": "queued" if again else "failed",
                    "attempts": attempts,
                    "gap": RETRY_GAPS[attempts - 1] if again else dt.timedelta(0),
                    "error": clean(str(failure)),
                    "id": row.id,
                },
            )
            retried, failed = (retried + 1, failed) if again else (retried, failed + 1)
            continue
        session.execute(
            text(
                "update email_outbox set status = 'sent', attempts = attempts + 1,"
                " sent_at = now(), provider_message_id = :message, last_error = null"
                " where id = :id"
            ),
            {"message": message_id, "id": row.id},
        )
        sent += 1
    waiting = int(
        session.scalar(
            text(
                "select count(*) from email_outbox"
                " where status = 'queued' and next_attempt_at <= now()"
            )
        )
        or 0
    )
    return SendReport(sent=sent, retried=retried, failed=failed, waiting=waiting)
