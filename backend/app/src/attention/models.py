"""Students needing attention entries (SPEC F23; BUILD_PROMPT 9.2 j2; D-147, D-150).

Written inside the publish transaction from the published snapshot and never
changed: one row per finding, linked to the report revision it came from.

- subject: a subject total below the pass mark (By subject view).
- skill: a skill rated at or below the attention point, with the rating word
  as published (By learning area view, Skill ratings levels).
- student: one summary per pupil, the number of failed subjects or skills and
  the average (By student view).

Lists read only the rows of each pupil's current Valid report, so a republish
replaces them without deleting history (AT-23.1). Who sees which rows (school
admins, HODs, teachers) is decided by the API (F23 rule 5).
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    SmallInteger,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, one_of

# What each kind of entry must (and must not) carry.
SUBJECT_FIELDS = (
    "kind <> 'subject' OR (subject_id IS NOT NULL AND score IS NOT NULL AND grade IS NOT NULL"
    " AND pass_mark IS NOT NULL AND learning_area_id IS NULL AND skill_id IS NULL"
    " AND rating IS NULL AND failed_count IS NULL AND average IS NULL)"
)
SKILL_FIELDS = (
    "kind <> 'skill' OR (learning_area_id IS NOT NULL AND skill_id IS NOT NULL"
    " AND rating IS NOT NULL AND subject_id IS NULL AND score IS NULL AND grade IS NULL"
    " AND pass_mark IS NULL AND failed_count IS NULL AND average IS NULL)"
)
STUDENT_FIELDS = (
    "kind <> 'student' OR (failed_count >= 1 AND subject_id IS NULL AND learning_area_id IS NULL"
    " AND skill_id IS NULL AND score IS NULL AND grade IS NULL AND rating IS NULL)"
)


class AttentionKind(StrEnum):
    SUBJECT = "subject"
    SKILL = "skill"
    STUDENT = "student"


class AttentionEntry(IdMixin, Base):
    __tablename__ = "attention_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["report_document_id", "school_id"],
            ["report_documents.id", "report_documents.school_id"],
        ),
        ForeignKeyConstraint(["subject_id", "school_id"], ["subjects.id", "subjects.school_id"]),
        ForeignKeyConstraint(
            ["learning_area_id", "school_id"], ["learning_areas.id", "learning_areas.school_id"]
        ),
        ForeignKeyConstraint(["skill_id", "school_id"], ["skills.id", "skills.school_id"]),
        Index("ix_attention_entries_report_document_id", "report_document_id"),
        Index(
            "ix_attention_entries_one_per_subject",
            "report_document_id",
            "subject_id",
            unique=True,
            postgresql_where=text("kind = 'subject'"),
        ),
        Index(
            "ix_attention_entries_one_per_skill",
            "report_document_id",
            "skill_id",
            unique=True,
            postgresql_where=text("kind = 'skill'"),
        ),
        Index(
            "ix_attention_entries_one_summary",
            "report_document_id",
            unique=True,
            postgresql_where=text("kind = 'student'"),
        ),
        CheckConstraint(one_of("kind", AttentionKind), name="kind_allowed"),
        CheckConstraint(SUBJECT_FIELDS, name="subject_fields"),
        CheckConstraint(SKILL_FIELDS, name="skill_fields"),
        CheckConstraint(STUDENT_FIELDS, name="student_fields"),
        CheckConstraint("score < pass_mark", name="below_pass_mark"),
        CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
        CheckConstraint("pass_mark BETWEEN 1 AND 99", name="pass_mark_range"),
        CheckConstraint("average BETWEEN 0 AND 100", name="average_range"),
        CheckConstraint("grade ~ '^[A-Z][A-Z0-9+-]{0,3}$'", name="grade_format"),
        CheckConstraint("btrim(rating) <> '' AND char_length(rating) <= 30", name="rating_valid"),
    )

    school_id: Mapped[uuid.UUID]
    # The report revision this finding came from.
    report_document_id: Mapped[uuid.UUID]
    kind: Mapped[str]
    subject_id: Mapped[uuid.UUID | None]
    # The subject or learning area teacher when the class was published (F23 rule 2).
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    score: Mapped[int | None] = mapped_column(SmallInteger)
    grade: Mapped[str | None]
    # The school's pass mark at publication (F08 rule 4).
    pass_mark: Mapped[int | None] = mapped_column(SmallInteger)
    learning_area_id: Mapped[uuid.UUID | None]
    skill_id: Mapped[uuid.UUID | None]
    # The rating word as published, for example "Needs improvement" (AC26.4).
    rating: Mapped[str | None]
    failed_count: Mapped[int | None] = mapped_column(SmallInteger)
    average: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
