"""Shared pytest fixtures. pytest loads this file automatically before any test.

`db_session` gives a test a database session on the real test database
(schoolflow_test in Docker, D-030). Everything the test writes is rolled back
at the end, so every test starts from the same clean state and tests never
depend on each other's data.
"""

import os
from collections.abc import Callable, Generator, Iterator
from contextlib import AbstractContextManager, contextmanager

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from schoolflow_api.db import make_engine

# The local Docker test database from compose.yaml (a local-only password).
# CI sets TEST_DATABASE_URL to its own throwaway service database.
LOCAL_TEST_DATABASE_URL = (
    "postgresql+psycopg://schoolflow_owner:local_dev_only@127.0.0.1:5432/schoolflow_test"
)


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """One connection pool for the whole test run."""
    engine = make_engine(os.environ.get("TEST_DATABASE_URL", LOCAL_TEST_DATABASE_URL))
    try:
        engine.connect().close()
    except OperationalError:
        pytest.fail(
            "Cannot reach the test database. Start it from the repo root with: "
            "docker compose up -d --wait",
            pytrace=False,
        )
    yield engine
    engine.dispose()


@contextmanager
def rolled_back_session(engine: Engine) -> Generator[Session]:
    """A session inside an outer transaction that is always rolled back.

    Recipe from the SQLAlchemy 2.1 docs, "Joining a Session into an External
    Transaction (such as for test suites)" (checked 2026-10-12): with
    join_transaction_mode="create_savepoint", a commit inside the code under
    test only releases a savepoint, and the outer rollback still undoes it.
    """
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def make_rolled_back_session() -> Callable[[Engine], AbstractContextManager[Session]]:
    """For tests that check the rollback itself (see test_database.py)."""
    return rolled_back_session


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    with rolled_back_session(db_engine) as session:
        yield session
