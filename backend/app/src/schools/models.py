"""Tables for schools, their feature switches and their report card levels.

Like custom tables a WordPress plugin registers, but each Python class here is
one table, each attribute one column, and the CHECK rules are enforced by
PostgreSQL itself. The migration in migrations/versions creates them.
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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin, one_of


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


class LoginLayout(StrEnum):
    """F02 rule 12: "Half and half" or "Picture behind"."""

    HALF = "half"
    BEHIND = "behind"


class LoginPicture(StrEnum):
    """F02 rule 12: "Pattern", "People" or "Your own photo"."""

    PATTERN = "pattern"
    PEOPLE = "people"
    PHOTO = "photo"


class School(IdMixin, TimestampMixin, Base):
    __tablename__ = "schools"
    __table_args__ = (
        UniqueConstraint("code"),
        # The logo is one of the school's own files (approved CHANGE, item 8). Files also
        # point back at schools, so this link is added after both tables exist (use_alter).
        ForeignKeyConstraint(
            ["logo_file_id", "id"], ["files.id", "files.school_id"], use_alter=True
        ),
        ForeignKeyConstraint(
            ["login_photo_file_id", "id"], ["files.id", "files.school_id"], use_alter=True
        ),
        CheckConstraint(one_of("login_layout", LoginLayout), name="login_layout_allowed"),
        CheckConstraint(one_of("login_picture", LoginPicture), name="login_picture_allowed"),
        CheckConstraint(
            "login_message is null or (btrim(login_message) <> ''"
            " and char_length(login_message) <= 80 and login_message !~ '[\\r\\n]')",
            name="login_message_valid",
        ),
        CheckConstraint(
            "login_picture <> 'photo' or login_photo_file_id is not null",
            name="login_photo_when_chosen",
        ),
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
    # The uploaded logo, a row of the files table (migration 16).
    logo_file_id: Mapped[uuid.UUID | None]
    status: Mapped[str] = mapped_column(server_default=SchoolStatus.ACTIVE.value)
    school_type: Mapped[str]
    # The school's own login page (migration 29, CHANGE C, D-182).
    login_layout: Mapped[str] = mapped_column(server_default=LoginLayout.HALF.value)
    login_picture: Mapped[str] = mapped_column(server_default=LoginPicture.PATTERN.value)
    login_message: Mapped[str | None]
    login_photo_file_id: Mapped[uuid.UUID | None]


class SchoolCodeChange(IdMixin, Base):
    """Old school codes, so a login link with one forwards for 30 days (migration 29).

    Written only by the owner-run trigger on schools; no app role reads it.
    """

    __tablename__ = "school_code_changes"
    __table_args__ = (Index("ix_school_code_changes_old_code", "old_code", "changed_at"),)

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    old_code: Mapped[str]
    new_code: Mapped[str]
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
