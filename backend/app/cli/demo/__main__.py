"""`python -m app.cli.demo`: builds the demo schools (D-180).

    SEED_PASSWORD=... uv run python -m app.cli.demo
    SEED_PASSWORD=... uv run python -m app.cli.demo --allow-outside-local

The password comes from SEED_PASSWORD only (never an argument, never
printed) and must meet the staff rules; every demo account uses it, and the
super admin `platform.admin` is made with it if missing. Outside local
development the command refuses unless --allow-outside-local is given. It
needs an empty database (no schools).

Exit codes: 0 done, 1 refused or stopped, 2 the input was wrong.
"""

import argparse
import os
import sys
from collections.abc import Callable

from sqlalchemy import text

from app.cli.__main__ import Connect, owner_session
from app.cli.demo.browser import SeedError
from app.cli.demo.platform import SUPER_ADMIN
from app.cli.demo.run import Say, real_seed
from app.cli.super_admin import BadPasswordError, check_password, create_super_admin

Seed = Callable[[str, Say], None]


def configured_environment() -> str:
    from app.core.config import get_settings

    return get_settings().app_env


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="python -m app.cli.demo", exit_on_error=False)
    top.add_argument(
        "--allow-outside-local",
        action="store_true",
        help="Seed a staging or production database (it must have no schools).",
    )
    return top


def ensure_super_admin(connect: Connect, password: str, say: Say) -> None:
    with connect() as session:
        exists = session.scalar(
            text("select exists (select 1 from users where username = :u)"), {"u": SUPER_ADMIN}
        )
        # The seed signs in as the super admin; it cannot know a real authenticator.
        if session.scalar(
            text("select totp_confirmed_at is not null from users where username = :u"),
            {"u": SUPER_ADMIN},
        ):
            raise SeedError(
                f"{SUPER_ADMIN} already has two-factor login. Seed a fresh database, or run"
                " reset-super-admin first."
            )
        if not exists:
            create_super_admin(
                session, username=SUPER_ADMIN, full_name="Platform Admin", email=None,
                password=password,
            )  # fmt: skip
            say(f"Super admin {SUPER_ADMIN} made.")


def forget_seed_authenticator(connect: Connect) -> None:
    """The seed set up two-factor only to sign in; your first real login sets up
    your own authenticator (D-043)."""
    with connect() as session:
        user_id = session.scalar(
            text("select id from users where username = :u"), {"u": SUPER_ADMIN}
        )
        session.execute(
            text(
                "update users set totp_secret = null, totp_confirmed_at = null,"
                " totp_last_step = null where id = :id"
            ),
            {"id": user_id},
        )
        session.execute(text("delete from recovery_codes where user_id = :id"), {"id": user_id})
        session.execute(text("delete from user_sessions where user_id = :id"), {"id": user_id})


def main(
    argv: list[str] | None = None,
    *,
    connect: Connect = owner_session,
    out: Say = print,
    environment: Callable[[], str] = configured_environment,
    seed: Seed = real_seed,
) -> int:
    top = parser()
    try:
        args = top.parse_args(argv)
    except argparse.ArgumentError, SystemExit:
        out(top.format_help())
        return 2
    password = os.environ.get("SEED_PASSWORD")
    if not password:
        out("Set SEED_PASSWORD first: every demo account uses it.")
        return 2
    try:
        check_password(password)
    except BadPasswordError as problem:
        out(f"SEED_PASSWORD: {problem}")
        return 2
    env = environment()
    if env != "local" and not args.allow_outside_local:
        out(f"This is {env}, not local. Add --allow-outside-local to seed it on purpose.")
        return 1
    try:
        ensure_super_admin(connect, password, out)
        seed(password, out)
        forget_seed_authenticator(connect)
    except SeedError as stopped:
        out(f"The seed stopped: {stopped}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
