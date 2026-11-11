"""The demo seed (BUILD_PROMPT 9.2v; ACCEPTANCE_TESTS fixtures; D-180).

Behaviour, round 1: the seed signs in as the super admin and, through the
app's own routes, saves the default price list as version 1 and creates GMC
(Secondary only, every feature on, billing on), BSA (Nursery and Primary,
Correction queue off, free pilot) and RCS (all levels), each with a principal
who signs in once with a temporary password and then uses the demo password.
It refuses to run twice. All data is fictional.
"""

from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.cli.demo.browser import Demo, SeedError
from app.cli.demo.platform import SUPER_ADMIN, seed_platform
from app.tests.auth_support import (
    ORIGIN,
    PASSWORD,
    build_platform_app,
    client_for,
    log_in,
    make_login,
    use_fast_hashing,
)

DEMO_PASSWORD = "harmattan-kettle-blue-river"  # noqa: S105 (fictional; 27 characters)


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    return build_platform_app(db_session)


@pytest.fixture
def demo(app: FastAPI, db_session: Session) -> Demo:
    make_login(db_session, username=SUPER_ADMIN, full_name="Platform Admin", is_super_admin=True)
    made = Demo(app, password=DEMO_PASSWORD, origin=ORIGIN)
    made.people[SUPER_ADMIN] = made.log_in(SUPER_ADMIN, PASSWORD)
    return made


def schools(db: Session) -> dict[str, Any]:
    rows = db.execute(
        text(
            "select s.code, s.name, sub.billing_enabled,"
            " (select array_agg(f.feature order by f.feature) from school_features f"
            "   where f.school_id = s.id and f.enabled) as features,"
            " (select array_agg(l.level order by l.level) from school_levels l"
            "   where l.school_id = s.id and l.enabled) as levels"
            " from schools s left join school_subscriptions sub on sub.school_id = s.id"
        )
    )
    return {r.code: r for r in rows}


def test_the_three_schools_are_made_as_the_fixtures_say(demo: Demo, db_session: Session) -> None:
    seed_platform(demo)
    made = schools(db_session)
    assert set(made) == {"GMC", "BSA", "RCS"}
    assert made["GMC"].name == "Greenfield Model College"
    assert made["GMC"].billing_enabled is True
    assert len(made["GMC"].features) == 6
    assert made["GMC"].levels == ["junior_secondary", "senior_secondary"]
    assert made["BSA"].billing_enabled is False  # free pilot
    assert "correction_queue" not in made["BSA"].features
    assert made["BSA"].levels == ["nursery", "primary"]
    assert len(made["RCS"].levels) == 4


def test_the_default_prices_become_version_1(demo: Demo, db_session: Session) -> None:
    seed_platform(demo)
    assert db_session.scalar(text("select count(*) from pricing_versions")) == 1
    assert db_session.scalar(text("select max(version) from pricing_versions")) == 1


def test_each_principal_uses_the_demo_password(app: FastAPI, demo: Demo) -> None:
    seed_platform(demo)
    for username in ("ngozi.okeke", "chiamaka.nwafor", "femi.adeyemi"):
        assert log_in(client_for(app), username, DEMO_PASSWORD) == 200, username
        me = demo.as_(username).get("/auth/me")
        assert me["must_change_password"] is False


def test_the_principals_are_the_primary_admins_of_their_own_school(
    demo: Demo, db_session: Session
) -> None:
    seed_platform(demo)
    rows = db_session.execute(
        text(
            "select u.username, s.code, m.role, m.is_primary from school_memberships m"
            " join users u on u.id = m.user_id join schools s on s.id = m.school_id"
        )
    )
    assert {(r.username, r.code, r.role, r.is_primary) for r in rows} == {
        ("ngozi.okeke", "GMC", "school_admin", True),
        ("chiamaka.nwafor", "BSA", "school_admin", True),
        ("femi.adeyemi", "RCS", "school_admin", True),
    }


def test_it_refuses_to_seed_twice(demo: Demo, db_session: Session) -> None:
    seed_platform(demo)
    with pytest.raises(SeedError, match="GMC is already used"):
        seed_platform(demo)
    assert db_session.scalar(text("select count(*) from schools")) == 3


def test_a_failed_request_names_the_route_not_the_body(demo: Demo) -> None:
    owner = demo.as_(SUPER_ADMIN)
    with pytest.raises(SeedError) as failed:
        owner.post(
            "/auth/change-password",
            {"current_password": "wrong-one-here", "new_password": DEMO_PASSWORD},
        )
    assert "/auth/change-password" in str(failed.value)
    assert DEMO_PASSWORD not in str(failed.value)


def test_the_demo_uses_only_fictional_addresses(demo: Demo, db_session: Session) -> None:
    seed_platform(demo)
    emails = set(db_session.scalars(text("select email from users where email is not null")))
    emails |= set(db_session.scalars(text("select email from schools")))
    assert emails
    assert all(e.endswith(".example") for e in emails), emails
