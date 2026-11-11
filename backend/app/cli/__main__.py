"""`python -m app.cli`: reads the command, asks for the password, runs it.

Passwords are typed at a hidden prompt (twice) or read from an environment
variable whose name is given with --password-env; they are never accepted as
a command-line argument (it would land in the shell history) and never printed.

Exit codes: 0 done, 1 refused, 2 the input was wrong.
"""

import argparse
import getpass
import os
import sys
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager

from sqlalchemy.orm import Session

from app.cli.super_admin import (
    BadPasswordError,
    RefusedError,
    create_super_admin,
    reset_super_admin,
)

Connect = Callable[[], AbstractContextManager[Session]]


@contextmanager
def owner_session() -> Generator[Session]:
    """One transaction on the owner connection, committed when the command succeeds."""
    from app.core.config import load_migration_settings
    from app.db.session import make_engine

    url = load_migration_settings().database_url_migrations.get_secret_value()
    engine = make_engine(url)
    try:
        with Session(engine) as session, session.begin():
            yield session
    finally:
        engine.dispose()


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="python -m app.cli", exit_on_error=False)
    commands = top.add_subparsers(dest="command")
    create = commands.add_parser("create-super-admin", help="Make a platform super admin.")
    create.add_argument("--username", required=True)
    create.add_argument("--full-name", required=True)
    create.add_argument("--email")
    create.add_argument("--password-env", metavar="NAME", help="Read the password from $NAME.")
    reset = commands.add_parser("reset-super-admin", help="Give a super admin a new password.")
    reset.add_argument("--username", required=True)
    reset.add_argument("--password-env", metavar="NAME", help="Read the password from $NAME.")
    return top


class InputError(Exception):
    pass


def read_password(name: str | None, ask: Callable[[str], str]) -> str:
    if name:
        value = os.environ.get(name)
        if not value:
            raise InputError(f"The environment variable {name} is not set.")
        return value
    first = ask("New password: ")
    if ask("Type it again: ") != first:
        raise InputError("The two passwords do not match. Nothing was changed.")
    return first


def main(
    argv: list[str] | None = None,
    *,
    connect: Connect = owner_session,
    ask: Callable[[str], str] = getpass.getpass,
    out: Callable[[str], None] = print,
) -> int:
    top = parser()
    try:
        args = top.parse_args(argv)
    except argparse.ArgumentError, SystemExit:
        out(top.format_help())
        return 2
    if args.command is None:
        out(top.format_help())
        return 2
    try:
        password = read_password(args.password_env, ask)
        with connect() as session:
            if args.command == "create-super-admin":
                create_super_admin(
                    session,
                    username=args.username,
                    full_name=args.full_name,
                    email=args.email,
                    password=password,
                )
                out(f"Super admin {args.username} is ready. They can log in now.")
            else:
                reset_super_admin(session, username=args.username, password=password)
                out(f"{args.username} has a new password and is signed out everywhere.")
    except (InputError, BadPasswordError) as problem:
        out(str(problem))
        return 2
    except RefusedError as refusal:
        out(str(refusal))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
