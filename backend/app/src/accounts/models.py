"""Tables for accounts and their links to schools (BUILD_PROMPT 9.1 item 2).

users: one row per person who can log in (like WordPress's wp_users table).
school_memberships: which school an account belongs to, and in what role
(a bit like WordPress user roles, but per school).

Rules that need more than one row (the super admin has no school, staff work
in one school, only the parent links their account to another school) are
database triggers in the migration; who may see or change what is row-level
security there too (D-137, D-138).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin, one_of


class MembershipRole(StrEnum):
    """The five school roles (D-045). The super admin is a platform role with no school."""

    SCHOOL_ADMIN = "school_admin"  # the principal is a school admin with is_primary
    REVIEWER = "reviewer"
    TEACHER = "teacher"
    PARENT = "parent"
    STUDENT = "student"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    # The school paused this person's access to the school (their account and
    # any other school's link are untouched, D-138).
    PAUSED = "paused"


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        # D-033: emails are unique on the whole platform (stored in lowercase).
        UniqueConstraint("email"),
        # D-033: staff, parent and super admin usernames are unique on the
        # whole platform; student usernames only within their school.
        Index(
            "ix_users_username_platform",
            "username",
            unique=True,
            postgresql_where=text("student_school_id IS NULL"),
        ),
        Index(
            "ix_users_username_per_school",
            "student_school_id",
            "username",
            unique=True,
            postgresql_where=text("student_school_id IS NOT NULL"),
        ),
        CheckConstraint("username ~ '^[a-z0-9._-]{3,30}$'", name="username_format"),
        CheckConstraint(
            r"email = lower(email) AND email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'",
            name="email_format",
        ),
        CheckConstraint(
            "btrim(full_name) <> '' AND char_length(full_name) <= 200", name="full_name_valid"
        ),
        CheckConstraint(
            "NOT (is_super_admin AND student_school_id IS NOT NULL)",
            name="super_admin_not_student",
        ),
        # D-040: a temporary password always forces a change at first login.
        CheckConstraint(
            "temp_password_expires_at IS NULL OR must_change_password",
            name="temporary_password_must_change",
        ),
    )

    full_name: Mapped[str]
    username: Mapped[str]
    # Optional: many pupils and some parents have none (F02 rule 7).
    email: Mapped[str | None]
    # Argon2id hash (D-035); empty until the person activates the account.
    password_hash: Mapped[str | None]
    must_change_password: Mapped[bool] = mapped_column(server_default=text("false"))
    temp_password_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Only made by the CLI command (D-048); no app role may set it.
    is_super_admin: Mapped[bool] = mapped_column(server_default=text("false"))
    # Set only for pupils: the school whose code they log in with (F02 rule 1).
    student_school_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("schools.id"))


class SchoolMembership(IdMixin, TimestampMixin, Base):
    __tablename__ = "school_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "school_id"),
        # Staff and pupils belong to one school; only parents can have links
        # in several schools (D-138).
        Index(
            "ix_school_memberships_one_non_parent_school",
            "user_id",
            unique=True,
            postgresql_where=text("role <> 'parent'"),
        ),
        Index(
            "ix_school_memberships_one_principal",
            "school_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
        Index("ix_school_memberships_school_id_role", "school_id", "role"),
        CheckConstraint(one_of("role", MembershipRole), name="role_allowed"),
        CheckConstraint(one_of("status", MembershipStatus), name="status_allowed"),
        CheckConstraint("NOT is_primary OR role = 'school_admin'", name="primary_is_school_admin"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    role: Mapped[str]
    # The principal (D-045); only the platform sets it (F03 rule 5).
    is_primary: Mapped[bool] = mapped_column(server_default=text("false"))
    status: Mapped[str] = mapped_column(server_default=MembershipStatus.ACTIVE.value)
