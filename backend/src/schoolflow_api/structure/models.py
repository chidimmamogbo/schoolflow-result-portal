"""Tables for a school's structure (BUILD_PROMPT 9.1 item 3; SPEC F04).

academic_sessions and terms: the school year (2026/2027) and its three terms.
classes and class_arms: "JSS 1" at a level, with arms such as "A" (JSS 1A).
departments and subjects: subject groups (an HOD's scope) and the subjects.
arm_subjects: which subjects each arm takes (sheets and "Teaches all
subjects" are built from it).

Every table carries school_id (row-level security, D-137), and every link to
another table also repeats school_id, so a row can only ever point at a row
of the same school: the database refuses a GMC term inside a BSA session.
For that, each parent table has a unique (id, school_id) pair to point at.
"""

import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from schoolflow_api.db import Base, IdMixin, TimestampMixin

# Names are compared without caring about capitals: "JSS 1" and "jss 1" clash.
UNIQUE_LOWER_NAME = text("lower(name)")


class AcademicSession(IdMixin, TimestampMixin, Base):
    __tablename__ = "academic_sessions"
    __table_args__ = (
        UniqueConstraint("school_id", "name"),
        UniqueConstraint("id", "school_id"),
        # "2026/2027": two years, the second right after the first. CASE makes
        # sure the year arithmetic only runs on text that matched the pattern.
        CheckConstraint(
            "CASE WHEN name ~ '^[0-9]{4}/[0-9]{4}$'"
            " THEN split_part(name, '/', 2)::int = split_part(name, '/', 1)::int + 1"
            " ELSE false END",
            name="name_format",
        ),
        CheckConstraint("ends_on > starts_on", name="dates_in_order"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    name: Mapped[str]
    starts_on: Mapped[date]
    ends_on: Mapped[date]


class Term(IdMixin, TimestampMixin, Base):
    __tablename__ = "terms"
    __table_args__ = (
        UniqueConstraint("session_id", "term_number"),
        UniqueConstraint("id", "school_id"),
        ForeignKeyConstraint(
            ["session_id", "school_id"], ["academic_sessions.id", "academic_sessions.school_id"]
        ),
        # AC04.1: one active term per school; its session is the active session.
        Index(
            "ix_terms_one_active_per_school",
            "school_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        CheckConstraint("term_number BETWEEN 1 AND 3", name="term_number_allowed"),
        CheckConstraint("ends_on > starts_on", name="dates_in_order"),
        CheckConstraint(
            "next_term_begins IS NULL OR next_term_begins > ends_on", name="next_term_after_end"
        ),
    )

    school_id: Mapped[uuid.UUID]
    session_id: Mapped[uuid.UUID]
    # 1 First Term, 2 Second Term, 3 Third Term.
    term_number: Mapped[int] = mapped_column(SmallInteger)
    starts_on: Mapped[date]
    ends_on: Mapped[date]
    # Shown on report cards ("Next term begins"); term dates also drive billing renewal.
    next_term_begins: Mapped[date | None]
    is_active: Mapped[bool] = mapped_column(server_default=text("false"))


class SchoolClass(IdMixin, TimestampMixin, Base):
    """A class such as "JSS 1" or "Primary 4" ("class" is a reserved word in Python)."""

    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        # The level must be one of the school's four level rows; a trigger in
        # the migration also refuses a level that is switched off (AC04.2).
        ForeignKeyConstraint(
            ["school_id", "level"], ["school_levels.school_id", "school_levels.level"]
        ),
        Index("ix_classes_unique_name", "school_id", UNIQUE_LOWER_NAME, unique=True),
        CheckConstraint("btrim(name) <> '' AND char_length(name) <= 40", name="name_valid"),
    )

    school_id: Mapped[uuid.UUID]
    level: Mapped[str]
    name: Mapped[str]


class ClassArm(IdMixin, TimestampMixin, Base):
    """An arm of a class: "A" makes JSS 1A. Empty for a class with one arm (Nursery 2)."""

    __tablename__ = "class_arms"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        ForeignKeyConstraint(["class_id", "school_id"], ["classes.id", "classes.school_id"]),
        Index("ix_class_arms_unique_name", "class_id", UNIQUE_LOWER_NAME, unique=True),
        CheckConstraint("name = btrim(name) AND char_length(name) <= 20", name="name_valid"),
    )

    school_id: Mapped[uuid.UUID]
    class_id: Mapped[uuid.UUID]
    name: Mapped[str] = mapped_column(server_default="")


class Department(IdMixin, TimestampMixin, Base):
    """A group of subjects such as "Sciences", led by an HOD (reviewer scope, F06)."""

    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        Index("ix_departments_unique_name", "school_id", UNIQUE_LOWER_NAME, unique=True),
        CheckConstraint("btrim(name) <> '' AND char_length(name) <= 60", name="name_valid"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    name: Mapped[str]


class Subject(IdMixin, TimestampMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        ForeignKeyConstraint(
            ["department_id", "school_id"], ["departments.id", "departments.school_id"]
        ),
        Index("ix_subjects_unique_name", "school_id", UNIQUE_LOWER_NAME, unique=True),
        CheckConstraint("btrim(name) <> '' AND char_length(name) <= 80", name="name_valid"),
        CheckConstraint(
            "btrim(category) <> '' AND char_length(category) <= 60", name="category_valid"
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    name: Mapped[str]
    department_id: Mapped[uuid.UUID | None]
    # Optional, for "Group subjects by category" on report cards (SPEC v0.5.1),
    # for example "Science and Mathematics" or "Languages".
    category: Mapped[str | None]


class ArmSubject(IdMixin, TimestampMixin, Base):
    """A subject an arm takes: one result sheet per subject per arm (F09)."""

    __tablename__ = "arm_subjects"
    __table_args__ = (
        UniqueConstraint("arm_id", "subject_id"),
        ForeignKeyConstraint(["arm_id", "school_id"], ["class_arms.id", "class_arms.school_id"]),
        ForeignKeyConstraint(["subject_id", "school_id"], ["subjects.id", "subjects.school_id"]),
        Index("ix_arm_subjects_subject_id", "subject_id"),
    )

    school_id: Mapped[uuid.UUID]
    arm_id: Mapped[uuid.UUID]
    subject_id: Mapped[uuid.UUID]
