"""Request and response shapes for billing (BUILD_PROMPT 9.2q to 9.2s). Money is integer kobo."""

import datetime as dt
from typing import Annotated, Literal

from pydantic import Field

from app.core.schemas import ApiModel

Reason = Annotated[str, Field(min_length=1, max_length=500)]
PlanName = Annotated[str, Field(min_length=1, max_length=40)]


class PlanForm(ApiModel):
    name: PlanName
    min_students: Annotated[int, Field(ge=1, le=1_000_000)]
    max_students: Annotated[int, Field(ge=1, le=1_000_000)] | None
    price_kobo: Annotated[int, Field(gt=0, le=100_000_000)]


class NewPricing(ApiModel):
    plans: Annotated[list[PlanForm], Field(max_length=20)]


class StudentRange(ApiModel):
    from_students: int
    to_students: int


class PricingPage(ApiModel):
    # None until the first save: the plans shown are the defaults.
    version: int | None
    plans: list[PlanForm]
    price_check: list[StudentRange]
    cliff_protection: bool


class PricingVersionRow(ApiModel):
    version: int
    created_at: dt.datetime
    plans: list[PlanForm]


class Generate(ApiModel):
    # Empty: every billable school.
    school_id: str | None = None
    # With a school: an adjustment invoice for pupils added after the term invoice.
    adjustment_students: Annotated[int, Field(ge=1, le=1_000_000)] | None = None


class InvoiceRow(ApiModel):
    id: str
    school_id: str
    term: str
    kind: str
    billable_students: int
    plan: str
    rate_kobo: int
    amount_kobo: int
    cliff_cap_applied: bool
    due_on: dt.date
    status: str
    paid_at: dt.datetime | None
    void_reason: str | None
    reference: str | None
    receipt_number: str | None
    created_at: dt.datetime


class Skipped(ApiModel):
    school_id: str
    name: str
    reason: str


class Generated(ApiModel):
    created: list[InvoiceRow]
    skipped: list[Skipped]


class VoidInvoice(ApiModel):
    reason: Reason


class ManualPayment(ApiModel):
    reference: Annotated[str, Field(min_length=1, max_length=100)]
    note: Reason


class BillingSchoolRow(ApiModel):
    id: str
    name: str
    code: str
    billing_enabled: bool
    status: str
    grace_period_days: int
    students: int
    current_invoice: InvoiceRow | None


class TermSummary(ApiModel):
    term: str
    invoices: int
    invoiced_kobo: int
    paid_kobo: int
    outstanding_kobo: int


class SubscriptionChange(ApiModel):
    billing_enabled: bool | None = None
    # Empty on purpose means "use the platform setting"; left out means no change.
    grace_period_days: Annotated[int, Field(ge=0, le=90)] | None = None
    use_platform_grace: bool = False
    suspended: bool | None = None
    reason: Reason | None = None


class SubscriptionRow(ApiModel):
    school_id: str
    billing_enabled: bool
    status: str
    grace_period_days: int


class SchoolBilling(ApiModel):
    billing_enabled: bool
    status: str
    # The rest is empty when billing is off (AC19.9).
    plan: str | None = None
    billable_students: int | None = None
    price_per_student_kobo: int | None = None
    amount_due_kobo: int | None = None
    due_on: dt.date | None = None
    next_renewal_on: dt.date | None = None
    projected_next_term_kobo: int | None = None
    current_invoice: InvoiceRow | None = None


class Checkout(ApiModel):
    checkout_url: str
    reference: str


class PaymentStatus(ApiModel):
    reference: str
    status: Literal["pending", "succeeded", "failed"]
    invoice_id: str
    invoice_status: str
    receipt_number: str | None


class Receipt(ApiModel):
    receipt_number: str
    school_name: str
    term: str
    plan: str
    billable_students: int
    amount_kobo: int
    reference: str
    paid_at: dt.datetime


class WebhookAnswer(ApiModel):
    received: bool
