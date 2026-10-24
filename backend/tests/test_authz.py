"""The authorization chain (BUILD_PROMPT 9.2c; D-018, D-047, D-049, D-050, D-051).

Behaviour: every route except a short, explicit public list runs the chain
signed in (session, CSRF) > password change done > school active > feature on > permission;
a feature that is off answers 404 with a clear code, a missing permission
403; principal-only permissions are refused to additional admins; the school
and user the database works for come from the session, never the request;
records of another school are not found (404); a report card level that is
off is refused; workflow-state and separation-of-duties guards refuse the
wrong move. Requests run as app_user. All data is fictional.
"""

import re
import uuid
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.authz.deps import (
    PUBLIC_ROUTES,
    Principal,
    ensure_level_enabled,
    found,
    require,
    require_someone_else,
    require_status,
)
from schoolflow_api.core.deps import DbSession
from schoolflow_api.core.errors import ProblemError
from schoolflow_api.main import create_app
from schoolflow_api.schools.models import Feature, Level
from tests.auth_support import ORIGIN, build_auth_app, csrf, logged_in, make_login, use_fast_hashing
from tests.factories import create_class, create_school

Allowed = Annotated[Principal, Depends(require())]
Teacher = Annotated[Principal, Depends(require("scores.enter", feature=Feature.RESULTS))]
Principals = Annotated[Principal, Depends(require("school_admins.create"))]
Platform = Annotated[Principal, Depends(require("schools.manage"))]


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    app = build_auth_app(db_session)

    @app.get("/api/v1/_test/anyone")
    def anyone(principal: Allowed, session: DbSession) -> dict[str, Any]:
        row = session.execute(
            text(
                "select current_setting('app.school_id', true) as school_id,"
                " current_setting('app.user_id', true) as user_id"
            )
        ).one()
        return {"school_id": row.school_id, "user_id": row.user_id, "role": principal.role.value}

    @app.post("/api/v1/_test/scores")
    def scores(principal: Teacher) -> dict[str, str]:
        return {"ok": principal.role.value}

    @app.post("/api/v1/_test/school-admins")
    def school_admins(principal: Principals) -> dict[str, str]:
        return {"ok": principal.role.value}

    @app.get("/api/v1/_test/platform")
    def platform(principal: Platform) -> dict[str, str]:
        return {"ok": principal.role.value}

    @app.get("/api/v1/_test/levels/{level}")
    def level(level: Level, principal: Allowed, session: DbSession) -> dict[str, str]:
        ensure_level_enabled(session, principal, level)
        return {"ok": level.value}

    @app.get("/api/v1/_test/classes/{class_id}")
    def one_class(class_id: uuid.UUID, principal: Allowed, session: DbSession) -> dict[str, str]:
        name = found(
            session.scalar(text("select name from classes where id = :id"), {"id": class_id})
        )
        return {"name": name}

    return app


@pytest.fixture
def gmc(db_session: Session) -> uuid.UUID:
    return create_school(db_session, code="GMC", name="Greenfield Model College")


@pytest.fixture
def bsa(db_session: Session) -> uuid.UUID:
    return create_school(db_session, code="BSA", name="Bright Stars Academy")


def answer(client: TestClient, method: str, url: str) -> tuple[int, str | None]:
    response = client.request(method, url, headers=csrf(client))
    body = response.json()
    return response.status_code, body.get("code") or body.get("ok")


