"""The audit log (SPEC F11; BUILD_PROMPT 9.1 item 11; D-051, D-156).

audit_events: one row per important action: who (set by the database from
the signed-in user), their role at the time, what (`scores.update`), on which
row, the old and new values, the reason and the revision. School events
carry the school; platform events (pricing, school set-up) carry none.

Like WordPress activity-log plugins, but stricter: rows are never changed or
deleted, not even by the table owner (trigger in migration 18), and never
hold password, token or hash keys.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin
from app.src.accounts.models import MembershipRole

SECRET_KEYS = (
    "password",
    "password_hash",
    "temporary_password",
    "token",
    "token_hash",
    "session_token",
    "secret",
)
ACTOR_ROLES = (*(role.value for role in MembershipRole), "super_admin", "system")
NO_SECRETS = "array[" + ", ".join(f"'{key}'" for key in SECRET_KEYS) + "]"


class AuditEvent(IdMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_school_id_created_at", "school_id", "created_at"),
        Index("ix_audit_events_target", "target_table", "target_id"),
        CheckConstraint(r"action ~ '^[a-z][a-z_]*\.[a-z][a-z_]*$'", name="action_format"),
        CheckConstraint(
            "actor_role in (" + ", ".join(f"'{role}'" for role in ACTOR_ROLES) + ")",
            name="actor_role_allowed",
        ),
        CheckConstraint(
            f"NOT coalesce(old_values, '{{}}') ?| {NO_SECRETS}"
            f" AND NOT coalesce(new_values, '{{}}') ?| {NO_SECRETS}",
            name="no_secrets",
        ),
    )

    # Empty for platform events.
    school_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("schools.id"))
    # Set by the database from the signed-in user; empty for system work (a webhook).
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    actor_role: Mapped[str]
    action: Mapped[str]
    target_table: Mapped[str | None]
    target_id: Mapped[uuid.UUID | None]
    old_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason: Mapped[str | None]
    revision: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
