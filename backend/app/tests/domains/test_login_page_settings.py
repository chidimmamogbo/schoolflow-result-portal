"""School settings > Login page, and the super admin's same choices (CHANGE C, D-182).

SPEC F02 rules 12 and 14. Behaviour: a school admin reads and changes the
layout, picture and message of the school's own login page, and uploads its
own photo (cleaned, saved as a JPEG, served publicly on the login page);
"Your own photo" needs a photo; teachers and parents cannot change it; the
super admin changes the same choices for any school (and sets them on Create
school), but never uploads the school's photo. Each change is audited. All
data is fictional.
"""

import io
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform.storage import LocalFileStorage, get_file_storage
from app.tests.auth_support import (
    build_platform_app,
    client_for,
    csrf,
    logged_in,
    make_login,
    use_fast_hashing,
)
from app.tests.factories import create_school


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def storage(tmp_path: Path) -> LocalFileStorage:
    return LocalFileStorage(tmp_path)


@pytest.fixture
def app(db_session: Session, storage: LocalFileStorage) -> FastAPI:
    app = build_platform_app(db_session)
    app.dependency_overrides[get_file_storage] = lambda: storage
    return app


@pytest.fixture
def gmc(db_session: Session) -> uuid.UUID:
    school = create_school(db_session, code="GMC", name="Greenfield Model College")
    make_login(
        db_session, username="ngozi.okeke", school_id=school, role="school_admin", is_primary=True
    )
    make_login(db_session, username="tunde.adebayo", school_id=school)
    make_login(db_session, username="ikenna.obi", school_id=school, role="parent")
    return school


@pytest.fixture
def principal(app: FastAPI, gmc: uuid.UUID) -> TestClient:
    return logged_in(app, "ngozi.okeke")


@pytest.fixture
def owner(app: FastAPI, db_session: Session) -> TestClient:
    make_login(db_session, username="platform.owner", is_super_admin=True)
    return logged_in(app, "platform.owner")


def photo_png(size: tuple[int, int] = (1600, 900)) -> bytes:
    out = io.BytesIO()
    Image.new("RGBA", size, (31, 111, 67, 255)).save(out, format="PNG")
    return out.getvalue()


def put_page(client: TestClient, url: str, body: dict[str, Any]) -> Any:
    return client.put(f"/api/v1{url}", json=body, headers=csrf(client))


def upload(client: TestClient, data: bytes) -> Any:
    return client.post(
        "/api/v1/school/login-page/photo",
        files={"file": ("our-school.png", data, "image/png")},
        headers=csrf(client),
    )


def test_a_school_admin_changes_the_login_page(
    principal: TestClient, db_session: Session, gmc: uuid.UUID
) -> None:
    """F02 rule 12: layout, picture and message; an empty message shows the default."""
    page = principal.get("/api/v1/school/login-page").json()
    assert page == {
        "layout": "half",
        "picture": "pattern",
        "message": None,
        "photo_url": None,
        "link": "/login/GMC",
    }
    response = put_page(
        principal,
        "/school/login-page",
        {
            "layout": "behind",
            "picture": "people",
            "message": "  Knowledge, Discipline and Service ",
        },
    )
    assert response.status_code == 200, response.json()
    assert (response.json()["layout"], response.json()["message"]) == (
        "behind",
        "Knowledge, Discipline and Service",
    )
    page = put_page(
        principal, "/school/login-page", {"layout": "half", "picture": "people", "message": " "}
    ).json()
    assert page["message"] is None
    actions = db_session.scalars(
        text("select action from audit_events where school_id = :s"), {"s": gmc}
    ).all()
    assert actions.count("school.login_page") == 2


@pytest.mark.parametrize(
    "body",
    [
        {"layout": "sideways", "picture": "pattern"},
        {"layout": "half", "picture": "drawing"},
        {"layout": "half", "picture": "pattern", "message": "x" * 81},
        {"layout": "half", "picture": "pattern", "message": "Line one\nLine two"},
        {"layout": "half", "picture": "pattern", "school_id": str(uuid.uuid4())},
    ],
)
def test_bad_choices_are_refused(principal: TestClient, body: dict[str, Any]) -> None:
    assert put_page(principal, "/school/login-page", body).status_code == 422


def test_your_own_photo_needs_a_photo(principal: TestClient) -> None:
    response = put_page(principal, "/school/login-page", {"layout": "half", "picture": "photo"})
    assert (response.status_code, response.json()["code"]) == (409, "photo_missing")


def test_the_uploaded_photo_is_cleaned_and_public(
    app: FastAPI, principal: TestClient, db_session: Session, gmc: uuid.UUID
) -> None:
    """F02 rule 12: a JPEG of at most 1200 pixels a side, shown on the login page."""
    response = upload(principal, photo_png())
    assert response.status_code == 200, response.json()
    page = response.json()
    assert (page["picture"], page["photo_url"]) == (
        "photo",
        "/api/v1/auth/schools/GMC/login-photo",
    )
    served = client_for(app).get(page["photo_url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/jpeg"
    with Image.open(io.BytesIO(served.content)) as picture:
        assert max(picture.size) <= 1200
    public = client_for(app).get("/api/v1/auth/schools/GMC/public").json()
    assert (public["picture"], public["photo_url"]) == ("photo", page["photo_url"])
    assert (
        "school.login_photo"
        in db_session.scalars(
            text("select action from audit_events where school_id = :s"), {"s": gmc}
        ).all()
    )


def test_a_photo_must_be_an_image_of_at_most_4_mb(principal: TestClient) -> None:
    assert upload(principal, b"<svg xmlns='http://www.w3.org/2000/svg'/>").status_code == 415
    assert upload(principal, b"\x89PNG" + b"0" * (4 * 1024 * 1024 + 1)).status_code == 413


@pytest.mark.parametrize("username", ["tunde.adebayo", "ikenna.obi"])
def test_teachers_and_parents_cannot_change_it(app: FastAPI, gmc: uuid.UUID, username: str) -> None:
    client = logged_in(app, username)
    assert client.get("/api/v1/school/login-page").status_code == 403
    response = put_page(client, "/school/login-page", {"layout": "behind", "picture": "people"})
    assert response.status_code == 403
    assert upload(client, photo_png()).status_code == 403


def test_the_super_admin_sets_the_same_choices(
    owner: TestClient, db_session: Session, gmc: uuid.UUID
) -> None:
    """F02 rule 14: on a school's details; never the school's photo."""
    url = f"/platform/schools/{gmc}/login-page"
    page = put_page(owner, url, {"layout": "behind", "picture": "people", "message": "Welcome!"})
    assert page.status_code == 200, page.json()
    assert owner.get(f"/api/v1{url}").json()["layout"] == "behind"
    assert (
        "schools.login_page"
        in db_session.scalars(
            text("select action from audit_events where school_id = :s"), {"s": gmc}
        ).all()
    )
    photo = put_page(owner, url, {"layout": "half", "picture": "photo"})
    assert (photo.status_code, photo.json()["code"]) == (409, "photo_missing")
    missing = put_page(
        owner,
        f"/platform/schools/{uuid.uuid4()}/login-page",
        {"layout": "half", "picture": "people"},
    )
    assert missing.status_code == 404


def test_a_school_admin_cannot_use_the_platform_route(
    principal: TestClient, gmc: uuid.UUID
) -> None:
    response = put_page(
        principal, f"/platform/schools/{gmc}/login-page", {"layout": "half", "picture": "people"}
    )
    assert response.status_code == 403
