"""Temporary passwords: four random words, shown once (D-040).

Words come from EFF's short word list 1 (1,296 everyday words, CC BY 3.0,
eff.org/dice; "yo-yo" left out because words are joined with dashes), so a
slip reads like "acorn-blimp-cozy-dwarf" and is easy to type on a phone.
Four words from 1,295 give about 41 bits: enough for a password that must
be changed at first login and expires after 7 days, behind throttling.
Only its Argon2id hash is stored.
"""

import secrets
from functools import cache
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.auth.passwords import hash_password

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
