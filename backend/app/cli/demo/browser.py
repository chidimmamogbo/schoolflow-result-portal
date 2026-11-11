"""A person using the app from inside this process (D-180).

Like a browser: it keeps the session cookie, sends the CSRF header and the
Origin the app expects, and calls the real routes. A request that fails stops
the seed with the route and the problem code, never the request body (it may
hold a password).
"""

from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import CSRF_COOKIE, CSRF_HEADER


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


class Demo:
    """The app, the one demo password, and everyone signed in so far."""

    def __init__(self, app: FastAPI, *, password: str, origin: str) -> None:
        self.app = app
        self.password = password
        self.origin = origin
        self.people: dict[str, Browser] = {}
        self.ids: dict[str, str] = {}

    def log_in(self, identifier: str, password: str, school_code: str | None = None) -> Browser:
        person = Browser(self.app, self.origin)
        body: dict[str, str] = {"identifier": identifier, "password": password}
        if school_code is not None:
            body["school_code"] = school_code
        person.post("/auth/login", body)
        return person

    def as_(self, username: str) -> Browser:
        """Someone already set up, signed in with the demo password."""
        if username not in self.people:
            self.people[username] = self.log_in(username, self.password)
        return self.people[username]

    def take_over(self, identifier: str, temporary: str, school_code: str | None = None) -> Browser:
        """First sign-in with a temporary password, then the demo password, as a person would."""
        person = self.log_in(identifier, temporary, school_code)
        person.post(
            "/auth/change-password",
            {"current_password": temporary, "new_password": self.password},
        )
        self.people[identifier] = person
        return person
