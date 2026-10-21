"""Staff, their assignments, and uploads (BUILD_PROMPT 9.2e part 2a).

SPEC F03, F06; D-055 to D-059, D-144.

Behaviour: school admins create teachers and reviewers (activation email or
a slip shown once) and edit their names and emails; they give teachers
subjects in arms the arm takes (one teacher per subject per arm), make one
form teacher per arm (optionally teaching all subjects), add at most two
assistants per arm, and scope reviewers to a department or to subjects and
classes; school admins and reviewers may teach too (D-144), parents never;
ids from another school and levels that are off are refused. Logos,
signatures and stamps are checked by their content (PNG, JPEG or WebP,
never SVG), re-saved without metadata, kept under the school's own folder
and served only to the school's own people. All data is fictional.
"""

import hashlib
import io
import uuid
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.files.storage import LocalFileStorage, get_file_storage
from tests.auth_support import (
    build_auth_app,
    client_for,
    csrf,
    log_in,
    logged_in,
    make_login,
    use_fast_hashing,
)
from tests.db_support import acting_as
from tests.factories import (
    add_arm_subject,
    create_arm,
    create_class,
    create_department,
    create_school,
    create_subject,
)


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fast_hashing(monkeypatch)


@pytest.fixture
def storage(tmp_path: Path) -> LocalFileStorage:
    return LocalFileStorage(tmp_path)


@pytest.fixture
def app(db_session: Session, storage: LocalFileStorage) -> FastAPI:
    app = build_auth_app(db_session)
    app.dependency_overrides[get_file_storage] = lambda: storage
    return app


@pytest.fixture
def gmc(db_session: Session) -> dict[str, uuid.UUID]:
    school = create_school(db_session, code="GMC", name="Greenfield Model College")
    jss1 = create_class(db_session, school, "junior_secondary", "JSS 1")
    arm_a = create_arm(db_session, school, jss1, "A")
    maths = create_subject(db_session, school, "Mathematics")
    english = create_subject(db_session, school, "English Language")
    igbo = create_subject(db_session, school, "Igbo Language")
    for subject in (maths, english):
        add_arm_subject(db_session, school, arm_a, subject)
    return {
        "school": school,
        "jss1": jss1,
        "arm_a": arm_a,
        "maths": maths,
        "english": english,
        "igbo": igbo,
        "sciences": create_department(db_session, school, "Sciences"),
        "ngozi": make_login(
            db_session,
            username="ngozi.okeke",
            school_id=school,
            role="school_admin",
            is_primary=True,
        ),
        "emeka": make_login(db_session, username="emeka.vp", school_id=school, role="school_admin"),
        "tunde": make_login(
            db_session, username="tunde.adebayo", email="tunde@gmc.example", school_id=school
        ),
        "grace": make_login(db_session, username="grace.etim", school_id=school),
        "bola": make_login(db_session, username="bola.ige", school_id=school),
        "hod": make_login(db_session, username="emeka.nwosu", school_id=school, role="reviewer"),
        "parent": make_login(db_session, username="ikenna.obi", school_id=school, role="parent"),
    }


@pytest.fixture
def principal(app: FastAPI, gmc: dict[str, uuid.UUID]) -> TestClient:
    return logged_in(app, "ngozi.okeke")


@pytest.fixture
def deputy(app: FastAPI, gmc: dict[str, uuid.UUID]) -> TestClient:
    return logged_in(app, "emeka.vp")


@pytest.fixture
def teacher(app: FastAPI, gmc: dict[str, uuid.UUID]) -> TestClient:
    return logged_in(app, "tunde.adebayo")


def send(client: TestClient, method: str, url: str, body: Any = None) -> tuple[int, Any]:
    response = client.request(method, f"/api/v1{url}", json=body, headers=csrf(client))
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def code_of(result: tuple[int, Any]) -> tuple[int, str | None]:
    status, body = result
    return status, cast(dict[str, Any], body or {}).get("code")


# --- teachers and reviewers -------------------------------------------------------------


