"""A school's own login page: its layout, picture, message and photo (CHANGE C, D-182).

SPEC F02 rules 12 and 14. School admins change it under School settings >
Login page; the super admin changes the same layout, picture and message on a
school's details (and sets them on Create school). Only the school uploads its
own photo, after the warning that it is public (F02 rule 12): the school takes
responsibility for it.

The photo is checked and cleaned like a logo (no metadata, at most 1200 pixels
a side), then saved as a JPEG so it stays well under its 2 MB limit. It is
served publicly by /auth/schools/{code}/login-photo.
"""

import hashlib
import io
import uuid
from typing import Any

from fastapi import UploadFile
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import Principal, found
from app.core.errors import ProblemError
from app.platform.images import clean_image, too_large
from app.platform.storage import FileStorage
from app.src.audit.services import write_audit
from app.src.files.models import ATTACHMENT_LIMIT_BYTES, LOGIN_PHOTO_LIMIT_BYTES
from app.src.login_page.schemas import LoginPage, LoginPageChange

# What a school may upload (4 MB) before cleaning; it is stored at 2 MB or less.
PHOTO_UPLOAD_LIMIT = ATTACHMENT_LIMIT_BYTES

PHOTO_MISSING = ProblemError(
    409,
    "Upload a photo first.",
    "Choose Pattern or People, or upload your own photo.",
    code="photo_missing",
)

FIELDS = ("login_layout", "login_picture", "login_message")


def page_of(session: Session, school_id: Any) -> LoginPage:
    row = found(
        session.execute(
            text(
                "select code, login_layout, login_picture, login_message, login_photo_file_id"
                " from schools where id = :id"
            ),
            {"id": school_id},
        ).first()
    )
    has_photo = row.login_photo_file_id is not None
    return LoginPage(
        layout=row.login_layout,
        picture=row.login_picture,
        message=row.login_message,
        photo_url=f"/api/v1/auth/schools/{row.code}/login-photo" if has_photo else None,
        link=f"/login/{row.code}",
    )


def change(session: Session, school_id: Any, body: LoginPageChange) -> dict[str, Any] | None:
    """Save the choices; the changed fields (old, new) for the audit, or None."""
    current = session.execute(
        text(
            "select login_layout, login_picture, login_message, login_photo_file_id"
            " from schools where id = :id"
        ),
        {"id": school_id},
    ).one()
    if body.picture == "photo" and current.login_photo_file_id is None:
        raise PHOTO_MISSING
    wanted = {
        "login_layout": body.layout,
        "login_picture": body.picture,
        "login_message": body.message,
    }
    old = {field: getattr(current, field) for field in FIELDS}
    changed = {field: value for field, value in wanted.items() if old[field] != value}
    if not changed:
        return None
    assignments = ", ".join(f"{field} = :{field}" for field in changed)
    session.execute(
        text(f"update schools set {assignments} where id = :id"),  # noqa: S608 (fixed names)
        {**changed, "id": school_id},
    )
    return {"old": {field: old[field] for field in changed}, "new": changed}


def as_jpeg(data: bytes) -> bytes:
    """The cleaned picture as a JPEG; transparent parts become white."""
    with Image.open(io.BytesIO(data)) as source:
        picture = source.convert("RGBA")
    flat = Image.new("RGB", picture.size, (255, 255, 255))
    flat.paste(picture, mask=picture.getchannel("A"))
    out = io.BytesIO()
    flat.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()


# --- school admins ----------------------------------------------------------------------


def get_page(who: Principal, session: Session) -> LoginPage:
    return page_of(session, found(who.school_id))


def edit_page(body: LoginPageChange, who: Principal, session: Session) -> LoginPage:
    school_id = found(who.school_id)
    changed = change(session, school_id, body)
    if changed is not None:
        write_audit(
            session,
            school_id,
            who.role.value,
            "school.login_page",
            target=("schools", school_id),
            **changed,
        )
    return page_of(session, school_id)


def upload_photo(
    file: UploadFile, who: Principal, session: Session, storage: FileStorage
) -> LoginPage:
    """The school's own photo becomes its login picture straight away."""
    image = clean_image(file.file.read(PHOTO_UPLOAD_LIMIT + 1), PHOTO_UPLOAD_LIMIT)
    data = as_jpeg(image.data)
    if len(data) > LOGIN_PHOTO_LIMIT_BYTES:
        raise too_large(LOGIN_PHOTO_LIMIT_BYTES)
    school_id = found(who.school_id)
    key = f"schools/{school_id}/login_photo/{uuid.uuid4().hex}.jpg"
    file_id: uuid.UUID = session.scalar(
        text(
            "insert into files (school_id, purpose, storage_key, content_type, size_bytes,"
            " sha256, original_name) values (:school, 'login_photo', :key, 'image/jpeg',"
            " :size, :sha, 'login photo') returning id"
        ),
        {
            "school": school_id,
            "key": key,
            "size": len(data),
            "sha": hashlib.sha256(data).digest(),
        },
    )
    # Stored after the row: if storing fails, the request fails and the row is rolled back.
    storage.put(key, data, "image/jpeg")
    session.execute(
        text("update schools set login_photo_file_id = :f, login_picture = 'photo' where id = :s"),
        {"f": file_id, "s": school_id},
    )
    write_audit(
        session,
        school_id,
        who.role.value,
        "school.login_photo",
        target=("files", file_id),
        new={"content_type": "image/jpeg", "size_bytes": len(data)},
    )
    return page_of(session, school_id)


# --- the super admin --------------------------------------------------------------------


def platform_get_page(school_id: uuid.UUID, db: Session) -> LoginPage:
    return page_of(db, school_id)


def platform_edit_page(school_id: uuid.UUID, body: LoginPageChange, db: Session) -> LoginPage:
    found(db.scalar(text("select id from schools where id = :id"), {"id": school_id}))
    changed = change(db, school_id, body)
    if changed is not None:
        # Local import: platform_admin.services imports this module for Create school.
        from app.src.platform_admin.services import audit

        audit(db, school_id, "schools.login_page", target=("schools", school_id), **changed)
    return page_of(db, school_id)
