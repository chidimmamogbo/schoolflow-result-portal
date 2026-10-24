"""Tests for the database connection and the test fixture (D-017, D-030).

Behaviour: tests run on real PostgreSQL 17, each test's writes are rolled
back (even if the code under test calls commit), and SQLAlchemy never adds
SQL parameter values (which can hold passwords, tokens or scores) to its
error messages.

Note: PostgreSQL's own message can still quote a value (for example
`invalid input syntax for type integer: "..."` or a unique violation's
`Key (email)=(...)`). The engine cannot stop that, so the error handler and
log redaction (BUILD_PROMPT 9.2a) must never log or return raw database
error text.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

EXISTS = text("select to_regclass(:name) is not null")


def table_exists(engine: Engine, name: str) -> bool:
    with engine.connect() as connection:
        return bool(connection.scalar(EXISTS, {"name": name}))


def test_database_is_postgres_17(db_session: Session) -> None:
    version = db_session.scalar(text("show server_version_num"))

    assert version is not None
    assert version.startswith("17")


def test_writes_are_rolled_back_after_each_test(
    db_engine: Engine,
    make_rolled_back_session: Callable[[Engine], AbstractContextManager[Session]],
) -> None:
    with make_rolled_back_session(db_engine) as session:
        session.execute(text("create table rollback_probe (id int)"))
        session.execute(text("insert into rollback_probe values (1)"))
        # Code under test may commit; that only releases a savepoint.
        session.commit()
        assert session.scalar(EXISTS, {"name": "rollback_probe"})

    # Seen from a brand-new connection, nothing was kept.
    assert not table_exists(db_engine, "rollback_probe")


def test_parameter_values_are_hidden_in_errors(db_session: Session) -> None:
    # Invalid case: the query fails (division by zero) for a reason that has
    # nothing to do with the value, so the value could only appear through
    # SQLAlchemy's "[parameters: ...]" section, which must be hidden.
    with pytest.raises(DBAPIError) as error:
        db_session.execute(text("select cast(:value as text), 1 / 0"), {"value": "pw-Adaeze-0001"})

    message = str(error.value)
    assert "division by zero" in message
    assert "pw-Adaeze-0001" not in message
