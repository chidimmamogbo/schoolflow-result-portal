"""Two-factor login for the super admin (CHANGE D, D-043, D-183; SPEC F02 rule 11).

Like a bank's token: after the password on /platform/login, the super admin
also types the 6-digit code their authenticator app shows (Google
Authenticator, Microsoft Authenticator and others follow RFC 6238). Until
then the session is only "half signed in": it lasts 5 minutes and every route
refuses it except these and logout.

- **Set-up** (first login, or after `reset-super-admin`): a new secret is
  shown as a QR code and as text; the first correct code confirms it and
  shows 10 one-time recovery codes, once.
- **Each login**: a code from the app, or one recovery code if the phone is lost.
- A code counts once (the database keeps the last 30-second step used); the
  app's clock may be 30 seconds out either way.
- Wrong codes count as failed logins (D-042), with the same growing delays.

The secret is encrypted (AES-GCM) with TOTP_ENCRYPTION_KEY before the
database sees it; recovery codes are stored as HMAC hashes only. Library:
pyotp 2.10.0, pinned (Chidimma, 2026-11-20).
"""

import base64
import hmac
import io
import os
import secrets
import time
from collections.abc import Callable

import pyotp
import segno
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import SignedIn
from app.core.errors import ProblemError, problem_response
from app.core.security import new_token, token_hash
from app.src.auth import services as auth
from app.src.two_factor.schemas import (
    CodesLeft,
    NewRecoveryCodes,
    Passed,
    SetUp,
)

STEP_SECONDS = 30
PENDING_SECONDS = 5 * 60
ISSUER = "SchoolFlow"
RECOVERY_COUNT = 10
# Crockford Base32 without look-alikes (no I, L, O, U), as in report codes (D-072).
RECOVERY_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
# Ties the encrypted secret to its purpose, so it cannot be swapped for another value.
AAD = b"schoolflow:totp:v1"

CODE_FAILED = ProblemError(
    401, "That code didn't work. Check the app and try again.", code="code_failed"
)
NOT_SET_UP = ProblemError(
    503, "Two-factor login is not set up on this server.", code="two_factor_unavailable"
)
NO_WAITING_LOGIN = ProblemError(401, "Please log in", code="not_signed_in")
ALREADY_ON = ProblemError(409, "Two-factor login is already set up.", code="two_factor_on")
NOT_ON = ProblemError(409, "Set up two-factor login first.", code="two_factor_off")

Clock = Callable[[], float]


class Cipher:
    """AES-GCM with the server's TOTP_ENCRYPTION_KEY (32 bytes)."""

    def __init__(self, key: bytes) -> None:
        self._aead = AESGCM(key)

    def seal(self, secret: str) -> bytes:
        nonce = os.urandom(12)
        return nonce + self._aead.encrypt(nonce, secret.encode(), AAD)

    def open(self, sealed: bytes) -> str:
        try:
            return self._aead.decrypt(sealed[:12], sealed[12:], AAD).decode()
        except InvalidTag:
            # Wrong key or changed data: the secret cannot be used.
            raise NOT_SET_UP from None


def cipher_from(encoded: str | None) -> Cipher:
    if not encoded:
        raise NOT_SET_UP
    return Cipher(base64.urlsafe_b64decode(encoded.encode()))


# --- codes --------------------------------------------------------------------------


