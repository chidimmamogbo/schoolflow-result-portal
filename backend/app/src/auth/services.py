"""Growing delays after repeated failed logins (D-042; migration 20).

Five failures are free; then the account (or, when no account matched, the
typed name) waits 30 seconds, 1 minute, 5 minutes, then 15 minutes after each
further failure. There is no permanent lockout, so nobody can lock a real
teacher out for good by guessing on purpose. A successful login clears the
count; a day without failures starts it again. A locked login gets the same
generic answer as a wrong password (D-034).
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import token_hash

FREE_FAILURES = 5
DELAYS = (30, 60, 300, 900)

_WAIT = text("select login_throttle_wait(:key)")
_FAILED = text(
    "select login_throttle_failed(:key, cast(:free as integer), cast(:delays as integer[]))"
)
_CLEAR = text("select login_throttle_clear(:key)")


def delay_after(failures: int) -> int:
    """Seconds locked after this many failures in a row."""
    if failures < FREE_FAILURES:
        return 0
    return DELAYS[min(failures - FREE_FAILURES, len(DELAYS) - 1)]


def throttle_key(name: str) -> bytes:
    return token_hash(f"login-throttle:{name}")


def seconds_locked(session: Session, key: bytes) -> int:
    return int(session.scalar(_WAIT, {"key": key}) or 0)


def record_failure(session: Session, key: bytes) -> None:
    session.execute(_FAILED, {"key": key, "free": FREE_FAILURES, "delays": list(DELAYS)})


def clear(session: Session, key: bytes) -> None:
    session.execute(_CLEAR, {"key": key})
