"""The email outbox (SPEC F18; BUILD_PROMPT 9.1 item 9; D-080 to D-083, D-153, D-154).

One row per email to send: type, address, template and its data, priority,
status (Queued, Sent, Failed), attempts and the next try, the last error
(cleaned of personal data) and a unique idempotency key, so each recipient
gets exactly one email per event (AC18.1). Secret links are made by the
sender at send time, never stored here (D-081), and the data never holds a
password or a score (checked by the database).

School users queue their school's emails and see status only; the platform
queues platform emails (no school) and sees every email's status; only the
background sender (app_sender, D-153) reads template data. The rules are
triggers in migration 17.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin, one_of

# Keys that must never appear in template data (F18, D-081, D-083).
FORBIDDEN_KEYS = (
    "password",
    "temporary_password",
    "token",
    "reset_token",
    "activation_token",
    "score",
    "scores",
    "grade",
    "grades",
    "position",
    "total",
    "average",
)
MAX_ATTEMPTS = 5
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class EmailStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"


class OutboxEmail(IdMixin, TimestampMixin, Base):
    __tablename__ = "email_outbox"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        Index(
            "ix_email_outbox_next_to_send",
            "priority",
            "next_attempt_at",
            postgresql_where=text("status = 'queued'"),
        ),
        CheckConstraint(one_of("status", EmailStatus), name="status_allowed"),
        CheckConstraint("type ~ '^[a-z][a-z_]{2,40}$'", name="type_format"),
        CheckConstraint("template ~ '^[a-z][a-z_]{2,40}$'", name="template_format"),
        CheckConstraint(
            f"to_address ~ '{EMAIL_PATTERN}' AND char_length(to_address) <= 254",
            name="to_address_format",
        ),
        CheckConstraint("jsonb_typeof(template_data) = 'object'", name="template_data_is_object"),
        CheckConstraint(
            "NOT template_data ?| array[" + ", ".join(f"'{k}'" for k in FORBIDDEN_KEYS) + "]",
            name="no_secrets_or_scores",
        ),
        # 1 goes first: account emails before bulk result emails (D-082).
        CheckConstraint("priority BETWEEN 1 AND 9", name="priority_range"),
        CheckConstraint(f"attempts BETWEEN 0 AND {MAX_ATTEMPTS}", name="attempts_range"),
        CheckConstraint(
            "status <> 'sent' OR (sent_at IS NOT NULL AND provider_message_id IS NOT NULL)",
            name="sent_with_proof",
        ),
        CheckConstraint(
            "btrim(idempotency_key) <> '' AND char_length(idempotency_key) <= 200",
            name="idempotency_key_valid",
        ),
        CheckConstraint("char_length(last_error) <= 500", name="last_error_length"),
    )

    # Empty for platform emails (a school admin's activation, for example).
    school_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("schools.id"))
    type: Mapped[str]
    to_address: Mapped[str]
    template: Mapped[str]
    template_data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    priority: Mapped[int] = mapped_column(SmallInteger, server_default=text("5"))
    status: Mapped[str] = mapped_column(server_default=EmailStatus.QUEUED.value)
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Cleaned of personal data before it is stored (D-080).
    last_error: Mapped[str | None]
    idempotency_key: Mapped[str]
    provider_message_id: Mapped[str | None]
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
