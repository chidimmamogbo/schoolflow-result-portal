"""A person using the app from inside this process (D-180).

Like a browser: it keeps the session cookie, sends the CSRF header and the
Origin the app expects, and calls the real routes. A request that fails stops
the seed with the route and the problem code, never the request body (it may
hold a password).
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import CSRF_COOKIE, CSRF_HEADER
from app.platform.email import trigger
from app.platform.email.provider import OutgoingEmail, RecordingProvider
from app.src.billing import processing

# A whole batch of sending, as the app_sender login (the real sender's session).
MailBatches = Callable[[], AbstractContextManager[Session]]


class SeedError(Exception):
    """The seed cannot go on; the message says which step and why."""


class Browser:
    def __init__(self, app: FastAPI, origin: str) -> None:
        host = urlsplit(origin).netloc
        # https, so the cookie jar sends the __Host- cookies back.
        self.client = TestClient(app, base_url=f"https://{host}")
        self.origin = origin

    def call(self, method: str, url: str, body: Any = None, *, school: str | None = None) -> Any:
        headers = {CSRF_HEADER: self.client.cookies.get(CSRF_COOKIE) or "", "Origin": self.origin}
        if school is not None:
            headers["X-School-Id"] = school
        response = self.client.request(method, f"/api/v1{url}", json=body, headers=headers)
        if response.status_code >= 400:
            try:
                problem = response.json()
                why = problem.get("code") or problem.get("title")
            except ValueError:
                why = response.reason_phrase
            raise SeedError(f"{method} {url} answered {response.status_code} ({why}).")
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def get(self, url: str, **kw: Any) -> Any:
        return self.call("GET", url, **kw)

    def post(self, url: str, body: Any = None, **kw: Any) -> Any:
        return self.call("POST", url, body, **kw)

    def put(self, url: str, body: Any = None, **kw: Any) -> Any:
        return self.call("PUT", url, body, **kw)

    def patch(self, url: str, body: Any = None, **kw: Any) -> Any:
        return self.call("PATCH", url, body, **kw)


def do_nothing() -> None:
    return None


class Demo:
    """The app, the one demo password, and everyone signed in so far."""

    def __init__(self, app: FastAPI, *, password: str, origin: str, mail: MailBatches) -> None:
        self.app = app
        self.password = password
        self.origin = origin
        self.mail = mail
        # False: only the brief's named pupils (tests); True: 20 to 30 per class.
        self.full = True
        self.people: dict[str, Browser] = {}
        # How someone signs in when it is not their username (an email, a school code).
        self.sign_in: dict[str, tuple[str, str | None]] = {}
        self.ids: dict[str, str] = {}
        # The seed's own app never starts a real email or payment run: no demo email
        # may reach Resend, and payments are left to the webhook as usual.
        app.dependency_overrides[trigger.get_email_kick] = lambda: do_nothing
        app.dependency_overrides[processing.get_payment_kick] = lambda: do_nothing

    def log_in(self, identifier: str, password: str, school_code: str | None = None) -> Browser:
        person = Browser(self.app, self.origin)
        body: dict[str, str] = {"identifier": identifier, "password": password}
        if school_code is not None:
            body["school_code"] = school_code
        person.post("/auth/login", body)
        return person

    def as_(self, name: str) -> Browser:
        """Someone already set up, signed in with the demo password."""
        if name not in self.people:
            identifier, school_code = self.sign_in.get(name, (name, None))
            self.people[name] = self.log_in(identifier, self.password, school_code)
        return self.people[name]

    def take_over(self, identifier: str, temporary: str, school_code: str | None = None) -> Browser:
        """First sign-in with a temporary password, then the demo password, as a person would."""
        person = self.log_in(identifier, temporary, school_code)
        person.post(
            "/auth/change-password",
            {"current_password": temporary, "new_password": self.password},
        )
        self.people[identifier] = person
        if school_code is not None:
            self.sign_in[identifier] = (identifier, school_code)
        return person

    def read_mail(self) -> list[OutgoingEmail]:
        """Runs the app's own sender, but into a mailbox here: nothing leaves this process."""
        mailbox = RecordingProvider()
        trigger.send_all(
            self.mail,
            mailbox,
            base_url=self.origin,
            from_domain="demo.example",
            daily_limit=1_000_000,
        )
        return mailbox.sent