def test_school_admins_create_teachers_and_reviewers(
    app: FastAPI, deputy: TestClient, teacher: TestClient, db_session: Session
) -> None:
    """F03 rules 3 and 4: an activation email or a slip shown once; never a parent here."""
    status, created = send(
        deputy,
        "POST",
        "/school/staff",
        {
            "full_name": "Amina Bello",
            "username": "amina.bello",
            "email": "amina@gmc.example",
            "role": "teacher",
            "login_method": "activation",
        },
    )
    assert status == 201, created
    assert created["temporary_password"] is None
    email = db_session.execute(
        text("select template, template_data from email_outbox where to_address = :a"),
        {"a": "amina@gmc.example"},
    ).one()
    assert email.template == "activation"
    assert email.template_data["school_code"] == "GMC"

    status, created = send(
        deputy,
        "POST",
        "/school/staff",
        {
            "full_name": "Femi Ade",
            "username": "femi.ade",
            "role": "reviewer",
            "login_method": "temporary_password",
        },
    )
    assert status == 201
    assert log_in(client_for(app), "femi.ade", created["temporary_password"]) == 200

    assert code_of(
        send(
            deputy,
            "POST",
            "/school/staff",
            {
                "full_name": "X",
                "username": "tunde.adebayo",
                "role": "teacher",
                "login_method": "temporary_password",
            },
        )
    ) == (409, "username_taken")
    for role in ("parent", "student", "school_admin", "super_admin"):
        assert (
            send(
                deputy,
                "POST",
                "/school/staff",
                {
                    "full_name": "X",
                    "username": "x.y",
                    "role": role,
                    "login_method": "temporary_password",
                },
            )[0]
            == 422
        ), role
    assert code_of(
        send(
            teacher,
            "POST",
            "/school/staff",
            {
                "full_name": "X",
                "username": "x.z",
                "role": "teacher",
                "login_method": "temporary_password",
            },
        )
    ) == (403, "permission_denied")

    status, staff = send(deputy, "GET", "/school/staff?role=teacher")
    assert status == 200
    assert {s["username"] for s in staff} == {
        "tunde.adebayo",
        "grace.etim",
        "bola.ige",
        "amina.bello",
    }
    assert {"users.create"} <= set(db_session.scalars(text("select action from audit_events")))


