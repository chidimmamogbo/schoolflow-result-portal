"""Rate limits counted in PostgreSQL (D-021, D-042).

Serverless instances share no memory, so counts live in the database, in
`rate_limit_buckets`, touched only by the owner-run function
`rate_limit_hit()` (migration 19). Keys such as "login:ip:198.51.100.7" are
turned into a keyed hash (HMAC with APP_SECRET_KEY) before they leave Python,
so the table never holds an IP address or an email.

Each hit is counted in its own short transaction (`for_engine`), so a hit
still counts when the request itself fails and rolls back.
"""

import hashlib
import hmac
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ProblemError

HIT = text(
    "select rate_limit_hit(:key_hash, cast(:max_hits as integer), cast(:window_seconds as integer))"
)
Runner = Callable[[bytes, int, int], int]


class RateLimiter:
    def __init__(self, run: Runner, secret: bytes) -> None:
        self._run = run
        self._secret = secret

    @classmethod
    def for_engine(cls, engine: Engine, secret: bytes) -> RateLimiter:
        def run(key_hash: bytes, max_hits: int, window_seconds: int) -> int:
            with engine.begin() as connection:
                wait = connection.scalar(HIT, _params(key_hash, max_hits, window_seconds))
            return int(wait or 0)

        return cls(run, secret)

    @classmethod
    def for_session(cls, session: Session, secret: bytes | None = None) -> RateLimiter:
        """Counts inside an existing session (tests: rolled back afterwards)."""

        def run(key_hash: bytes, max_hits: int, window_seconds: int) -> int:
            return int(session.scalar(HIT, _params(key_hash, max_hits, window_seconds)) or 0)

        return cls(run, secret or _secret())

    def hit(self, key: str, max_hits: int, window_seconds: int) -> int:
        """Count one hit; 0 means go ahead, otherwise the seconds to wait."""
        key_hash = hmac.new(self._secret, key.encode(), hashlib.sha256).digest()
        return self._run(key_hash, max_hits, window_seconds)


def _params(key_hash: bytes, max_hits: int, window_seconds: int) -> dict[str, object]:
    return {"key_hash": key_hash, "max_hits": max_hits, "window_seconds": window_seconds}


def _secret() -> bytes:
    return get_settings().app_secret_key.get_secret_value().encode()


def client_ip(request: Request) -> str:
    """The caller's IP: outside local, only from Vercel's own header.

    Vercel overwrites x-forwarded-for and x-vercel-forwarded-for with the real
    client IP to prevent spoofing (vercel.com/docs/headers/request-headers,
    checked 2026-10-15); x-vercel-forwarded-for also survives a proxy in front.
    """
    if request.app.state.app_env == "local":
        return request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-vercel-forwarded-for", "")
    return forwarded.split(",")[0].strip() or "unknown"


def limit_by_ip(name: str, max_hits: int, window_seconds: int) -> Callable[..., None]:
    """A route dependency: at most `max_hits` per IP per window, then 429."""
    # Imported here: deps imports this module (a cycle at import time).
    from app.core.dependencies import get_rate_limiter

    def check(
        ip: Annotated[str, Depends(client_ip)],
        limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    ) -> None:
        wait = limiter.hit(f"{name}:ip:{ip}", max_hits, window_seconds)
        if wait:
            raise ProblemError(
                429,
                "Too many attempts",
                "Please wait a little and try again.",
                headers={"Retry-After": str(wait)},
            )

    return check
