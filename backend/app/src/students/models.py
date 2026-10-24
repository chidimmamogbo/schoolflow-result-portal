"""Tables for pupils, their enrolment and their subjects (SPEC F05; D-139).

students: one row per pupil in a school (children's data: least privilege,
F21). A login is optional; nursery pupils usually have none (F14).
enrolments: which arm a pupil is in for a session. Moving arms ends one
enrolment (left_on) and starts another, so history is kept.
student_subjects: the subjects a pupil takes in an enrolment; a result sheet
lists only pupils who take its subject (AC05.2).

Same-school links throughout: every reference repeats school_id (see
structure/models.py), and row-level security keeps each school to its own
rows (migration 7).
"""

import uuid
from datetime import date
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin, one_of


class Gender(StrEnum):
    FEMALE = "female"
    MALE = "male"


class StudentStatus(StrEnum):
    """Billing counts active pupils with an enrolment (F19, F25 rule 6)."""

    ACTIVE = "active"
    WITHDRAWN = "withdrawn"
    GRADUATED = "graduated"


class Student(IdMixin, TimestampMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        UniqueConstraint("user_id"),
        # Unique within the school, whatever the capitals (AC02.6: another school may reuse it).
        Index(
            "ix_students_unique_admission_number",
            "school_id",
            text("lower(admission_number)"),
            unique=True,
        ),
        Index("ix_students_name_order", "school_id", "surname", "first_name"),
        # A pupil's login must be a member of this school (a trigger checks the role).
        ForeignKeyConstraint(
            ["user_id", "school_id"],
            ["school_memberships.user_id", "school_memberships.school_id"],
        ),
        ForeignKeyConstraint(
            ["department_id", "school_id"], ["departments.id", "departments.school_id"]
        ),
        # Letters, numbers and / . _ - with no spaces, because pupils type it to log in.
        CheckConstraint(
            "admission_number ~ '^[A-Za-z0-9][A-Za-z0-9/._-]{0,29}$'",
            name="admission_number_format",
        ),
        CheckConstraint(
            "btrim(surname) <> '' AND char_length(surname) <= 60", name="surname_valid"
        ),
        CheckConstraint(
            "btrim(first_name) <> '' AND char_length(first_name) <= 60", name="first_name_valid"
        ),
        CheckConstraint(
            "btrim(other_names) <> '' AND char_length(other_names) <= 100",
            name="other_names_valid",
        ),
        CheckConstraint("btrim(house) <> '' AND char_length(house) <= 40", name="house_valid"),
        CheckConstraint(one_of("gender", Gender), name="gender_allowed"),
        CheckConstraint(one_of("status", StudentStatus), name="status_allowed"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    user_id: Mapped[uuid.UUID | None]
    admission_number: Mapped[str]
    surname: Mapped[str]
    first_name: Mapped[str]
    other_names: Mapped[str | None]
    gender: Mapped[str]
    date_of_birth: Mapped[date | None]
    house: Mapped[str | None]
    # Senior Secondary only (Science, Arts, Commercial: the school's own list).
    department_id: Mapped[uuid.UUID | None]
    # The passport photo; the files table and its link arrive with file storage.
    photo_file_id: Mapped[uuid.UUID | None]
    status: Mapped[str] = mapped_column(server_default=StudentStatus.ACTIVE.value)


class Enrolment(IdMixin, TimestampMixin, Base):
    __tablename__ = "enrolments"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        ForeignKeyConstraint(
            ["session_id", "school_id"], ["academic_sessions.id", "academic_sessions.school_id"]
        ),
        ForeignKeyConstraint(["arm_id", "school_id"], ["class_arms.id", "class_arms.school_id"]),
        # One current arm per pupil per session; ended enrolments stay as history.
        Index(
            "ix_enrolments_one_current_per_session",
            "student_id",
            "session_id",
            unique=True,
            postgresql_where=text("left_on IS NULL"),
        ),
        Index("ix_enrolments_arm_id_session_id", "arm_id", "session_id"),
        CheckConstraint("left_on IS NULL OR left_on >= enrolled_on", name="left_after_enrolled"),
    )

    school_id: Mapped[uuid.UUID]
    student_id: Mapped[uuid.UUID]
    session_id: Mapped[uuid.UUID]
    arm_id: Mapped[uuid.UUID]
    enrolled_on: Mapped[date] = mapped_column(server_default=func.current_date())
    left_on: Mapped[date | None]


class StudentSubject(IdMixin, TimestampMixin, Base):
    __tablename__ = "student_subjects"
    __table_args__ = (
        UniqueConstraint("enrolment_id", "subject_id"),
        ForeignKeyConstraint(
            ["enrolment_id", "school_id"], ["enrolments.id", "enrolments.school_id"]
        ),
        ForeignKeyConstraint(["subject_id", "school_id"], ["subjects.id", "subjects.school_id"]),
        Index("ix_student_subjects_subject_id", "subject_id"),
    )

    school_id: Mapped[uuid.UUID]
    enrolment_id: Mapped[uuid.UUID]
    # Must be a subject the enrolment's arm takes (a trigger in the migration checks).
    subject_id: Mapped[uuid.UUID]
