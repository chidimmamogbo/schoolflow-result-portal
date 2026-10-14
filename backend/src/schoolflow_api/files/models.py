"""The files table (D-057; BUILD_PROMPT 9.1 item 8; D-152).

One row per uploaded file: the school it belongs to, what it is for (a logo,
a signature, a stamp or a correction attachment), its type and size, its
SHA-256, where the bytes live in storage (a random path under
schools/{school_id}/) and who uploaded it. The original file name is kept as
a label only. Rows never change.

The bytes themselves live in Vercel Blob (local folder in development) behind
the FileStorage interface (D-059), and are delivered only through the
authorised files route (D-056). Checking what a file really contains (magic
bytes) and re-saving images without their metadata happen in the upload code.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from schoolflow_api.db import Base, IdMixin, one_of

IMAGE_LIMIT_BYTES = 1024 * 1024  # 1 MB for logos, signatures and stamps (D-057)
ATTACHMENT_LIMIT_BYTES = 4 * 1024 * 1024  # 4 MB for correction attachments (D-057)


class FilePurpose(StrEnum):
    LOGO = "logo"
    SIGNATURE = "signature"  # the principal's signature image on report cards
    STAMP = "stamp"  # the school stamp image on report cards
    CORRECTION_ATTACHMENT = "correction_attachment"


class StoredFile(IdMixin, Base):
    """One uploaded file ("File" would read like Python's own file objects)."""

    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        UniqueConstraint("storage_key"),
        CheckConstraint(one_of("purpose", FilePurpose), name="purpose_allowed"),
        # D-057: PNG, JPEG or WebP; PDF only for correction attachments; never SVG.
        CheckConstraint(
            "content_type IN ('image/png', 'image/jpeg', 'image/webp')"
            " OR (content_type = 'application/pdf' AND purpose = 'correction_attachment')",
            name="content_type_allowed",
        ),
        CheckConstraint(
            f"size_bytes BETWEEN 1 AND CASE WHEN purpose = 'correction_attachment'"
            f" THEN {ATTACHMENT_LIMIT_BYTES} ELSE {IMAGE_LIMIT_BYTES} END",
            name="size_within_limit",
        ),
        CheckConstraint("octet_length(sha256) = 32", name="sha256_length"),
        # Inside the school's own folder, with no way to climb out of it.
        CheckConstraint(
            "starts_with(storage_key, 'schools/' || school_id::text || '/')"
            " AND storage_key ~ '^[A-Za-z0-9._/-]+$'"
            " AND strpos(storage_key, '..') = 0"
            " AND char_length(storage_key) <= 255",
            name="storage_key_format",
        ),
        CheckConstraint(
            "btrim(original_name) <> '' AND char_length(original_name) <= 255",
            name="original_name_valid",
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    purpose: Mapped[str]
    storage_key: Mapped[str]
    content_type: Mapped[str]
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[bytes] = mapped_column(LargeBinary)
    # A label only; storage uses the random key above.
    original_name: Mapped[str]
    # Set by the database from the signed-in user.
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