def test_editing_a_staff_members_name_and_email(
    deputy: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    url = f"/school/staff/{gmc['tunde']}"
    status, body = send(
        deputy, "PATCH", url, {"full_name": "Tunde A. Adebayo", "email": "Tunde.New@gmc.example"}
    )
    assert status == 200, body
    assert (body["full_name"], body["email"]) == ("Tunde A. Adebayo", "tunde.new@gmc.example")
    assert db_session.scalar(
        text("select email_verified_at is null from users where id = :id"), {"id": gmc["tunde"]}
    )
    grace_email = {"email": "tunde.new@gmc.example"}
    assert code_of(send(deputy, "PATCH", f"/school/staff/{gmc['grace']}", grace_email)) == (
        409,
        "email_taken",
    )
    # Admins are managed on the admins page; parents and other schools are not staff here.
    other = make_login(
        db_session,
        username="bsa.teacher",
        school_id=create_school(db_session, code="BSA", name="Bright Stars"),
    )
    for person in (gmc["ngozi"], gmc["emeka"], gmc["parent"], other, uuid.uuid4()):
        assert send(deputy, "PATCH", f"/school/staff/{person}", {"full_name": "Y"})[0] == 404


# --- assignments -----------------------------------------------------------------------


def test_subject_assignments(
    principal: TestClient, teacher: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    """F06 rule 1, D-144: one teacher per subject in an arm, only subjects the arm takes."""
    url = "/school/assignments"
    maths = {
        "teacher_id": str(gmc["tunde"]),
        "arm_id": str(gmc["arm_a"]),
        "subject_id": str(gmc["maths"]),
    }
    status, row = send(principal, "POST", url, maths)
    assert status == 201, row
    assert (row["teacher_name"], row["subject_id"]) == ("Tunde Adebayo", str(gmc["maths"]))
    assert send(principal, "POST", url, {**maths, "teacher_id": str(gmc["grace"])})[0] == 409
    igbo = {**maths, "subject_id": str(gmc["igbo"])}
    assert send(principal, "POST", url, igbo)[0] == 409  # JSS 1A does not take Igbo
    english_by_admin = {**maths, "teacher_id": str(gmc["emeka"]), "subject_id": str(gmc["english"])}
    assert send(principal, "POST", url, english_by_admin)[0] == 201  # D-144
    by_parent = {**maths, "teacher_id": str(gmc["parent"]), "subject_id": str(gmc["english"])}
    assert code_of(send(principal, "POST", url, by_parent)) == (
        409,
        "teacher_assignments_teacher_id_is_staff",
    )
    for bad in (
        {**maths, "is_form_teacher": True},
        {"teacher_id": str(gmc["tunde"]), "arm_id": str(gmc["arm_a"])},
        {**maths, "teaches_all_subjects": True},
    ):
        assert send(principal, "POST", url, bad)[0] == 422, bad
    status, rows = send(teacher, "GET", f"{url}?arm_id={gmc['arm_a']}")
    assert status == 200  # staff can see who teaches what in the school
    assert len(rows) == 2
    assert code_of(send(teacher, "POST", url, maths)) == (403, "permission_denied")
    assert send(principal, "DELETE", f"{url}/{row['id']}")[0] == 204
    assert db_session.scalar(text("select count(*) from teacher_assignments")) == 1


def test_form_teacher_and_teaches_all_subjects(
    principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    """F06 rule 2: one form teacher per arm; "Teaches all subjects" covers the arm's subjects."""
    url = "/school/assignments"
    form = {
        "teacher_id": str(gmc["tunde"]),
        "arm_id": str(gmc["arm_a"]),
        "is_form_teacher": True,
        "teaches_all_subjects": True,
    }
    assert send(principal, "POST", url, form)[0] == 201
    assert send(principal, "POST", url, {**form, "teacher_id": str(gmc["grace"])})[0] == 409
    taught = set(
        db_session.scalars(
            text("select subject_id from teacher_subjects where teacher_id = :t"),
            {"t": gmc["tunde"]},
        )
    )
    assert taught == {gmc["maths"], gmc["english"]}


def test_assignments_refuse_other_schools_and_levels_that_are_off(
    principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    bsa = create_school(
        db_session, code="BSA", name="Bright Stars Academy", school_type="nursery_primary"
    )
    pry1 = create_class(db_session, bsa, "primary", "Primary 1")
    bsa_arm = create_arm(db_session, bsa, pry1, "A")
    bsa_teacher = make_login(db_session, username="bsa.teacher", school_id=bsa)
    url = "/school/assignments"
    form = {"teacher_id": str(gmc["tunde"]), "arm_id": str(gmc["arm_a"]), "is_form_teacher": True}
    assert send(principal, "POST", url, {**form, "arm_id": str(bsa_arm)})[0] == 404
    assert send(principal, "POST", url, {**form, "teacher_id": str(bsa_teacher)})[0] == 404
    db_session.execute(
        text("update school_levels set enabled = (level = 'primary') where school_id = :s"),
        {"s": gmc["school"]},
    )
    assert code_of(send(principal, "POST", url, form)) == (404, "level_disabled")


def test_class_teacher_assistants(
    principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    """F06 rule 3: at most two assistants per arm; staff only."""
    url = f"/school/arms/{gmc['arm_a']}/assistants"
    assert send(principal, "POST", url, {"user_id": str(gmc["grace"])})[0] == 201
    assert send(principal, "POST", url, {"user_id": str(gmc["bola"])})[0] == 201
    assert code_of(send(principal, "POST", url, {"user_id": str(gmc["tunde"])})) == (
        409,
        "class_assistants_at_most_two",
    )
    _, assistants = send(principal, "GET", url)
    assert {a["username"] for a in assistants} == {"grace.etim", "bola.ige"}
    assert send(principal, "DELETE", f"{url}/{gmc['bola']}")[0] == 204
    assert code_of(send(principal, "POST", url, {"user_id": str(gmc["parent"])})) == (
        409,
        "class_assistants_assistant_id_is_staff",
    )
    assert send(principal, "DELETE", f"{url}/{gmc['bola']}")[0] == 404


def test_reviewer_scopes(
    principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    """F06 rule 1: a whole department, or subjects and/or classes."""
    url = f"/school/reviewers/{gmc['hod']}/scopes"
    status, scope = send(principal, "POST", url, {"department_id": str(gmc["sciences"])})
    assert status == 201, scope
    assert send(principal, "POST", url, {"department_id": str(gmc["sciences"])})[0] == 409
    assert (
        send(
            principal,
            "POST",
            url,
            {"subject_id": str(gmc["english"]), "class_id": str(gmc["jss1"])},
        )[0]
        == 201
    )
    for bad in ({}, {"department_id": str(gmc["sciences"]), "subject_id": str(gmc["maths"])}):
        assert send(principal, "POST", url, bad)[0] == 422
    status, scopes = send(principal, "GET", url)
    assert len(scopes) == 2
    assert code_of(
        send(
            principal,
            "POST",
            f"/school/reviewers/{gmc['tunde']}/scopes",
            {"department_id": str(gmc["sciences"])},
        )
    ) == (409, "reviewer_scopes_reviewer_id_is_reviewer")
    other = create_department(
        db_session, create_school(db_session, code="BSA", name="Bright Stars"), "Arts"
    )
    assert send(principal, "POST", url, {"department_id": str(other)})[0] == 404
    assert send(principal, "DELETE", f"/school/reviewer-scopes/{scope['id']}")[0] == 204


# --- uploads (D-057) ------------------------------------------------------------------


def image_bytes(fmt: str, size: tuple[int, int] = (64, 64), **save: Any) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (30, 107, 69)).save(buffer, fmt, **save)
    return buffer.getvalue()


def upload(
    client: TestClient,
    purpose: str,
    data: bytes,
    name: str = "logo.png",
    content_type: str = "image/png",
) -> tuple[int, Any]:
    response = client.post(
        "/api/v1/school/files",
        data={"purpose": purpose},
        files={"file": (name, data, content_type)},
        headers=csrf(client),
    )
    return response.status_code, response.json()


def test_a_logo_is_checked_cleaned_stored_and_set(
    principal: TestClient,
    storage: LocalFileStorage,
    db_session: Session,
    gmc: dict[str, uuid.UUID],
) -> None:
    """D-057: content check, metadata stripped, resized, school folder, logo set."""
    exif = Image.Exif()
    exif[0x8825] = {2: (6.0, 27.0, 0.0)}  # GPS information
    exif[0x010F] = "Fictional Camera Ltd"
    photo = image_bytes("JPEG", (2400, 1200), exif=exif.tobytes())
    status, body = upload(principal, "logo", photo, "school photo.jpg", "image/jpeg")
    assert status == 201, body
    assert (body["purpose"], body["content_type"]) == ("logo", "image/jpeg")
    row = db_session.execute(
        text("select storage_key, sha256, size_bytes, original_name from files where id = :id"),
        {"id": body["id"]},
    ).one()
    assert row.storage_key.startswith(f"schools/{gmc['school']}/logo/")
    assert row.original_name == "school photo.jpg"
    stored = storage.get(row.storage_key)
    assert hashlib.sha256(stored).digest() == row.sha256
    assert len(stored) == row.size_bytes
    cleaned = Image.open(io.BytesIO(stored))
    assert max(cleaned.size) == 1200
    assert len(cleaned.getexif()) == 0
    assert db_session.scalar(
        text("select logo_file_id from schools where id = :id"), {"id": gmc["school"]}
    ) == uuid.UUID(body["id"])
    assert "school.logo" in set(db_session.scalars(text("select action from audit_events")))


def test_signature_and_stamp_are_stored_but_not_set_as_the_logo(
    principal: TestClient, db_session: Session, gmc: dict[str, uuid.UUID]
) -> None:
    for purpose, fmt, kind in (("signature", "PNG", "image/png"), ("stamp", "WEBP", "image/webp")):
        status, body = upload(principal, purpose, image_bytes(fmt), f"{purpose}.img", kind)
        assert (status, body["content_type"]) == (201, kind)
    assert (
        db_session.scalar(
            text("select logo_file_id from schools where id = :id"), {"id": gmc["school"]}
        )
        is None
    )


def test_disguised_oversized_and_unsafe_files_are_refused(
    principal: TestClient, teacher: TestClient, db_session: Session
) -> None:
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    pdf = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"
    big = b"\x89PNG\r\n\x1a\n" + bytes(1024 * 1024 + 1)
    cases = [
        (svg, "logo.svg", "image/svg+xml", (415, "unsupported_file")),
        (svg, "logo.png", "image/png", (415, "unsupported_file")),
        (b"just text, not an image", "logo.png", "image/png", (415, "unsupported_file")),
        (pdf, "logo.pdf", "application/pdf", (415, "unsupported_file")),
        (b"\x89PNG\r\n\x1a\n" + b"broken", "logo.png", "image/png", (415, "unsupported_file")),
        (big, "logo.png", "image/png", (413, "file_too_large")),
    ]
    for data, name, kind, expected in cases:
        status, body = upload(principal, "logo", data, name, kind)
        assert (status, body.get("code")) == expected, name
    assert upload(principal, "correction_attachment", image_bytes("PNG"))[0] == 422
    assert code_of(upload(teacher, "logo", image_bytes("PNG"))) == (403, "permission_denied")
    assert db_session.scalar(text("select count(*) from files")) == 0


def test_files_are_served_only_to_their_own_school(
    app: FastAPI, principal: TestClient, teacher: TestClient, db_session: Session
) -> None:
    """D-056: the full chain, private caching, an ETag."""
    _, body = upload(principal, "stamp", image_bytes("PNG"), "stamp.png")
    url = f"/api/v1/files/{body['id']}"
    response = teacher.get(url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, no-cache"
    etag = response.headers["etag"]
    assert teacher.get(url, headers={"If-None-Match": etag}).status_code == 304
    assert client_for(app).get(url).status_code == 401
    assert teacher.get(f"/api/v1/files/{uuid.uuid4()}").status_code == 404

    bsa = create_school(db_session, code="BSA", name="Bright Stars Academy")
    make_login(db_session, username="bsa.teacher", school_id=bsa)
    assert logged_in(app, "bsa.teacher").get(url).status_code == 404


def test_correction_attachments_are_not_served_here(
    principal: TestClient,
    storage: LocalFileStorage,
    db_session: Session,
    gmc: dict[str, uuid.UUID],
) -> None:
    """D-056: attachments follow the correction module's own rules, not this route's."""
    key = f"schools/{gmc['school']}/correction_attachment/evidence.png"
    data = image_bytes("PNG")
    storage.put(key, data, "image/png")
    with acting_as(db_session, "app_user", school_id=gmc["school"], user_id=gmc["ngozi"]):
        file_id = db_session.scalar(
            text(
                "insert into files (school_id, purpose, storage_key, content_type, size_bytes,"
                " sha256, original_name) values (:s, 'correction_attachment', :k, 'image/png',"
                " :n, :h, 'evidence.png') returning id"
            ),
            {"s": gmc["school"], "k": key, "n": len(data), "h": hashlib.sha256(data).digest()},
        )
    assert principal.get(f"/api/v1/files/{file_id}").status_code == 404


def test_local_storage_never_leaves_its_folder(storage: LocalFileStorage) -> None:
    for key in ("../outside.png", "/etc/passwd", "schools/../../outside.png"):
        with pytest.raises(ValueError, match="inside the storage folder"):
            storage.put(key, b"x", "image/png")
    storage.put("schools/a/logo/x.png", b"x", "image/png")
    assert storage.get("schools/a/logo/x.png") == b"x"
