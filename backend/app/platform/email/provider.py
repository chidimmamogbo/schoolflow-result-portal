"""Where emails go out: the EmailProvider interface and Resend (D-078, D-176).

The sender builds an OutgoingEmail and hands it to a provider, which sends
it and returns the provider's message id, or raises SendError saying
whether trying again could help. Resend is the real one; RecordingProvider
keeps the emails in memory for tests and local runs, so nothing is sent.

Resend's API, checked 2026-10-25 (resend.com/docs/api-reference/emails/send-email):
POST https://api.resend.com/emails with a Bearer key and JSON `from`, `to`
(a list), `subject`, `html`, `text`, `reply_to`; an `Idempotency-Key` header
(at most 256 characters, kept 24 hours) stops a repeated request sending
twice. The answer holds the email's `id`. 400, 401, 403, 409 and 422 mean
"do not retry"; 429 and 5xx mean "retry later".
"""

import contextlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

import httpx

RESEND_URL = "https://api.resend.com/emails"


@dataclass(frozen=True)
class OutgoingEmail:
    sender: str  # "Greenfield Model College <no-reply@notify.meritiaa.com>"
    to: str
    subject: str
    html: str
    text: str
    reply_to: str | None
    idempotency_key: str


class SendError(Exception):
    """The provider did not take the email; `temporary` says a retry could work."""

    def __init__(self, detail: str, *, temporary: bool) -> None:
        super().__init__(detail)
        self.temporary = temporary


class EmailProvider(Protocol):
    def send(self, email: OutgoingEmail) -> str: ...


class ResendProvider:
    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self._key = api_key
        self._client = client or httpx.Client(timeout=10)

    def send(self, email: OutgoingEmail) -> str:
        body: dict[str, object] = {
            "from": email.sender,
            "to": [email.to],
            "subject": email.subject,
            "html": email.html,
            "text": email.text,
        }
        if email.reply_to:
            body["reply_to"] = email.reply_to
        try:
            response = self._client.post(
                RESEND_URL,
                json=body,
                headers={
                    "Authorization": f"Bearer {self._key}",
                    "Idempotency-Key": email.idempotency_key[:256],
                },
            )
        except httpx.HTTPError as error:
            raise SendError(
                f"Resend could not be reached ({type(error).__name__})", temporary=True
            ) from None
        if response.status_code == 200:
            message_id: str = response.json()["id"]
            return message_id
        name = ""
        with contextlib.suppress(ValueError):
            name = str(response.json().get("name", ""))[:60]
        retry = response.status_code == 429 or response.status_code >= 500
        raise SendError(f"Resend answered {response.status_code} {name}".strip(), temporary=retry)


@dataclass
class RecordingProvider:
    """Keeps every email instead of sending it; `failures` are raised first, in order."""

    failures: Sequence[SendError] = ()
    sent: list[OutgoingEmail] = field(default_factory=list[OutgoingEmail])
    _tries: int = 0

    def send(self, email: OutgoingEmail) -> str:
        self._tries += 1
        if self._tries <= len(self.failures):
            raise self.failures[self._tries - 1]
        self.sent.append(email)
        return f"msg-{len(self.sent)}"
