"""Tables for result sheets, scores and their workflow (SPEC F09, F10, F11, section 8).

result_sheets: one per subject (a score sheet) or per learning area of the
arm's class (a rating sheet, item 6a) per arm per term. It records the
assessment structure it uses (the structure used is stored with each
result, F08 rule 3), its workflow status and its current revision. The
status moves only along SPEC section 8; triggers in migrations 11 and 12
check every move (who, comments, separation of duties, completeness).
scores: raw component scores (totals, grades and positions are worked out by
the results engine, never stored here), each with its author.
result_revisions and approval_actions: the sheet's history, written only by
the workflow triggers and never changed afterwards (D-029, F11).
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
    SmallInteger,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from schoolflow_api.db import Base, IdMixin, TimestampMixin, one_of


class SheetStatus(StrEnum):
    """SPEC section 8. Teachers edit only in DRAFT and RETURNED_FOR_CORRECTION."""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED_FOR_CORRECTION = "returned_for_correction"
    RESUBMITTED = "resubmitted"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    PUBLISHED = "published"


class ResultSheet(IdMixin, TimestampMixin, Base):
    __tablename__ = "result_sheets"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        ForeignKeyConstraint(["term_id", "school_id"], ["terms.id", "terms.school_id"]),
        ForeignKeyConstraint(["arm_id", "school_id"], ["class_arms.id", "class_arms.school_id"]),
        ForeignKeyConstraint(
            ["structure_id", "school_id"],
            ["assessment_structures.id", "assessment_structures.school_id"],
        ),
        # A score sheet's subject must be one the arm takes.
        ForeignKeyConstraint(
            ["arm_id", "subject_id"], ["arm_subjects.arm_id", "arm_subjects.subject_id"]
        ),
        # A rating sheet's area must also be one of the arm's class (a trigger, migration 12).
        ForeignKeyConstraint(
            ["learning_area_id", "school_id"], ["learning_areas.id", "learning_areas.school_id"]
        ),
        Index(
            "ix_result_sheets_one_score_sheet",
            "term_id",
            "arm_id",
            "subject_id",
            unique=True,
            postgresql_where=text("subject_id IS NOT NULL"),
        ),
        Index(
            "ix_result_sheets_one_rating_sheet",
            "term_id",
            "arm_id",
            "learning_area_id",
            unique=True,
            postgresql_where=text("learning_area_id IS NOT NULL"),
        ),
        CheckConstraint(one_of("status", SheetStatus), name="status_allowed"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        # A score sheet (subject) or a rating sheet (learning area).
        CheckConstraint(
            "(subject_id IS NULL) <> (learning_area_id IS NULL)", name="subject_or_learning_area"
        ),
        CheckConstraint(
            "btrim(status_comment) <> '' AND char_length(status_comment) <= 1000",
            name="status_comment_valid",
        ),
    )

    school_id: Mapped[uuid.UUID]
    term_id: Mapped[uuid.UUID]
    arm_id: Mapped[uuid.UUID]
    structure_id: Mapped[uuid.UUID]
    subject_id: Mapped[uuid.UUID | None]
    learning_area_id: Mapped[uuid.UUID | None]
    status: Mapped[str] = mapped_column(server_default=SheetStatus.DRAFT.value)
    revision: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    # The comment that came with the last move: a return's comment, a reopen's reason.
    status_comment: Mapped[str | None]


class ResultRevision(IdMixin, Base):
    __tablename__ = "result_revisions"
    __table_args__ = (
        UniqueConstraint("sheet_id", "revision_number"),
        ForeignKeyConstraint(
            ["sheet_id", "school_id"], ["result_sheets.id", "result_sheets.school_id"]
        ),
        CheckConstraint("revision_number >= 1", name="revision_number_positive"),
        # Every reopen gives a reason (F10).
        CheckConstraint("revision_number = 1 OR btrim(reason) <> ''", name="reopen_has_reason"),
    )

    school_id: Mapped[uuid.UUID]
    sheet_id: Mapped[uuid.UUID]
    revision_number: Mapped[int] = mapped_column(SmallInteger)
    opened_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApprovalAction(IdMixin, Base):
    __tablename__ = "approval_actions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["sheet_id", "school_id"], ["result_sheets.id", "result_sheets.school_id"]
        ),
        Index("ix_approval_actions_sheet_id", "sheet_id"),
    )

    school_id: Mapped[uuid.UUID]
    sheet_id: Mapped[uuid.UUID]
    revision_number: Mapped[int] = mapped_column(SmallInteger)
    from_status: Mapped[str]
    to_status: Mapped[str]
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Score(IdMixin, TimestampMixin, Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("sheet_id", "enrolment_id", "component_id"),
        ForeignKeyConstraint(
            ["sheet_id", "school_id"], ["result_sheets.id", "result_sheets.school_id"]
        ),
        ForeignKeyConstraint(
            ["enrolment_id", "school_id"], ["enrolments.id", "enrolments.school_id"]
        ),
        Index("ix_scores_enrolment_id", "enrolment_id"),
        CheckConstraint("value >= 0", name="value_not_negative"),
        CheckConstraint(
            "btrim(change_reason) <> '' AND char_length(change_reason) <= 300",
            name="change_reason_valid",
        ),
    )

    school_id: Mapped[uuid.UUID]
    sheet_id: Mapped[uuid.UUID]
    enrolment_id: Mapped[uuid.UUID]
    component_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_components.id"))
    # Whole marks (AT-11.2); the column's maximum is checked by a trigger.
    value: Mapped[int] = mapped_column(SmallInteger)
    # Set by the database from the signed-in user, never by the request.
    entered_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # Required once the sheet has been submitted (D-143); the audit trail keeps each one.
    change_reason: Mapped[str | None]
