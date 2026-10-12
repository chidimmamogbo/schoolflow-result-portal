"""Tables for schools, their feature switches and their report card levels.

Like custom tables a WordPress plugin registers, but each Python class here is
one table, each attribute one column, and the CHECK rules are enforced by
PostgreSQL itself. The migration in migrations/versions creates them.
"""

import uuid
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from schoolflow_api.db import Base, IdMixin, TimestampMixin, one_of


class SchoolStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"  # super admin only, with a reason; data is kept (F24)


class SchoolType(StrEnum):
    """F25 rule 1. "custom" is shown when the toggles no longer match a type."""

    NURSERY_PRIMARY = "nursery_primary"
    SECONDARY_ONLY = "secondary_only"
    ALL_LEVELS = "all_levels"
    CUSTOM = "custom"


class Feature(StrEnum):
    """The six feature switches (F01). A switch that is off rejects requests."""

    RESULTS = "results"
    REPORT_CARDS = "report_cards"
    PARENT_PORTAL = "parent_portal"
    CORRECTION_QUEUE = "correction_queue"
    NOTICE_BOARD = "notice_board"
    EMAIL_NOTIFICATIONS = "email_notifications"


class Level(StrEnum):
    """Four rows per school (option A). One "Secondary report cards" toggle
    switches junior and senior secondary together; the database enforces it."""

    NURSERY = "nursery"
    PRIMARY = "primary"
    JUNIOR_SECONDARY = "junior_secondary"
    SENIOR_SECONDARY = "senior_secondary"


class AssessmentMode(StrEnum):
    SCORES = "scores"
    SKILL_RATINGS = "skill_ratings"


class School(IdMixin, TimestampMixin, Base):
    __tablename__ = "schools"
    __table_args__ = (
        UniqueConstraint("code"),
        CheckConstraint("code ~ '^[A-Z0-9]{3,10}$'", name="code_format"),
        CheckConstraint("colour ~ '^#[0-9A-Fa-f]{6}$'", name="colour_hex"),
        CheckConstraint("btrim(name) <> ''", name="name_not_blank"),
        CheckConstraint(r"email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'", name="email_format"),
        CheckConstraint(one_of("status", SchoolStatus), name="status_allowed"),
        CheckConstraint(one_of("school_type", SchoolType), name="school_type_allowed"),
    )

    name: Mapped[str]
    email: Mapped[str]
    phone: Mapped[str]
    address: Mapped[str]
    city: Mapped[str]
    state: Mapped[str]
    country: Mapped[str] = mapped_column(server_default="Nigeria")
    # Students log in with this code (F02); changing it stops the old one working.
    code: Mapped[str]
    colour: Mapped[str]
    # The uploaded logo; the files table and its link arrive with file storage.
    logo_file_id: Mapped[uuid.UUID | None]
    status: Mapped[str] = mapped_column(server_default=SchoolStatus.ACTIVE.value)
    school_type: Mapped[str]


class SchoolFeature(IdMixin, TimestampMixin, Base):
    __tablename__ = "school_features"
    __table_args__ = (
        UniqueConstraint("school_id", "feature"),
        CheckConstraint(one_of("feature", Feature), name="feature_allowed"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    feature: Mapped[str]
    enabled: Mapped[bool]


class SchoolLevel(IdMixin, TimestampMixin, Base):
    __tablename__ = "school_levels"
    __table_args__ = (
        UniqueConstraint("school_id", "level"),
        CheckConstraint(one_of("level", Level), name="level_allowed"),
        CheckConstraint(one_of("assessment_mode", AssessmentMode), name="assessment_mode_allowed"),
        CheckConstraint("btrim(head_title) <> ''", name="head_title_not_blank"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    level: Mapped[str]
    # Report card toggle: only the super admin changes it (F25 rule 3).
    enabled: Mapped[bool]
    assessment_mode: Mapped[str]
    # Labels the head's comment and signature on report cards (F12 rule 0).
    head_title: Mapped[str]
