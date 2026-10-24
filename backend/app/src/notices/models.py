"""Tables for the notice board (SPEC F17; BUILD_PROMPT 9.1 item 9; D-084 to D-086, D-154).

notices: a school's notice, manual (posted by a school admin) or system (for
example "First Term results for JSS 1 are now available"), with its title,
plain-text body, pin and status (Published, Archived).
notice_audiences: what the admin chose: everyone, roles, classes.
notice_recipients: the people the notice reached, worked out when it was
posted (D-084), each a member of the notice's school.
notice_reads: who has read it, for the unread badge.

The rules that read other tables are triggers in migration 17.
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin, one_of
from app.src.accounts.models import MembershipRole

NOTICE = ["notices.id", "notices.school_id"]
MEMBERSHIP = ["school_memberships.user_id", "school_memberships.school_id"]


class NoticeKind(StrEnum):
    MANUAL = "manual"
    SYSTEM = "system"


class NoticeStatus(StrEnum):
    PUBLISHED = "published"
    ARCHIVED = "archived"


class Notice(IdMixin, TimestampMixin, Base):
    __tablename__ = "notices"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        Index("ix_notices_school_id", "school_id"),
        CheckConstraint(one_of("kind", NoticeKind), name="kind_allowed"),
        CheckConstraint(one_of("status", NoticeStatus), name="status_allowed"),
        CheckConstraint("btrim(title) <> '' AND char_length(title) <= 120", name="title_valid"),
        # Plain text only (D-086); shown as text, never as HTML.
        CheckConstraint("btrim(body) <> '' AND char_length(body) <= 5000", name="body_valid"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    title: Mapped[str]
    body: Mapped[str]
    kind: Mapped[str] = mapped_column(server_default=NoticeKind.MANUAL.value)
    pinned: Mapped[bool] = mapped_column(server_default=text("false"))
    status: Mapped[str] = mapped_column(server_default=NoticeStatus.PUBLISHED.value)
    # Set by the database from the signed-in user; empty for a system notice made with
    # nobody signed in (a payment webhook).
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class NoticeAudience(IdMixin, Base):
    """One choice the admin made; no role and no class means everyone."""

    __tablename__ = "notice_audiences"
    __table_args__ = (
        ForeignKeyConstraint(["notice_id", "school_id"], NOTICE),
        ForeignKeyConstraint(["class_id", "school_id"], ["classes.id", "classes.school_id"]),
        Index(
            "ix_notice_audiences_unique_choice",
            "notice_id",
            "role",
            "class_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(one_of("role", MembershipRole), name="role_allowed"),
    )

    school_id: Mapped[uuid.UUID]
    notice_id: Mapped[uuid.UUID]
    role: Mapped[str | None]
    class_id: Mapped[uuid.UUID | None]


class NoticeRecipient(IdMixin, Base):
    __tablename__ = "notice_recipients"
    __table_args__ = (
        UniqueConstraint("notice_id", "user_id"),
        ForeignKeyConstraint(["notice_id", "school_id"], NOTICE),
        ForeignKeyConstraint(["user_id", "school_id"], MEMBERSHIP),
        Index("ix_notice_recipients_user_id", "user_id"),
    )

    school_id: Mapped[uuid.UUID]
    notice_id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID]


class NoticeRead(IdMixin, Base):
    __tablename__ = "notice_reads"
    __table_args__ = (
        UniqueConstraint("notice_id", "user_id"),
        ForeignKeyConstraint(["notice_id", "school_id"], NOTICE),
        ForeignKeyConstraint(["user_id", "school_id"], MEMBERSHIP),
    )

    school_id: Mapped[uuid.UUID]
    notice_id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID]
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
