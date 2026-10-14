"""Tables for report cards and their verification (SPEC F11, F12, F13, section 8;
BUILD_PROMPT 9.1 item 7; D-058, D-072, D-073, D-149, D-150).

report_templates: each save is a new version of a level's template, with its
style and settings (JSON, checked against the API's schema, D-061). Versions
never change, so a published report keeps the version it was issued with.
report_documents: one per pupil per term per revision: the frozen snapshot and
its SHA-256 hash, the template version, the report ID, the verification code
(kept so regenerated PDFs print the same QR, D-149), the masked name for the
verify page and the status (Valid, Superseded, Revoked). PDFs are regenerated
from these, never stored (D-058).
verification_tokens: the SHA-256 hash of each report's code, written by the
database when a report is published. The public lookup, verify_report()
(migration 15), reads only this and returns only the published facts.

The rules that read other tables are triggers in migration 15.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    SmallInteger,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from schoolflow_api.db import Base, IdMixin, one_of

HASH_BYTES = 32  # SHA-256
# D-072: three groups of four Crockford Base32 characters (no I, L, O or U), 7KQ4-M2XD-P9QA.
CODE_GROUP = "[0-9A-HJKMNP-TV-Z]{4}"
CODE_PATTERN = f"^{CODE_GROUP}-{CODE_GROUP}-{CODE_GROUP}$"


class ReportStyle(StrEnum):
    """F12 rule 1. The last three come after the core."""

    MODERN = "modern"
    CLASSIC = "classic"
    COMPACT = "compact"
    EARLY_YEARS = "early_years"
    BOLD_BANNER = "bold_banner"
    INK_SAVER = "ink_saver"
    CUMULATIVE = "cumulative"


class ReportStatus(StrEnum):
    """SPEC section 8: Valid, then Superseded (a newer revision) or Revoked (with a reason)."""

    VALID = "valid"
    SUPERSEDED = "superseded"
    REVOKED = "revoked"


class ReportTemplate(IdMixin, Base):
    __tablename__ = "report_templates"
    __table_args__ = (
        UniqueConstraint("school_id", "level", "version"),
        UniqueConstraint("id", "school_id"),
        ForeignKeyConstraint(
            ["school_id", "level"], ["school_levels.school_id", "school_levels.level"]
        ),
        CheckConstraint(one_of("style", ReportStyle), name="style_allowed"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("jsonb_typeof(settings) = 'object'", name="settings_is_object"),
    )

    school_id: Mapped[uuid.UUID]
    level: Mapped[str]
    # Numbered by the database, 1, 2, 3 ... per school and level ("Save as version {n}").
    version: Mapped[int] = mapped_column(SmallInteger)
    style: Mapped[str]
    # Head's title, block order, block settings and template settings (F12 rules 0 to 4).
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Set by the database from the signed-in user.
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportDocument(IdMixin, Base):
    """One pupil's published report for a term, at one revision."""

    __tablename__ = "report_documents"
    __table_args__ = (
        UniqueConstraint("enrolment_id", "term_id", "revision"),
        UniqueConstraint("school_id", "report_code", "revision"),
        UniqueConstraint("verification_code"),
        UniqueConstraint("id", "school_id"),
        ForeignKeyConstraint(["term_id", "school_id"], ["terms.id", "terms.school_id"]),
        ForeignKeyConstraint(["arm_id", "school_id"], ["class_arms.id", "class_arms.school_id"]),
        ForeignKeyConstraint(
            ["enrolment_id", "school_id"], ["enrolments.id", "enrolments.school_id"]
        ),
        ForeignKeyConstraint(
            ["template_id", "school_id"], ["report_templates.id", "report_templates.school_id"]
        ),
        Index("ix_report_documents_term_id_arm_id", "term_id", "arm_id"),
        CheckConstraint(one_of("status", ReportStatus), name="status_allowed"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        # GMC-2627-T1-JSS1A-014 (AT-16.2): capitals and digits in groups joined by dashes.
        CheckConstraint(
            "report_code ~ '^[A-Z0-9]+(-[A-Z0-9]+)*$' AND char_length(report_code) <= 64",
            name="report_code_format",
        ),
        CheckConstraint(f"verification_code ~ '{CODE_PATTERN}'", name="verification_code_format"),
        CheckConstraint("jsonb_typeof(snapshot) = 'object'", name="snapshot_is_object"),
        CheckConstraint(f"octet_length(snapshot_hash) = {HASH_BYTES}", name="snapshot_hash_length"),
        CheckConstraint(
            "calculation_version ~ '^[0-9A-Za-z.-]{1,20}$'", name="calculation_version_format"
        ),
        CheckConstraint(
            "btrim(revoke_reason) <> '' AND char_length(revoke_reason) <= 500",
            name="revoke_reason_valid",
        ),
        # Revoked exactly when a reason, a person and a time are recorded.
        CheckConstraint(
            "(status = 'revoked') = (revoked_at IS NOT NULL AND revoked_by IS NOT NULL"
            " AND revoke_reason IS NOT NULL)",
            name="revoked_with_reason",
        ),
    )

    school_id: Mapped[uuid.UUID]
    term_id: Mapped[uuid.UUID]
    arm_id: Mapped[uuid.UUID]
    enrolment_id: Mapped[uuid.UUID]
    template_id: Mapped[uuid.UUID]
    # Numbered by the database per pupil and term; a new revision supersedes the last.
    revision: Mapped[int] = mapped_column(SmallInteger)
    report_code: Mapped[str]
    # Printed as the QR code; only its hash is in verification_tokens (D-073, D-149).
    verification_code: Mapped[str]
    status: Mapped[str] = mapped_column(server_default=ReportStatus.VALID.value)
    # Everything the card shows, frozen at publication (AT-16.2).
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Worked out by the database: SHA-256 of the stored snapshot's text.
    snapshot_hash: Mapped[bytes] = mapped_column(LargeBinary)
    calculation_version: Mapped[str]
    # For the verify page, worked out by the database: "Chuk*** O." (D-074).
    masked_name: Mapped[str]
    published_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None]


class VerificationToken(IdMixin, Base):
    """The SHA-256 hash of one report's verification code; never the code itself."""

    __tablename__ = "verification_tokens"
    __table_args__ = (
        UniqueConstraint("code_hash"),
        UniqueConstraint("report_document_id"),
        ForeignKeyConstraint(
            ["report_document_id", "school_id"],
            ["report_documents.id", "report_documents.school_id"],
        ),
        CheckConstraint(f"octet_length(code_hash) = {HASH_BYTES}", name="code_hash_length"),
    )

    school_id: Mapped[uuid.UUID]
    report_document_id: Mapped[uuid.UUID]
    code_hash: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