def matching_step(secret: str, code: str, now: float) -> int | None:
    """The 30-second step whose code this is (now, or one step either side)."""
    digits = "".join(code.split())
    if len(digits) != 6 or not digits.isdigit():
        return None
    totp = pyotp.TOTP(secret, interval=STEP_SECONDS)
    for offset in (-1, 0, 1):
        moment = int(now) + offset * STEP_SECONDS
        if hmac.compare_digest(totp.at(moment), digits):
            return int(moment // STEP_SECONDS)
    return None


def new_recovery_codes() -> list[str]:
    """Ten codes like 7KQ4M-2XDP9: 50 random bits each."""
    codes: list[str] = []
    for _ in range(RECOVERY_COUNT):
        raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def recovery_hash(code: str) -> bytes:
    """Hyphens, spaces and case do not matter when typing a code back."""
    cleaned = "".join(ch for ch in code.upper() if ch.isalnum())
    return token_hash(f"recovery:{cleaned}")


def qr_svg(uri: str) -> str:
    out = io.BytesIO()
    segno.make(uri, error="m").save(out, kind="svg", scale=5, border=2, xmldecl=False)
    return out.getvalue().decode()


# --- the half-signed-in step ---------------------------------------------------------


def waiting(signed_in: SignedIn) -> SignedIn:
    """Only a super admin's session that still waits for its code."""
    if not (signed_in.second_factor_pending and signed_in.is_super_admin):
        raise NO_WAITING_LOGIN
    return signed_in


def state(session: Session) -> tuple[bytes | None, bool]:
    row = session.execute(text("select secret, confirmed from auth_totp_state()")).first()
    if row is None:
        return None, False
    return row.secret, bool(row.confirmed)


def code_failed() -> JSONResponse:
    """Returned, not raised: a raised error rolls the request back, and the failure
    must be counted (D-042), as the password login does."""
    return problem_response(CODE_FAILED.status, CODE_FAILED.title, code="code_failed")


def check_code(session: Session, signed_in: SignedIn, secret: str, code: str, clock: Clock) -> bool:
    """A right, unused code (cleared count), or False with the failure counted."""
    key = auth.throttle_key(f"account:{signed_in.user_id}")
    if auth.seconds_locked(session, key) > 0:
        return False
    step = matching_step(secret, code, clock())
    if step is None or not session.scalar(text("select auth_totp_use_step(:step)"), {"step": step}):
        auth.record_failure(session, key)
        return False
    auth.clear(session, key)
    return True


def pass_second_factor(session: Session, signed_in: SignedIn, response: Response) -> None:
    """The waiting session becomes a full one under a new token (D-037)."""
    token = new_token()
    lifetime = auth.SESSION_SECONDS[True]
    if not session.scalar(
        text("select auth_second_factor_passed(:id, :hash, :lifetime)"),
        {"id": signed_in.session_id, "hash": token_hash(token), "lifetime": lifetime},
    ):
        raise NO_WAITING_LOGIN
    auth.set_session_cookies(response, token, lifetime)


def username_of(session: Session, user_id: object) -> str:
    return str(session.scalar(text("select username from users where id = :id"), {"id": user_id}))


# --- routes' work ---------------------------------------------------------------------


def start_setup(signed_in: SignedIn, session: Session, cipher: Cipher) -> SetUp:
    """A secret to scan; the same one again until it is confirmed."""
    waiting(signed_in)
    sealed, confirmed = state(session)
    if confirmed:
        raise ALREADY_ON
    if sealed is None:
        secret = pyotp.random_base32()
        session.execute(text("select auth_totp_start(:s)"), {"s": cipher.seal(secret)})
    else:
        secret = cipher.open(sealed)
    totp = pyotp.TOTP(secret, interval=STEP_SECONDS)
    uri: str = totp.provisioning_uri(  # pyright: ignore[reportUnknownMemberType]
        name=username_of(session, signed_in.user_id), issuer_name=ISSUER
    )
    return SetUp(secret=secret, qr_svg=qr_svg(uri))


def finish_setup(
    code: str,
    signed_in: SignedIn,
    session: Session,
    response: Response,
    cipher: Cipher,
    clock: Clock,
) -> NewRecoveryCodes | JSONResponse:
    waiting(signed_in)
    sealed, confirmed = state(session)
    if confirmed:
        raise ALREADY_ON
    if sealed is None:
        raise NOT_ON
    if not check_code(session, signed_in, cipher.open(sealed), code, clock):
        return code_failed()
    codes = new_recovery_codes()
    session.execute(
        text("select auth_totp_confirm(:hashes)"),
        {"hashes": [recovery_hash(c) for c in codes]},
    )
    pass_second_factor(session, signed_in, response)
    return NewRecoveryCodes(
        recovery_codes=codes, must_change_password=signed_in.must_change_password
    )


def verify(
    code: str,
    signed_in: SignedIn,
    session: Session,
    response: Response,
    cipher: Cipher,
    clock: Clock,
) -> Passed | JSONResponse:
    waiting(signed_in)
    sealed, confirmed = state(session)
    if sealed is None or not confirmed:
        raise NOT_ON
    if not check_code(session, signed_in, cipher.open(sealed), code, clock):
        return code_failed()
    pass_second_factor(session, signed_in, response)
    return Passed(must_change_password=signed_in.must_change_password)


def use_recovery(
    code: str, signed_in: SignedIn, session: Session, response: Response
) -> CodesLeft | JSONResponse:
    waiting(signed_in)
    key = auth.throttle_key(f"account:{signed_in.user_id}")
    if auth.seconds_locked(session, key) > 0:
        return code_failed()
    if not session.scalar(text("select auth_recovery_use(:h)"), {"h": recovery_hash(code)}):
        auth.record_failure(session, key)
        return code_failed()
    auth.clear(session, key)
    pass_second_factor(session, signed_in, response)
    left = int(session.scalar(text("select auth_recovery_left()")) or 0)
    return CodesLeft(codes_left=left, must_change_password=signed_in.must_change_password)


def codes_left(session: Session) -> CodesLeft:
    left = int(session.scalar(text("select auth_recovery_left()")) or 0)
    return CodesLeft(codes_left=left, must_change_password=False)


def replace_codes(
    code: str, signed_in: SignedIn, session: Session, cipher: Cipher, clock: Clock
) -> NewRecoveryCodes | JSONResponse:
    """New recovery codes for a signed-in super admin, after a fresh code."""
    sealed, confirmed = state(session)
    if sealed is None or not confirmed:
        raise NOT_ON
    if not check_code(session, signed_in, cipher.open(sealed), code, clock):
        return code_failed()
    codes = new_recovery_codes()
    session.execute(
        text("select auth_recovery_replace(:hashes)"),
        {"hashes": [recovery_hash(c) for c in codes]},
    )
    return NewRecoveryCodes(recovery_codes=codes, must_change_password=False)


def system_clock() -> float:
    return time.time()
