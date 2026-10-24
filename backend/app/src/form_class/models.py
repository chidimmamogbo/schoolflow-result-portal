"""Tables for the form teacher's class sections (SPEC F22, F10, section 8; BUILD_PROMPT
9.1 item 6b; D-146, D-148).

class_report_sections: one row per arm per term with the status of the form
teacher's sections (Open, Submitted, Returned, Published), the revision, the
comment that came with the last move, and times school opened (once for the
class). Triggers in migration 14 check every move: only the arm's form or
class teacher submits, a return needs a comment, and a reopen needs a reason
and starts the next revision.
class_section_actions: every move, written only by the database and never
changed afterwards.
student_term_entries: one per pupil per section, with the form teacher's
comment, the head's comment and times present (never more than times school
opened).
student_trait_ratings: the pupil's affective and psychomotor ratings, one per
trait, on the school's 1 to 5 key.

Times absent is worked out (opened minus present), never stored.
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

from app.db.base import Base, IdMixin, TimestampMixin, one_of

SECTION = ["class_report_sections.id", "class_report_sections.school_id"]


def comment_valid(column: str) -> str:
    """Not blank and at most 300 characters (F22 rule 3)."""
    return f"btrim({column}) <> '' AND char_length({column}) <= 300"


class SectionStatus(StrEnum):
    """SPEC section 8 (v0.5.5). Teachers edit only while OPEN or RETURNED."""

    OPEN = "open"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    PUBLISHED = "published"


class ClassReportSection(IdMixin, TimestampMixin, Base):
    __tablename__ = "class_report_sections"
    __table_args__ = (
        UniqueConstraint("term_id", "arm_id"),
        UniqueConstraint("id", "school_id"),
        ForeignKeyConstraint(["term_id", "school_id"], ["terms.id", "terms.school_id"]),
        ForeignKeyConstraint(["arm_id", "school_id"], ["class_arms.id", "class_arms.school_id"]),
        CheckConstraint(one_of("status", SectionStatus), name="status_allowed"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint(
            "btrim(status_comment) <> '' AND char_length(status_comment) <= 1000",
            name="status_comment_valid",
        ),
        # No more than the days in a year, which also covers schools that count twice a day.
        CheckConstraint("times_school_opened BETWEEN 1 AND 366", name="times_school_opened_range"),
    )

    school_id: Mapped[uuid.UUID]
    term_id: Mapped[uuid.UUID]
    arm_id: Mapped[uuid.UUID]
    status: Mapped[str] = mapped_column(server_default=SectionStatus.OPEN.value)
    revision: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    # The comment that came with the last move: a return's comment, a reopen's reason.
    status_comment: Mapped[str | None]
    # Once for the class (F22 rule 5); set by the form teacher or an assistant.
    times_school_opened: Mapped[int | None] = mapped_column(SmallInteger)


class ClassSectionAction(IdMixin, Base):
    """One move of a class's sections; written only by the workflow trigger."""

    __tablename__ = "class_section_actions"
    __table_args__ = (
        ForeignKeyConstraint(["section_id", "school_id"], SECTION),
        Index("ix_class_section_actions_section_id", "section_id"),
    )

    school_id: Mapped[uuid.UUID]
    section_id: Mapped[uuid.UUID]
    revision_number: Mapped[int] = mapped_column(SmallInteger)
    from_status: Mapped[str]
    to_status: Mapped[str]
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    comment: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentTermEntry(IdMixin, TimestampMixin, Base):
    __tablename__ = "student_term_entries"
    __table_args__ = (
        UniqueConstraint("section_id", "enrolment_id"),
        UniqueConstraint("id", "school_id"),
        ForeignKeyConstraint(["section_id", "school_id"], SECTION),
        ForeignKeyConstraint(
            ["enrolment_id", "school_id"], ["enrolments.id", "enrolments.school_id"]
        ),
        Index("ix_student_term_entries_enrolment_id", "enrolment_id"),
        CheckConstraint(comment_valid("form_teacher_comment"), name="form_teacher_comment_valid"),
        CheckConstraint(comment_valid("head_comment"), name="head_comment_valid"),
        CheckConstraint("times_present >= 0", name="times_present_not_negative"),
    )

    school_id: Mapped[uuid.UUID]
    section_id: Mapped[uuid.UUID]
    enrolment_id: Mapped[uuid.UUID]
    # Shown as "Class teacher's comment" in Nursery and Primary (F22 rule 3).
    form_teacher_comment: Mapped[str | None]
    # Written by a school admin on the publish screen (F10) and labelled with the
    # template's head's title, for example "Principal's comment".
    head_comment: Mapped[str | None]
    times_present: Mapped[int | None] = mapped_column(SmallInteger)
    # Set by the database from the signed-in user, never by the request.
    entered_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class StudentTraitRating(IdMixin, TimestampMixin, Base):
    """One affective or psychomotor rating, for example Punctuality 5 (F22 rule 4)."""

    __tablename__ = "student_trait_ratings"
    __table_args__ = (
        UniqueConstraint("entry_id", "trait_id"),
        ForeignKeyConstraint(
            ["entry_id", "school_id"],
            ["student_term_entries.id", "student_term_entries.school_id"],
        ),
        ForeignKeyConstraint(
            ["trait_id", "school_id"], ["rating_traits.id", "rating_traits.school_id"]
        ),
        # The value must be a point on the school's own 1 to 5 key.
        ForeignKeyConstraint(
            ["school_id", "value"], ["trait_scale_points.school_id", "trait_scale_points.value"]
        ),
    )

    school_id: Mapped[uuid.UUID]
    entry_id: Mapped[uuid.UUID]
    trait_id: Mapped[uuid.UUID]
    value: Mapped[int] = mapped_column(SmallInteger)
    # Set by the database from the signed-in user, never by the request.
    entered_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
