"""Helpers for the test database.

At the start of every test run the test database is wiped and rebuilt with
`alembic upgrade head`, so tests always run on exactly the schema that will
run on Neon (D-030: a fresh database per test run).

`acting_as` and `refused` let a test run SQL as one of the app's database
roles and expect PostgreSQL to refuse something (D-137).
"""

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from schoolflow_api.db import use_context

BACKEND_DIR = Path(__file__).resolve().parent.parent

# The roles the app logs in as (D-026, D-051). Never the owner, which skips RLS.
APP_ROLES = ("app_platform", "app_user", "app_verifier")
_SET_ROLE = {role: text(f"set local role {role}") for role in APP_ROLES}

# PostgreSQL's code for "permission denied", used for missing grants and for
# rows that row-level security refuses to write.
INSUFFICIENT_PRIVILEGE = "42501"


def alembic_config(connection: Connection) -> Config:
    """Alembic settings from pyproject.toml, using this connection (not .env)."""
    config = Config(
        file_=BACKEND_DIR / "alembic.ini",
        toml_file=BACKEND_DIR / "pyproject.toml",
    )
    config.attributes["connection"] = connection
    return config


def assert_is_test_database(name: str) -> None:
    """Safety catch: never wipe a database that is not a test database."""
    if not name.endswith("_test") or name == "_test":
        raise RuntimeError(
            f"The test fixture only resets a database whose name ends in _test, not {name!r}."
        )


def reset_and_migrate(engine: Engine) -> None:
    """Drop every table, then build the schema again from the migrations."""
    with engine.begin() as connection:
        name = connection.scalar(text("select current_database()"))
        assert_is_test_database(str(name))
        connection.execute(text("drop schema public cascade"))
        connection.execute(text("create schema public"))
        command.upgrade(alembic_config(connection), "head")


@contextmanager
def acting_as(
    session: Session,
    role: str,
    *,
    school_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> Generator[None]:
    """Run the block as one of the app's database roles, for this school and user.

    SET LOCAL ROLE lasts until the test's transaction ends, and PostgreSQL then
    applies exactly the grants and row-level security rules that role has.
    """
    use_context(session, school_id=school_id, user_id=user_id)
    session.execute(_SET_ROLE[role])
    yield
    # Only reached when the block succeeded; after an error the test's own
    # rollback cleans up, and running SQL here would hide the real error.
    session.execute(text("reset role"))
    use_context(session)


@contextmanager
def refused(session: Session, sqlstate: str = INSUFFICIENT_PRIVILEGE) -> Generator[None]:
    """Expect PostgreSQL to refuse the block (by default: permission denied).

    The block runs inside a savepoint, so after the refusal the test can carry
    on in the same transaction, still as the same role.
    """
    with pytest.raises(DBAPIError) as error, session.begin_nested():
        yield
    original = error.value.orig
    assert isinstance(original, psycopg.Error)
    assert original.sqlstate == sqlstate, original


@contextmanager
def violates(session: Session, constraint: str) -> Generator[None]:
    """Expect the database to refuse the block because of this named rule.

    Works for constraints (unique, check, foreign key) and for trigger rules
    that name themselves with RAISE ... USING CONSTRAINT. Runs in a savepoint.
    """
    with pytest.raises(IntegrityError) as error, session.begin_nested():
        yield
    original = error.value.orig
    assert isinstance(original, psycopg.Error)
    assert original.diag.constraint_name == constraint, original
