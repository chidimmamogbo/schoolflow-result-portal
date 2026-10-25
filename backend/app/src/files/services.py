"""Uploading and serving school images (D-056, D-057, D-059; BUILD_PROMPT 9.2e).

POST /school/files: a school admin uploads a logo, the head's signature or
the school stamp. The image is checked and cleaned (files/images.py), its
row written (the database fills in the uploader and checks type, size and
folder), then the bytes are stored under a random key in the school's
folder. A logo becomes the school's logo straight away; signatures and
stamps are picked in the report template.

GET /files/{id}: the school's own people get the bytes after the full chain,
with private caching and an ETag. Correction attachments are served by the
correction module, with its own rules about who may see them.
"""

import hashlib
import uuid
from typing import Annotated, Literal

from fastapi import File, Form, Request, Response, UploadFile
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import Principal, found
from app.platform.images import clean_image
from app.platform.storage import FileStorage
from app.src.audit.services import write_audit
from app.src.files.models import IMAGE_LIMIT_BYTES
from app.src.files.schemas import StoredFileOut

SCHOOL_IMAGES = ("logo", "signature", "stamp")


def label(name: str | None) -> str:
    """The original name, kept as a label only (never used for storage)."""
    cleaned = " ".join((name or "").split())[:255]
    return cleaned or "upload"


def upload_school_image(
    purpose: Annotated[Literal["logo", "signature", "stamp"], Form()],
    file: Annotated[UploadFile, File()],
    who: Principal,
    session: Session,
    storage: FileStorage,
) -> StoredFileOut:
    image = clean_image(file.file.read(IMAGE_LIMIT_BYTES + 1))
    school_id = found(who.school_id)
    key = f"schools/{school_id}/{purpose}/{uuid.uuid4().hex}.{image.extension}"
    file_id: uuid.UUID = session.scalar(
        text(
            "insert into files (school_id, purpose, storage_key, content_type, size_bytes,"
            " sha256, original_name) values (:school, :purpose, :key, :type, :size, :sha,"
            " :name) returning id"
        ),
        {
            "school": school_id,
            "purpose": purpose,
            "key": key,
            "type": image.content_type,
            "size": len(image.data),
            "sha": hashlib.sha256(image.data).digest(),
            "name": label(file.filename),
        },
    )
    # Stored after the row: if storing fails, the request fails and the row is rolled back.
    storage.put(key, image.data, image.content_type)
    if purpose == "logo":
        session.execute(
            text("update schools set logo_file_id = :f where id = :s"),
            {"f": file_id, "s": school_id},
        )
    write_audit(
        session,
        school_id,
        who.role.value,
        f"school.{purpose}",
        target=("files", file_id),
        new={"content_type": image.content_type, "size_bytes": len(image.data)},
    )
    return StoredFileOut(
        id=str(file_id),
        purpose=purpose,
        content_type=image.content_type,
        size_bytes=len(image.data),
    )


def download(
    file_id: uuid.UUID,
    request: Request,
    _: Principal,
    session: Session,
    storage: FileStorage,
) -> Response:
    row = found(
        session.execute(
            text(
                "select storage_key, content_type, sha256 from files where id = :id"
                " and purpose in ('logo', 'signature', 'stamp')"
            ),
            {"id": file_id},
        ).first()
    )
    etag = f'"{bytes(row.sha256).hex()}"'
    headers = {"Cache-Control": "private, no-cache", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(storage.get(row.storage_key), media_type=row.content_type, headers=headers)
