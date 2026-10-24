"""Password hashing and password rules (D-035, D-036).

Hashes are Argon2id through pwdlib (like WordPress's wp_hash_password(), but
with a memory-hard algorithm). The cost is OWASP's first Argon2id setting
(46 MiB, 1 pass, 1 lane; OWASP Password Storage Cheat Sheet): pwdlib's own
defaults (64 MiB, 3 passes, 4 lanes) took about 2 seconds a check on the
development machine, too slow for a login on a small serverless instance.
`verify_password` returns a new hash when the cost changes, so raising it
later upgrades each account at its next login.

Rules: at least 15 characters (10 for students), at most 128, and not on the
bundled list of common passwords (common_passwords.txt: the entries of 10 or
more characters from SecLists' "100k-most-used-passwords-NCSC.txt", MIT
licence, lowercased; taken 2026-10-21).
"""

import hashlib
import hmac
import secrets
from enum import StrEnum
from functools import cache
from pathlib import Path

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings

MIN_LENGTH = 15
MIN_LENGTH_STUDENT = 10
MAX_LENGTH = 128

PASSWORD_HASH = PasswordHash((Argon2Hasher(memory_cost=47_104, time_cost=1, parallelism=1),))
_COMMON = Path(__file__).with_name("common_passwords.txt")


class PasswordProblem(StrEnum):
    TOO_SHORT = "password_too_short"
    TOO_LONG = "password_too_long"
    TOO_COMMON = "password_too_common"


def hash_password(password: str) -> str:
    return PASSWORD_HASH.hash(password)


@cache
def _dummy_hash(hasher: PasswordHash) -> str:
    return hasher.hash("no account has this password")


def verify_password(password: str, stored: str | None) -> tuple[bool, str | None]:
    """(matches, new hash or None). With no stored hash, checks a dummy one.

    The dummy check takes as long as a real one, so a missing account answers
    in the same time as a wrong password (D-034).
    """
    if stored is None:
        PASSWORD_HASH.verify(password, _dummy_hash(PASSWORD_HASH))
        return False, None
    return PASSWORD_HASH.verify_and_update(password, stored)


@cache
def _common_passwords() -> frozenset[str]:
    return frozenset(_COMMON.read_text(encoding="utf-8").split("\n")) - {""}


def is_common(password: str) -> bool:
    return password.lower() in _common_passwords()


def password_problem(password: str, *, student: bool) -> PasswordProblem | None:
    if len(password) < (MIN_LENGTH_STUDENT if student else MIN_LENGTH):
        return PasswordProblem.TOO_SHORT
    if len(password) > MAX_LENGTH:
        return PasswordProblem.TOO_LONG
    if is_common(password):
        return PasswordProblem.TOO_COMMON
    return None


# --- tokens ------------------------------------------------------------
# Session and CSRF tokens (D-037, D-038, D-039).
#
# A session token is 32 random bytes (256 bits) in the `__Host-sf_session`
# cookie; the database keeps only HMAC-SHA256(APP_SECRET_KEY, token), so a
# copy of the database cannot be used to sign in. Links in emails are hashed
# the same way.
#
# The CSRF token is worked out from the session token with a different HMAC
# label ("signed double submit", OWASP CSRF Prevention Cheat Sheet): the
# frontend copies the `__Host-sf_csrf` cookie into the X-CSRF-Token header,
# and only a page on our own site can read that cookie. A token from another
# session never matches.

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


# --- temporary ------------------------------------------------------------
# Temporary passwords: four random words, shown once (D-040).
#
# Words come from EFF's short word list 1 (1,296 everyday words, CC BY 3.0,
# eff.org/dice; "yo-yo" left out because words are joined with dashes), so a
# slip reads like "acorn-blimp-cozy-dwarf" and is easy to type on a phone.
# Four words from 1,295 give about 41 bits: enough for a password that must
# be changed at first login and expires after 7 days, behind throttling.
# Only its Argon2id hash is stored.

WORDS = 4
VALID_DAYS = 7
_LIST = Path(__file__).with_name("temporary_words.txt")


@cache
def _words() -> tuple[str, ...]:
    return tuple(word for word in _LIST.read_text(encoding="utf-8").split("\n") if word)


def new_temporary_password() -> str:
    words = _words()
    return "-".join(secrets.choice(words) for _ in range(WORDS))


def issue_temporary_password(session: Session, user_id: object) -> str:
    """Set a new temporary password and end every session; return it once."""
    password = new_temporary_password()
    session.execute(
        text(
            "update users set password_hash = :hash, must_change_password = true,"
            " temp_password_expires_at = now() + make_interval(days => :days)"
            " where id = :id"
        ),
        {"hash": hash_password(password), "days": VALID_DAYS, "id": user_id},
    )
    session.execute(text("delete from user_sessions where user_id = :id"), {"id": user_id})
    return password