def test_the_chain_sets_the_database_context_from_the_session(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    """D-051: school and user come from the signed-in membership."""
    teacher = make_login(db_session, username="tunde.adebayo", school_id=gmc)
    body = logged_in(app, "tunde.adebayo").get("/api/v1/_test/anyone").json()
    assert body == {"school_id": str(gmc), "user_id": str(teacher), "role": "teacher"}


def test_a_feature_that_is_off_rejects_even_a_valid_login(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    """AT-27.2, D-047: 404 with a clear code."""
    make_login(db_session, username="tunde.adebayo", school_id=gmc)
    client = logged_in(app, "tunde.adebayo")
    assert answer(client, "POST", "/api/v1/_test/scores") == (200, "teacher")
    db_session.execute(text("update school_features set enabled = false where feature = 'results'"))
    assert answer(client, "POST", "/api/v1/_test/scores") == (404, "feature_disabled")


def test_a_missing_permission_is_refused(app: FastAPI, db_session: Session, gmc: uuid.UUID) -> None:
    make_login(db_session, username="ikenna.obi", school_id=gmc, role="parent")
    client = logged_in(app, "ikenna.obi")
    assert answer(client, "POST", "/api/v1/_test/scores") == (403, "permission_denied")
    assert answer(client, "GET", "/api/v1/_test/platform") == (403, "permission_denied")


def test_only_the_principal_manages_school_admins(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    """AC03.1, D-045: an additional admin is refused the principal's permissions."""
    make_login(
        db_session, username="ngozi.okeke", school_id=gmc, role="school_admin", is_primary=True
    )
    make_login(db_session, username="emeka.vp", school_id=gmc, role="school_admin")
    principal = logged_in(app, "ngozi.okeke")
    deputy = logged_in(app, "emeka.vp")
    assert answer(principal, "POST", "/api/v1/_test/school-admins") == (200, "school_admin")
    assert answer(deputy, "POST", "/api/v1/_test/school-admins") == (403, "permission_denied")


def test_the_super_admin_has_platform_permissions_and_no_school(
    app: FastAPI, db_session: Session
) -> None:
    make_login(db_session, username="platform.owner", is_super_admin=True)
    client = logged_in(app, "platform.owner")
    assert answer(client, "GET", "/api/v1/_test/platform") == (200, "super_admin")
    assert answer(client, "POST", "/api/v1/_test/scores") == (403, "permission_denied")
    body = client.get("/api/v1/_test/anyone").json()
    assert body["school_id"] == ""


def test_a_temporary_password_blocks_every_protected_route(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    """D-040: enforced on the server, not by hiding pages."""
    make_login(db_session, username="tunde.adebayo", school_id=gmc, temporary=True)
    client = logged_in(app, "tunde.adebayo")
    for method, url in (("GET", "/api/v1/_test/anyone"), ("POST", "/api/v1/_test/scores")):
        assert answer(client, method, url) == (403, "password_change_required")


def test_a_suspended_school_stops_existing_sessions(
    app: FastAPI, db_session: Session, gmc: uuid.UUID
) -> None:
    make_login(db_session, username="tunde.adebayo", school_id=gmc)
    client = logged_in(app, "tunde.adebayo")
    db_session.execute(text("update schools set status = 'suspended' where id = :id"), {"id": gmc})
    assert answer(client, "GET", "/api/v1/_test/anyone") == (403, "school_paused")


def test_another_schools_record_is_not_found(
    app: FastAPI, db_session: Session, gmc: uuid.UUID, bsa: uuid.UUID
) -> None:
    """D-047, D-051: an ID from another school answers 404, like one that never existed."""
    make_login(db_session, username="tunde.adebayo", school_id=gmc)
    own = create_class(db_session, gmc, "junior_secondary", "JSS 1")
    theirs = create_class(db_session, bsa, "junior_secondary", "JSS 1")
    client = logged_in(app, "tunde.adebayo")
    assert client.get(f"/api/v1/_test/classes/{own}").json() == {"name": "JSS 1"}
    for missing in (theirs, uuid.uuid4()):
        response = client.get(f"/api/v1/_test/classes/{missing}")
        assert response.status_code == 404
        assert response.json()["title"] == "Not Found"


def test_a_level_that_is_off_is_refused(app: FastAPI, db_session: Session, gmc: uuid.UUID) -> None:
    """D-050, AC04.2: GMC is secondary only, so Nursery and Primary are off."""
    make_login(db_session, username="tunde.adebayo", school_id=gmc)
    client = logged_in(app, "tunde.adebayo")
    assert answer(client, "GET", "/api/v1/_test/levels/junior_secondary") == (
        200,
        "junior_secondary",
    )
    assert answer(client, "GET", "/api/v1/_test/levels/nursery") == (404, "level_disabled")


def test_workflow_and_separation_of_duties_guards() -> None:
    """D-047 steps 8 and 9 (the database checks them too, migration 11)."""
    require_status("submitted", "submitted", "resubmitted")
    with pytest.raises(ProblemError) as error:
        require_status("draft", "submitted", "resubmitted")
    assert (error.value.status, error.value.code) == (409, "wrong_status")

    me, someone = uuid.uuid4(), uuid.uuid4()
    require_someone_else(me, someone)
    require_someone_else(me, None)
    with pytest.raises(ProblemError) as error:
        require_someone_else(me, me)
    assert (error.value.status, error.value.code) == (403, "separation_of_duties")


def test_found_returns_the_value_or_answers_404() -> None:
    assert found("JSS 1") == "JSS 1"
    assert found(0) == 0
    with pytest.raises(ProblemError) as error:
        found(None)
    assert error.value.status == 404


def operations(app: FastAPI) -> set[tuple[str, str]]:
    """Every (method, path) the app serves, from its own OpenAPI description."""
    schema = app.openapi()
    return {
        (method.upper(), path)
        for path, item in schema["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    }


def test_every_route_except_the_public_list_needs_a_session(db_session: Session) -> None:
    """D-018: a new route that skips the chain fails this test.

    Each route is called with no session at all; every one outside the public
    list must answer 401 before doing anything else.
    """
    app = build_auth_app(db_session)
    served = operations(create_app(app_env="local"))
    assert served >= PUBLIC_ROUTES
    client = TestClient(app, base_url="https://testserver")
    for method, path in sorted(served - PUBLIC_ROUTES):
        url = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)
        response = client.request(method, url, headers={"Origin": ORIGIN})
        assert (response.status_code, response.json().get("code")) == (401, "not_signed_in"), (
            method,
            path,
        )
    assert {
        ("GET", "/api/v1/health"),
        ("GET", "/api/v1/health/ready"),
        ("POST", "/api/v1/auth/login"),
        ("GET", "/api/v1/auth/schools/{code}/public"),
        ("GET", "/api/v1/auth/schools/{code}/logo"),
        ("POST", "/api/v1/auth/activate"),
        ("POST", "/api/v1/auth/password/forgot"),
        ("POST", "/api/v1/auth/password/reset"),
        ("GET", "/api/v1/verify/{code}"),  # public report verification (F13, D-071)
    } == PUBLIC_ROUTES
