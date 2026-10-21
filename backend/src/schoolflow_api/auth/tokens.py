"""Session and CSRF tokens (D-037, D-038, D-039).

A session token is 32 random bytes (256 bits) in the `__Host-sf_session`
cookie; the database keeps only HMAC-SHA256(APP_SECRET_KEY, token), so a
copy of the database cannot be used to sign in. Links in emails are hashed
the same way.

The CSRF token is worked out from the session token with a different HMAC
label ("signed double submit", OWASP CSRF Prevention Cheat Sheet): the
frontend copies the `__Host-sf_csrf` cookie into the X-CSRF-Token header,
and only a page on our own site can read that cookie. A token from another
session never matches.
"""

import hashlib
import hmac
import secrets

from schoolflow_api.settings import get_settings

SESSION_COOKIE = "__Host-sf_session"
CSRF_COOKIE = "__Host-sf_csrf"
CSRF_HEADER = "X-CSRF-Token"


def _secret() -> bytes:
    return get_settings().app_secret_key.get_secret_value().encode()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> bytes:
    return hmac.new(_secret(), token.encode(), hashlib.sha256).digest()


def csrf_token(session_token: str) -> str:
    return hmac.new(_secret(), b"csrf:" + session_token.encode(), hashlib.sha256).hexdigest()


def csrf_matches(session_token: str, sent: str | None) -> bool:
    return sent is not None and hmac.compare_digest(csrf_token(session_token), sent)
