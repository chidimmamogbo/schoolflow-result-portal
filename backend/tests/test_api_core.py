"""The API core (BUILD_PROMPT 9.2a; D-015, D-016, D-020, D-021, D-038, D-042, D-124, D-126).

Behaviour: every error is an RFC 9457 problem (application/problem+json) with
a request ID and never repeats what was sent, never quotes the database's own
message and never shows a crash's details; every response carries the request
ID and the security headers; no other site may call the API from a browser
(no CORS); the /docs page exists only locally; one request ID per request,
never taken from the caller; logs are JSON with secrets and personal data
redacted and the route template (never the raw path) logged; the readiness
check reaches the database; rate limits are counted in PostgreSQL by a
function the app roles can call but no role can read, per client IP taken
only from Vercel's own header outside local development. All data is fictional.
"""

import hashlib
import hmac
import json
import logging
import uuid
from collections.abc import Iterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from schoolflow_api.core.deps import get_db, get_rate_limiter
from schoolflow_api.core.errors import ProblemError
from schoolflow_api.core.logs import JsonFormatter, redact
from schoolflow_api.core.ratelimit import RateLimiter, client_ip, limit_by_ip
from schoolflow_api.core.schemas import ApiModel
from schoolflow_api.main import create_app
from tests.db_support import acting_as, refused

PROBLEM = "application/problem+json"


class Signup(ApiModel):
    username: str
    password: Annotated[str, Field(min_length=15)]


def build_app(db_session: Session, app_env: str = "local") -> FastAPI:
    """The real app plus a few test-only routes that fail in known ways."""
    app = create_app(app_env=app_env)

    def test_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[get_rate_limiter] = lambda: RateLimiter.for_session(db_session)

    @app.post("/api/v1/_test/strict")
    def strict(body: Signup) -> dict[str, str]:
        return {"username": body.username}

    @app.post("/api/v1/_test/database-rule")
    def database_rule(session: Annotated[Session, Depends(get_db, scope="function")]) -> None:
        # A school code that breaks the format rule; PostgreSQL quotes the value.
        session.execute(
            text(
                "insert into schools (code, name, email, phone, address, city, state, colour,"
                " school_type) values ('lowercase-secret-value', 'Fictional School',"
                " 'office@fictional.example', '08000000000', '1 Test Road', 'Enugu', 'Enugu',"
                " '#1D4ED8', 'secondary')"
            )
        )

    @app.get("/api/v1/_test/crash")
    def crash() -> None:
        raise RuntimeError("internal detail: password=hunter2")

    @app.get("/api/v1/_test/conflict")
    def conflict() -> None:
        raise ProblemError(409, "Already taken", "That username is in use.", code="username_taken")

    @app.get("/api/v1/_test/limited/{code}", dependencies=[Depends(limit_by_ip("test", 2, 60))])
    def limited(code: str) -> dict[str, str]:
        return {"ok": code[:0]}

    return app


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    with TestClient(build_app(db_session), raise_server_exceptions=False) as test_client:
        yield test_client


def assert_problem(response_json: dict[str, object], status: int) -> None:
    assert response_json["status"] == status
    assert isinstance(response_json["title"], str)
    assert response_json["type"] == "about:blank" or str(response_json["type"]).startswith(
        "https://"
    )
    uuid.UUID(str(response_json["request_id"]))


# --- the error format (RFC 9457) ------------------------------------------------------


def test_an_unknown_route_is_a_problem(client: TestClient) -> None:
    response = client.get("/api/v1/nothing-here")

    assert response.status_code == 404
    assert response.headers["content-type"] == PROBLEM
    assert_problem(response.json(), 404)
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_a_service_problem_keeps_its_code(client: TestClient) -> None:
    body = client.get("/api/v1/_test/conflict").json()

    assert_problem(body, 409)
    assert (body["title"], body["detail"], body["code"]) == (
        "Already taken",
        "That username is in use.",
        "username_taken",
    )


