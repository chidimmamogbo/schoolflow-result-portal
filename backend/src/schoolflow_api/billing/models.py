"""Tables for billing (SPEC F19; BUILD_PROMPT 9.1 item 10; D-087 to D-097, D-155).

pricing_versions and pricing_tiers: each save of the pricing table is a new
version with its plans (Basic, Standard, Premium), prices in kobo. Versions
never change, so an issued invoice always points at the prices it used.
school_subscriptions: one per school: billing on or off (free pilot) and the
subscription status.
invoices: one term invoice per school per term (plus adjustments), a snapshot
of the count, plan, rate and amount at issue (D-091). Only the status moves.
payments: one try at paying an invoice through the gateway; the amount comes
from the invoice, never the browser (D-093).
payment_events: the raw log of signature-verified webhook events, one row per
gateway event (D-094).

Money is integer kobo (BigInteger), never a float. The rules that read other
tables are triggers in migration 18.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from schoolflow_api.db import Base, IdMixin, TimestampMixin, one_of


class SubscriptionStatus(StrEnum):
    FREE_PILOT = "free_pilot"
    ACTIVE = "active"
    DUE = "due"
    OVERDUE = "overdue"
    SUSPENDED = "suspended"


class InvoiceKind(StrEnum):
    TERM = "term"
    ADJUSTMENT = "adjustment"


class InvoiceStatus(StrEnum):
    UNPAID = "unpaid"
    PAID = "paid"
    VOID = "void"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PaymentEventStatus(StrEnum):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"


class PricingVersion(IdMixin, Base):
    __tablename__ = "pricing_versions"
    __table_args__ = (UniqueConstraint("version"),)

    # Numbered by the database: 1, 2, 3 ...
    version: Mapped[int]
    # The super admin who saved it, set by the database.
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PricingTier(IdMixin, Base):
    __tablename__ = "pricing_tiers"
    __table_args__ = (
        UniqueConstraint("version_id", "position"),
        Index("ix_pricing_tiers_unique_name", "version_id", text("lower(name)"), unique=True),
        CheckConstraint("btrim(name) <> '' AND char_length(name) <= 40", name="name_valid"),
        CheckConstraint("position >= 1", name="position_positive"),
        CheckConstraint(
            "min_students >= 1 AND (max_students IS NULL OR max_students >= min_students)",
            name="range_valid",
        ),
        CheckConstraint("price_kobo > 0", name="price_positive"),
    )

    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pricing_versions.id"))
    position: Mapped[int]
    name: Mapped[str]
    min_students: Mapped[int]
    # Empty for the open-ended last plan ("1,001 and above").
    max_students: Mapped[int | None]
    # Price per student per term.
    price_kobo: Mapped[int] = mapped_column(BigInteger)


class SchoolSubscription(IdMixin, TimestampMixin, Base):
    __tablename__ = "school_subscriptions"
    __table_args__ = (
        UniqueConstraint("school_id"),
        CheckConstraint(one_of("status", SubscriptionStatus), name="status_allowed"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    billing_enabled: Mapped[bool] = mapped_column(server_default=text("false"))
    status: Mapped[str] = mapped_column(server_default=SubscriptionStatus.FREE_PILOT.value)


class Invoice(IdMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("id", "school_id"),
        ForeignKeyConstraint(["term_id", "school_id"], ["terms.id", "terms.school_id"]),
        Index("ix_invoices_school_id", "school_id"),
        # One live term invoice per school per term; a void one can be issued again.
        Index(
            "ix_invoices_one_per_term",
            "school_id",
            "term_id",
            unique=True,
            postgresql_where=text("kind = 'term' AND status <> 'void'"),
        ),
        CheckConstraint(one_of("kind", InvoiceKind), name="kind_allowed"),
        CheckConstraint(one_of("status", InvoiceStatus), name="status_allowed"),
        CheckConstraint("billable_students > 0", name="students_positive"),
        CheckConstraint("rate_kobo > 0 AND amount_kobo > 0", name="money_positive"),
        # The cliff cap only ever lowers the amount, and is flagged exactly when it did.
        CheckConstraint(
            "amount_kobo <= rate_kobo * billable_students"
            " AND cliff_cap_applied = (amount_kobo < rate_kobo * billable_students)",
            name="amount_matches",
        ),
        CheckConstraint("status <> 'paid' OR paid_at IS NOT NULL", name="paid_with_time"),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    term_id: Mapped[uuid.UUID]
    kind: Mapped[str] = mapped_column(server_default=InvoiceKind.TERM.value)
    # The snapshot (D-091): count, prices used, plan, rate and amount.
    billable_students: Mapped[int]
    pricing_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pricing_versions.id"))
    tier_name: Mapped[str]
    rate_kobo: Mapped[int] = mapped_column(BigInteger)
    amount_kobo: Mapped[int] = mapped_column(BigInteger)
    cliff_cap_applied: Mapped[bool]
    due_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(server_default=InvoiceStatus.UNPAID.value)
    void_reason: Mapped[str | None]
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The super admin who issued it, set by the database.
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class Payment(IdMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("reference"),
        UniqueConstraint("receipt_number"),
        ForeignKeyConstraint(["invoice_id", "school_id"], ["invoices.id", "invoices.school_id"]),
        Index("ix_payments_invoice_id", "invoice_id"),
        # One succeeded payment per invoice (AC19.7).
        Index(
            "ix_payments_one_success",
            "invoice_id",
            unique=True,
            postgresql_where=text("status = 'succeeded'"),
        ),
        CheckConstraint(one_of("status", PaymentStatus), name="status_allowed"),
        CheckConstraint("gateway = 'paystack'", name="gateway_allowed"),
        CheckConstraint("currency = 'NGN'", name="currency_ngn"),
        CheckConstraint("amount_kobo > 0", name="amount_positive"),
        CheckConstraint("reference ~ '^[A-Za-z0-9-]{6,64}$'", name="reference_format"),
        CheckConstraint(
            "status <> 'succeeded' OR (verified_at IS NOT NULL AND gateway_reference IS NOT NULL)",
            name="succeeded_with_proof",
        ),
        CheckConstraint(
            "(status = 'succeeded') = (receipt_number IS NOT NULL)", name="receipt_on_success"
        ),
    )

    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("schools.id"))
    invoice_id: Mapped[uuid.UUID]
    # Our reference sent to the gateway.
    reference: Mapped[str]
    gateway: Mapped[str] = mapped_column(server_default=text("'paystack'"))
    # Copied from the invoice by the database (D-093).
    amount_kobo: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(server_default=text("'NGN'"))
    status: Mapped[str] = mapped_column(server_default=PaymentStatus.PENDING.value)
    # From Verify Transaction, set by the platform's worker (D-094).
    gateway_reference: Mapped[str | None]
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None]
    # SF-RCPT-000001, numbered by the database on success (D-095).
    receipt_number: Mapped[str | None]
    # The school admin who started it, set by the database.
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class PaymentEvent(IdMixin, Base):
    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id"),
        CheckConstraint("provider = 'paystack'", name="provider_allowed"),
        CheckConstraint(one_of("status", PaymentEventStatus), name="status_allowed"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_is_object"),
    )

    provider: Mapped[str]
    # The gateway's own id for the event: the same event twice is refused (AC19.7).
    event_id: Mapped[str]
    event_type: Mapped[str]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(server_default=PaymentEventStatus.RECEIVED.value)
    error: Mapped[str | None]
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
