"""Tables for the correction queue (SPEC F15, section 8; BUILD_PROMPT 9.1 item 8; D-151,
D-152).

correction_requests: "Report a problem" on a published report, numbered per
school (shown as CR-0012): which subject or learning area (none means the
whole report), what looks wrong, the explanation, who sent it, the status
(Open, Investigating, Needs more information, Resolved, Rejected), the
message that came with the last move and, once resolved, the newer report
revision that fixed it (D-151).
correction_events: the timeline the requester and the school see, written
only by the database and never changed.
correction_attachments: the one optional file sent with a request.

The rules that read other tables are triggers in migration 16.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from schoolflow_api.db import Base, IdMixin, TimestampMixin, one_of

REQUEST = ["correction_requests.id", "correction_requests.school_id"]
REPORT = ["report_documents.id", "report_documents.school_id"]
MESSAGE_VALID = "btrim({0}) <> '' AND char_length({0}) <= 1000"


class IssueType(StrEnum):
    """The "What looks wrong?" choices on the Report a problem form."""

    SCORE = "score"  # A score looks wrong
    DETAIL = "detail"  # A name or detail is wrong
    OTHER = "other"  # Something else


class CorrectionStatus(StrEnum):
    """SPEC section 8."""

    OPEN = "open"
    INVESTIGATING = "investigating"
    NEEDS_MORE_INFORMATION = "needs_more_information"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class CorrectionRequest(IdMixin, TimestampMixin, Base):
    __tablename__ = "correction_requests"
    __table_args__ = (
        UniqueConstraint("school_id", "number"),
        UniqueConstraint("id", "school_id"),
        ForeignKeyConstraint(["report_document_id", "school_id"], REPORT),
        ForeignKeyConstraint(["corrected_report_id", "school_id"], REPORT),
        ForeignKeyConstraint(["subject_id", "school_id"], ["subjects.id", "subjects.school_id"]),
        ForeignKeyConstraint(
            ["learning_area_id", "school_id"], ["learning_areas.id", "learning_areas.school_id"]
        ),
        Index("ix_correction_requests_report_document_id", "report_document_id"),
        CheckConstraint("number >= 1", name="number_positive"),
        CheckConstraint(one_of("issue_type", IssueType), name="issue_type_allowed"),
        CheckConstraint(one_of("status", CorrectionStatus), name="status_allowed"),
        # One subject or learning area at most; none means the whole report.
        CheckConstraint(
            "num_nonnulls(subject_id, learning_area_id) <= 1", name="one_subject_or_area"
        ),
        CheckConstraint(MESSAGE_VALID.format("explanation"), name="explanation_valid"),
        CheckConstraint(MESSAGE_VALID.format("status_message"), name="status_message_valid"),
        CheckConstraint(
            "corrected_report_id IS NULL OR status = 'resolved'",
            name="corrected_only_when_resolved",
        ),
    )

    school_id: Mapped[uuid.UUID]
    # Numbered by the database per school; shown as CR-0012.
    number: Mapped[int] = mapped_column(Integer)
    # The published report the problem is about.
    report_document_id: Mapped[uuid.UUID]
    subject_id: Mapped[uuid.UUID | None]
    learning_area_id: Mapped[uuid.UUID | None]
    issue_type: Mapped[str]
    explanation: Mapped[str]
    status: Mapped[str] = mapped_column(server_default=CorrectionStatus.OPEN.value)
    # The message that came with the last move: the school's answer or the requester's reply.
    status_message: Mapped[str | None]
    # Set by the database from the signed-in user.
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    # The pupil's newer report revision that fixed the problem (D-151).
    corrected_report_id: Mapped[uuid.UUID | None]


class CorrectionEvent(IdMixin, Base):
    """One step of a request's timeline: sent, investigating, answered, replied ..."""

    __tablename__ = "correction_events"
    __table_args__ = (
        ForeignKeyConstraint(["request_id", "school_id"], REQUEST),
        Index("ix_correction_events_request_id", "request_id"),
    )

    school_id: Mapped[uuid.UUID]
    request_id: Mapped[uuid.UUID]
    # Empty for the first step, when the request is sent.
    from_status: Mapped[str | None]
    to_status: Mapped[str]
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    message: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CorrectionAttachment(IdMixin, Base):
    __tablename__ = "correction_attachments"
    __table_args__ = (
        # One optional attachment per request (F15).
        UniqueConstraint("request_id"),
        UniqueConstraint("file_id"),
        ForeignKeyConstraint(["request_id", "school_id"], REQUEST),
        ForeignKeyConstraint(["file_id", "school_id"], ["files.id", "files.school_id"]),
    )

    school_id: Mapped[uuid.UUID]
    request_id: Mapped[uuid.UUID]
    file_id: Mapped[uuid.UUID]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
