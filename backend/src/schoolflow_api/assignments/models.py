"""Who teaches, assists and reviews what (SPEC F06; D-049).

teacher_assignments: three kinds of row. A subject row says "this teacher
teaches Mathematics in JSS 1A". A learning area row (item 6a) says "this
teacher rates Letter work in Nursery 2". A form teacher row (neither) says
"this teacher is JSS 1A's form teacher" (called class teacher in Nursery and
Primary); with teaches_all_subjects it also covers every subject of the arm
and every learning area of its class, including ones added later, worked out
when asked through the teacher_subjects view (migrations 8 and 12). A
subject or area given to a specialist stays with the specialist.
class_assistants: up to two class teacher assistants per arm, who enter but
never submit (F06 rule 3).
reviewer_scopes: what an HOD or reviewer may review: a department, or
chosen subjects and classes.

Logins are checked by the check_member_role() trigger (a teacher, a
reviewer) and every link stays inside the school.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from schoolflow_api.db import Base, IdMixin, TimestampMixin

MEMBERSHIP = ["school_memberships.user_id", "school_memberships.school_id"]


class TeacherAssignment(IdMixin, TimestampMixin, Base):
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        ForeignKeyConstraint(["teacher_id", "school_id"], MEMBERSHIP),
        ForeignKeyConstraint(["arm_id", "school_id"], ["class_arms.id", "class_arms.school_id"]),
        # A subject row must name a subject the arm takes (AT: JSS 1B has no Igbo).
        ForeignKeyConstraint(
            ["arm_id", "subject_id"], ["arm_subjects.arm_id", "arm_subjects.subject_id"]
        ),
        Index(
            "ix_teacher_assignments_one_teacher_per_subject",
            "arm_id",
            "subject_id",
            unique=True,
            postgresql_where=text("subject_id IS NOT NULL"),
        ),
        # A learning area row must name an area of the arm's class (a trigger, migration 12).
        ForeignKeyConstraint(
            ["learning_area_id", "school_id"], ["learning_areas.id", "learning_areas.school_id"]
        ),
        Index(
            "ix_teacher_assignments_one_teacher_per_area",
            "arm_id",
            "learning_area_id",
            unique=True,
            postgresql_where=text("learning_area_id IS NOT NULL"),
        ),
        Index(
            "ix_teacher_assignments_one_form_teacher_per_arm",
            "arm_id",
            unique=True,
            postgresql_where=text("is_form_teacher"),
        ),
        Index(
            "ix_teacher_assignments_one_form_arm_per_teacher",
            "teacher_id",
            unique=True,
            postgresql_where=text("is_form_teacher"),
        ),
        Index("ix_teacher_assignments_teacher_id", "teacher_id"),
        # Exactly one kind: a subject, a learning area, or the form teacher row.
        CheckConstraint(
            "num_nonnulls(subject_id, learning_area_id) + is_form_teacher::int = 1",
            name="one_kind",
        ),
        CheckConstraint(
            "NOT teaches_all_subjects OR is_form_teacher", name="teaches_all_needs_form_teacher"
        ),
    )

    school_id: Mapped[uuid.UUID]
    teacher_id: Mapped[uuid.UUID]
    arm_id: Mapped[uuid.UUID]
    subject_id: Mapped[uuid.UUID | None]
    learning_area_id: Mapped[uuid.UUID | None]
    is_form_teacher: Mapped[bool] = mapped_column(server_default=text("false"))
    teaches_all_subjects: Mapped[bool] = mapped_column(server_default=text("false"))


class ClassAssistant(IdMixin, TimestampMixin, Base):
    __tablename__ = "class_assistants"
    __table_args__ = (
        UniqueConstraint("arm_id", "assistant_id"),
        ForeignKeyConstraint(["arm_id", "school_id"], ["class_arms.id", "class_arms.school_id"]),
        ForeignKeyConstraint(["assistant_id", "school_id"], MEMBERSHIP),
        Index("ix_class_assistants_assistant_id", "assistant_id"),
    )

    school_id: Mapped[uuid.UUID]
    arm_id: Mapped[uuid.UUID]
    # A teacher of the school; at most two per arm (a trigger in migration 8).
    assistant_id: Mapped[uuid.UUID]


class ReviewerScope(IdMixin, TimestampMixin, Base):
    __tablename__ = "reviewer_scopes"
    __table_args__ = (
        ForeignKeyConstraint(["reviewer_id", "school_id"], MEMBERSHIP),
        ForeignKeyConstraint(
            ["department_id", "school_id"], ["departments.id", "departments.school_id"]
        ),
        ForeignKeyConstraint(["subject_id", "school_id"], ["subjects.id", "subjects.school_id"]),
        ForeignKeyConstraint(["class_id", "school_id"], ["classes.id", "classes.school_id"]),
        # The same scope once per reviewer; empty columns count as equal here.
        Index(
            "ix_reviewer_scopes_unique_scope",
            "reviewer_id",
            "department_id",
            "subject_id",
            "class_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        # Either a whole department, or a subject and/or a class (F06 rule 1).
        CheckConstraint(
            "(department_id IS NOT NULL) <> (subject_id IS NOT NULL OR class_id IS NOT NULL)",
            name="department_or_subjects",
        ),
    )

    school_id: Mapped[uuid.UUID]
    reviewer_id: Mapped[uuid.UUID]
    department_id: Mapped[uuid.UUID | None]
    subject_id: Mapped[uuid.UUID | None]
    class_id: Mapped[uuid.UUID | None]
