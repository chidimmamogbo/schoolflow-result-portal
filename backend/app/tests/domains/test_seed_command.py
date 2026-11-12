"""The demo seed command, `python -m app.cli.demo` (BUILD_PROMPT 9.2v; D-180).

Behaviour: the command takes the demo password from SEED_PASSWORD only (never
an argument, never printed), checks it against the staff password rules,
refuses to run outside local development unless --allow-outside-local is
given, makes the super admin `platform.admin` with that password if missing
(an existing one is left alone), then runs the seed. A seed that stops says
why and exits with 1. All data is fictional.
"""

from collections.abc import Callable, Generator
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.cli.demo.__main__ import main
from app.cli.demo.browser import SeedError
from app.tests.auth_support import make_login, use_fast_hashing

DEMO_PASSWORD = "harmattan-kettle-blue-river"  # noqa: S105 (fictional; 27 characters)


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


class Run:
    def __init__(self, db: Session, env: str = "local") -> None:
        self.db = db
        self.env = env
        self.printed: list[str] = []
        self.seeded: list[str] = []
        self.fail: str | None = None

    def seed(self, password: str, out: Callable[[str], None]) -> None:
        if self.fail is not None:
            raise SeedError(self.fail)
        self.seeded.append(password)

    def __call__(self, *args: str) -> int:
        @contextmanager
        def connect() -> Generator[Session]:
            yield self.db

        return main(
            list(args),
            connect=connect,
            out=self.printed.append,
            environment=lambda: self.env,
            seed=self.seed,
        )

    @property
    def output(self) -> str:
        return "\n".join(self.printed)


def super_admin(db: Session) -> bool | None:
    return db.scalar(text("select is_super_admin from users where username = 'platform.admin'"))


def test_it_seeds_with_the_password_from_the_environment(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEED_PASSWORD", DEMO_PASSWORD)
    run = Run(db_session)
    assert run() == 0
    assert run.seeded == [DEMO_PASSWORD]
    assert super_admin(db_session) is True
    assert DEMO_PASSWORD not in run.output


def test_an_existing_super_admin_is_left_alone(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_login(db_session, username="platform.admin", full_name="Platform Admin",
               is_super_admin=True)  # fmt: skip
    before = db_session.scalar(
        text("select password_hash from users where username = 'platform.admin'")
    )
    monkeypatch.setenv("SEED_PASSWORD", DEMO_PASSWORD)
    run = Run(db_session)
    assert run() == 0
    after = db_session.scalar(
        text("select password_hash from users where username = 'platform.admin'")
    )
    assert after == before


def test_without_seed_password_nothing_happens(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SEED_PASSWORD", raising=False)
    run = Run(db_session)
    assert run() == 2
    assert "SEED_PASSWORD" in run.output
    assert run.seeded == [] and super_admin(db_session) is None


def test_a_weak_seed_password_is_refused(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEED_PASSWORD", "short-one")
    run = Run(db_session)
    assert run() == 2
    assert run.seeded == [] and "short-one" not in run.output


@pytest.mark.parametrize("env", ["staging", "production"])
def test_outside_local_it_needs_to_be_asked_for(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, env: str
) -> None:
    monkeypatch.setenv("SEED_PASSWORD", DEMO_PASSWORD)
    run = Run(db_session, env)
    assert run() == 1
    assert "--allow-outside-local" in run.output
    assert run.seeded == [] and super_admin(db_session) is None
    assert run("--allow-outside-local") == 0
    assert run.seeded == [DEMO_PASSWORD]


def test_a_seed_that_stops_says_why(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEED_PASSWORD", DEMO_PASSWORD)
    run = Run(db_session)
    run.fail = "The database already has schools. Seed an empty database."
    assert run() == 1
    assert "already has schools" in run.output
