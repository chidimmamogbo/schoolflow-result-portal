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

from enum import StrEnum
from functools import cache
from pathlib import Path

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

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