def test_unknown_fields_are_refused_without_echoing_values(client: TestClient) -> None:
    # D-016: extra fields refused; the response never repeats what was sent.
    response = client.post(
        "/api/v1/_test/strict",
        json={"username": "ada.obi", "password": "short-secret-1", "is_admin": True},
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == PROBLEM
    assert_problem(response.json(), 422)
    locations = sorted(error["loc"] for error in response.json()["errors"])
    assert locations == [["body", "is_admin"], ["body", "password"]]
    assert "short-secret-1" not in response.text


def test_a_database_rule_never_leaks_its_message(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    # MEMORY: PostgreSQL quotes values in its messages; only the SQLSTATE is logged.
    with caplog.at_level(logging.WARNING):
        response = client.post("/api/v1/_test/database-rule")

    assert response.status_code == 409
    assert response.json()["code"] == "ck_schools_code_format"
    assert "lowercase-secret-value" not in response.text
    logged = [r.fields for r in caplog.records if r.name == "schoolflow.errors"]  # type: ignore[attr-defined]
    assert logged == [{"sqlstate": "23514", "constraint": "ck_schools_code_format"}]
    assert "lowercase-secret-value" not in caplog.text


def test_a_crash_shows_nothing_inside(client: TestClient) -> None:
    response = client.get("/api/v1/_test/crash")

    assert response.status_code == 500
    assert response.headers["content-type"] == PROBLEM
    assert_problem(response.json(), 500)
    assert "hunter2" not in response.text
    assert "internal detail" not in response.text
    assert response.headers["x-content-type-options"] == "nosniff"


# --- headers, CORS, docs, request IDs ------------------------------------------------


def test_every_response_has_the_security_headers(client: TestClient) -> None:
    headers = client.get("/api/v1/health").headers

    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert headers["cross-origin-resource-policy"] == "same-origin"
    assert headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in headers  # local runs on http


def test_staging_and_production_insist_on_https(db_session: Session) -> None:
    with TestClient(build_app(db_session, "staging")) as staging:
        headers = staging.get("/api/v1/health").headers

    assert headers["strict-transport-security"] == "max-age=63072000; includeSubDomains"


def test_other_sites_cannot_call_the_api(client: TestClient) -> None:
    # Same domain only (D-015): no CORS headers are ever sent.
    response = client.options(
        "/api/v1/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(("app_env", "status"), [("local", 200), ("staging", 404)])
def test_the_docs_page_is_local_only(db_session: Session, app_env: str, status: int) -> None:
    # D-020.
    with TestClient(build_app(db_session, app_env)) as test_client:
        assert test_client.get("/api/v1/docs").status_code == status
        assert test_client.get("/api/v1/openapi.json").status_code == status


def test_each_request_gets_its_own_id(client: TestClient) -> None:
    first = client.get("/api/v1/health", headers={"X-Request-ID": "attacker-chosen"})
    second = client.get("/api/v1/health")

    ids = {first.headers["x-request-id"], second.headers["x-request-id"]}
    assert len(ids) == 2
    assert "attacker-chosen" not in ids


# --- logs (D-124) ---------------------------------------------------------------------


def test_logs_redact_secrets_and_personal_data() -> None:
    cleaned = redact(
        {
            "password": "correct-horse-battery",
            "new_password": "x",
            "token": "abc",
            "csrf_token": "abc",
            "cookie": "sf=1",
            "email": "ada@example.com",
            "full_name": "Ada Obi",
            "scores": [12, 14],
            "nested": {"Authorization": "Bearer abc", "school_id": "keep"},
            "note": "sent to ada@example.com",
        }
    )

    assert cleaned == {
        "password": "[redacted]",
        "new_password": "[redacted]",
        "token": "[redacted]",
        "csrf_token": "[redacted]",
        "cookie": "[redacted]",
        "email": "[redacted]",
        "full_name": "[redacted]",
        "scores": "[redacted]",
        "nested": {"Authorization": "[redacted]", "school_id": "keep"},
        "note": "sent to [email]",
    }


def test_a_log_line_is_json_with_the_request_id() -> None:
    record = logging.LogRecord("schoolflow", logging.INFO, __file__, 1, "Reset for %s", None, None)
    record.args = ("ada@example.com",)
    record.request_id = "r-1"
    record.fields = {"password": "x", "status": 200}

    line = json.loads(JsonFormatter().format(record))

    assert line["message"] == "Reset for [email]"
    assert (line["level"], line["request_id"], line["password"], line["status"]) == (
        "INFO",
        "r-1",
        "[redacted]",
        200,
    )


def test_the_access_log_names_the_route_not_the_path(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    # A verification code in the URL never reaches the logs.
    with caplog.at_level(logging.INFO, logger="schoolflow.access"):
        client.get("/api/v1/_test/limited/7KQ4M2XDP9QA?x=secret")

    access = [r for r in caplog.records if r.name == "schoolflow.access"]
    assert access[-1].fields["route"] == "/api/v1/_test/limited/{code}"  # type: ignore[attr-defined]
    assert "7KQ4M2XDP9QA" not in caplog.text
    assert "secret" not in caplog.text


# --- readiness (D-126) ----------------------------------------------------------------


def test_ready_checks_the_database(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")

    assert (response.status_code, response.json()) == (200, {"status": "ok"})


def test_ready_says_when_the_database_is_down(db_session: Session) -> None:
    class Down:
        def execute(self, *_: object) -> None:
            raise OperationalError("select 1", {}, Exception("connection refused"))

    app = build_app(db_session)
    app.dependency_overrides[get_db] = lambda: Down()
    with TestClient(app) as test_client:
        response = test_client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.headers["content-type"] == PROBLEM
    assert "connection refused" not in response.text


# --- rate limits (D-021, D-042) -------------------------------------------------------


def test_the_limit_counts_hits_per_key(db_session: Session) -> None:
    limiter = RateLimiter.for_session(db_session)

    waits = [limiter.hit("login:ip:192.0.2.1", 3, 60) for _ in range(4)]
    other = limiter.hit("login:ip:192.0.2.2", 3, 60)

    assert waits[:3] == [0, 0, 0]
    assert 1 <= waits[3] <= 60
    assert other == 0


def test_the_limit_starts_again_after_the_window(db_session: Session) -> None:
    limiter = RateLimiter.for_session(db_session)
    for _ in range(2):
        limiter.hit("verify:ip:192.0.2.9", 1, 60)
    db_session.execute(
        text("update rate_limit_buckets set window_started_at = now() - interval '61 seconds'")
    )

    assert limiter.hit("verify:ip:192.0.2.9", 1, 60) == 0


def test_keys_are_stored_only_as_keyed_hashes(db_session: Session) -> None:
    key = "login:id:ada@example.com"
    RateLimiter.for_session(db_session, b"fictional-test-secret").hit(key, 5, 60)

    stored = db_session.scalar(text("select key_hash from rate_limit_buckets"))
    assert stored == hmac.new(b"fictional-test-secret", key.encode(), hashlib.sha256).digest()


@pytest.mark.parametrize("role", ["app_user", "app_platform", "app_verifier"])
def test_app_roles_count_hits_but_never_read_them(db_session: Session, role: str) -> None:
    with acting_as(db_session, role):
        assert RateLimiter.for_session(db_session).hit("x", 5, 60) == 0
        with refused(db_session):
            db_session.execute(text("select count(*) from rate_limit_buckets"))


def test_the_sender_role_has_no_limits_to_count(db_session: Session) -> None:
    with acting_as(db_session, "app_sender"), refused(db_session):
        RateLimiter.for_session(db_session).hit("x", 5, 60)


def test_too_many_requests_is_a_problem_with_retry_after(client: TestClient) -> None:
    statuses = [client.get("/api/v1/_test/limited/a").status_code for _ in range(3)]
    blocked = client.get("/api/v1/_test/limited/a")

    assert statuses == [200, 200, 429]
    assert blocked.headers["content-type"] == PROBLEM
    assert 1 <= int(blocked.headers["retry-after"]) <= 60


def test_a_spoofed_forwarded_header_does_not_dodge_the_limit(db_session: Session) -> None:
    # Outside local, the IP comes only from Vercel's own header, which Vercel overwrites.
    with TestClient(build_app(db_session, "staging")) as staging:
        statuses = [
            staging.get(
                "/api/v1/_test/limited/a",
                headers={
                    "x-vercel-forwarded-for": "198.51.100.7",
                    "x-forwarded-for": f"10.0.0.{n}",
                },
            ).status_code
            for n in range(3)
        ]

    assert statuses == [200, 200, 429]


@pytest.mark.parametrize(
    ("app_env", "headers", "expected"),
    [
        ("staging", {"x-vercel-forwarded-for": "198.51.100.7"}, "198.51.100.7"),
        ("staging", {"x-vercel-forwarded-for": "198.51.100.7, 10.0.0.1"}, "198.51.100.7"),
        ("staging", {"x-forwarded-for": "10.0.0.1"}, "unknown"),
        ("local", {"x-vercel-forwarded-for": "198.51.100.7"}, "testclient"),
    ],
)
def test_the_client_ip(
    db_session: Session, app_env: str, headers: dict[str, str], expected: str
) -> None:
    app = build_app(db_session, app_env)
    seen: list[str] = []

    @app.get("/api/v1/_test/ip")
    def ip(request_ip: Annotated[str, Depends(client_ip)]) -> None:
        seen.append(request_ip)

    with TestClient(app) as test_client:
        test_client.get("/api/v1/_test/ip", headers=headers)

    assert seen == [expected]
