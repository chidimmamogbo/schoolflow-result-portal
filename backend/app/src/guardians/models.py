"""Tables for parents as each school knows them (SPEC F07, F21; D-138, D-140).

guardians: the school's own record of a parent (name, phone, email it was
given, consent). One parent can have a record in several schools; each
school keeps and edits only its own. user_id points at the parent's login
once there is one.
guardian_students: which pupils a guardian may see, with the relationship.
Access follows these links on the very next request (D-049).
parent_link_requests: a school's emailed request for a parent to link their
login (D-138). It holds only the email the school typed, never anything from
an existing account, so the school cannot tell whether the email already
uses SchoolFlow (option 2A, D-140).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.src.auth.models import TOKEN_HASH_BYTES

EMAIL_FORMAT = r"email = lower(email) AND email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'"


class Guardian(IdMixin, TimestampMixin, Base):
    __tablename__ = "guardians"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        UniqueConstraint("school_id", "user_id"),
        # The login must be a member of this school (a trigger checks it is a parent).
        ForeignKeyConstraint(
            ["user_id", "school_id"],
            ["school_memberships.user_id", "school_memberships.school_id"],
        ),
        CheckConstraint(
            "btrim(full_name) <> '' AND char_length(full_name) <= 200", name="full_name_valid"
        ),
        CheckConstraint(EMAIL_FORMAT, name="email_format"),
        # For example 08030001122, 0803 000 1122 or +234 803 000 1122.
        CheckConstraint(r"phone ~ '^\+?[0-9][0-9 ()-]{5,19}$'", name="phone_format"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    user_id: Mapped[uuid.UUID | None]
    full_name: Mapped[str]
    phone: Mapped[str | None]
    email: Mapped[str | None]
    # When the school recorded the parent's consent under its privacy notice (F21).
    privacy_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GuardianStudent(IdMixin, TimestampMixin, Base):
    __tablename__ = "guardian_students"
    __table_args__ = (
        UniqueConstraint("guardian_id", "student_id"),
        ForeignKeyConstraint(["guardian_id", "school_id"], ["guardians.id", "guardians.school_id"]),
        ForeignKeyConstraint(["student_id", "school_id"], ["students.id", "students.school_id"]),
        Index("ix_guardian_students_student_id", "student_id"),
        CheckConstraint(
            "btrim(relationship) <> '' AND char_length(relationship) <= 40",
            name="relationship_valid",
        ),
    )

    school_id: Mapped[uuid.UUID]
    guardian_id: Mapped[uuid.UUID]
    student_id: Mapped[uuid.UUID]
    # In the school's words, for example "Father", "Mother", "Aunt".
    relationship: Mapped[str]


class ParentLinkRequest(IdMixin, Base):
    __tablename__ = "parent_link_requests"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        ForeignKeyConstraint(["guardian_id", "school_id"], ["guardians.id", "guardians.school_id"]),
        Index(
            "ix_parent_link_requests_one_open_per_guardian",
            "guardian_id",
            unique=True,
            postgresql_where=text(
                "accepted_at IS NULL AND declined_at IS NULL AND cancelled_at IS NULL"
            ),
        ),
        # A signed-in parent's waiting requests are found by their verified email.
        Index("ix_parent_link_requests_email", "email"),
        CheckConstraint(EMAIL_FORMAT, name="email_format"),
        CheckConstraint(f"octet_length(token_hash) = {TOKEN_HASH_BYTES}", name="token_hash_length"),
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
        CheckConstraint(
            "num_nonnulls(accepted_at, declined_at, cancelled_at) <= 1", name="one_outcome"
        ),
    )

    school_id: Mapped[uuid.UUID]
    guardian_id: Mapped[uuid.UUID]
    email: Mapped[str]
    # Hash of the token in the emailed link (D-039 style): the link itself is never stored.
    token_hash: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # 14 days (SPEC section 12).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
