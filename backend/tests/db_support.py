"""Helpers for building the test database from the migrations.

At the start of every test run the test database is wiped and rebuilt with
`alembic upgrade head`, so tests always run on exactly the schema that will
run on Neon (D-030: a fresh database per test run).
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent


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
