"""The billing routes: each takes the request and calls the service (D-173).

The rules live in services.py and processing.py. Three routers: the super
admin's (/platform), the school's (/school) and Paystack's public webhook, whose
signature check comes before anything else (D-094).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, Response
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.dependencies import DbSession, Principal, require
from app.core.errors import ProblemError
from app.core.rate_limit import limit_by_ip
from app.platform.payments.gateway import PaymentGateway
from app.src.billing import processing, services
from app.src.billing.schemas import (
    BillingSchoolRow,
    Checkout,
    Generate,
    Generated,
    InvoiceRow,
    ManualPayment,
    NewPricing,
    PaymentStatus,
    PricingPage,
    PricingVersionRow,
    Receipt,
    SchoolBilling,
    SubscriptionChange,
    SubscriptionRow,
    TermSummary,
    VoidInvoice,
    WebhookAnswer,
)
from app.src.platform_admin.dependencies import PlatformDb, RawPlatformDb

platform_router = APIRouter(prefix="/platform", tags=["billing"])
school_router = APIRouter(prefix="/school", tags=["billing"])
webhook_router = APIRouter(prefix="/webhooks", tags=["billing"])

Pricing = Annotated[Principal, Depends(require("pricing.manage"))]
Invoicing = Annotated[Principal, Depends(require("invoices.generate"))]
ManualPayments = Annotated[Principal, Depends(require("payments.record_manual"))]
Manage = Annotated[Principal, Depends(require("schools.manage"))]
BillingViewer = Annotated[Principal, Depends(require("billing.view"))]
Payer = Annotated[Principal, Depends(require("invoices.pay"))]


def get_payment_gateway() -> PaymentGateway:
    gateway = processing.real_gateway()
    if gateway is None:
        raise ProblemError(
            503,
            "We couldn't reach the payment service.",
            "Please try again in a few minutes.",
            code="payment_unavailable",
        )
    return gateway


def get_webhook_secret() -> SecretStr | None:
    return get_settings().paystack_secret_key


def get_base_url() -> str:
    return str(get_settings().app_base_url)


Gateway = Annotated[PaymentGateway, Depends(get_payment_gateway)]


# --- price lists ----------------------------------------------------------------------------------
@platform_router.get("/pricing", response_model=PricingPage)
def get_pricing(_: Pricing, db: PlatformDb) -> PricingPage:
    return services.get_pricing(db=db)


@platform_router.post("/pricing", status_code=201, response_model=PricingPage)
def save_pricing(body: NewPricing, _: Pricing, db: PlatformDb) -> PricingPage:
    return services.save_pricing(body=body, db=db)


@platform_router.get("/pricing/versions", response_model=list[PricingVersionRow])
def pricing_versions(_: Pricing, db: PlatformDb) -> list[PricingVersionRow]:
    return services.pricing_versions(db=db)


# --- invoices -------------------------------------------------------------------------------------
@platform_router.post("/invoices/generate", response_model=Generated)
def generate_invoices(body: Generate, _: Invoicing, db: PlatformDb) -> Generated:
    return services.generate_invoices(body=body, db=db)


@platform_router.get("/invoices", response_model=list[InvoiceRow])
def list_invoices(
    _: Invoicing, db: PlatformDb, school_id: uuid.UUID | None = None
) -> list[InvoiceRow]:
    return services.list_invoices(db=db, school_id=school_id)


@platform_router.get("/invoices/{invoice_id}", response_model=InvoiceRow)
def get_invoice(invoice_id: uuid.UUID, _: Invoicing, db: PlatformDb) -> InvoiceRow:
    return services.get_invoice(invoice_id=invoice_id, db=db)


@platform_router.post("/invoices/{invoice_id}/void", response_model=InvoiceRow)
def void_invoice(
    invoice_id: uuid.UUID, body: VoidInvoice, _: Invoicing, db: PlatformDb
) -> InvoiceRow:
    return services.void_invoice(invoice_id=invoice_id, body=body, db=db)


@platform_router.post("/invoices/{invoice_id}/manual-payment", response_model=InvoiceRow)
def manual_payment(
    invoice_id: uuid.UUID, body: ManualPayment, _: ManualPayments, db: PlatformDb
) -> InvoiceRow:
    return services.record_manual_payment(invoice_id=invoice_id, body=body, db=db)


@platform_router.post("/payments/{payment_id}/resend-receipt", status_code=204)
def resend_receipt(payment_id: uuid.UUID, _: ManualPayments, db: PlatformDb) -> None:
    services.resend_receipt(payment_id=payment_id, db=db)


# --- the overview ---------------------------------------------------------------------------------
@platform_router.get("/billing/schools", response_model=list[BillingSchoolRow])
def billing_schools(_: Invoicing, db: PlatformDb) -> list[BillingSchoolRow]:
    return services.billing_schools(db=db)


@platform_router.get("/billing/summary", response_model=list[TermSummary])
def billing_summary(_: Invoicing, db: PlatformDb) -> list[TermSummary]:
    return services.billing_summary(db=db)


@platform_router.patch("/schools/{school_id}/subscription", response_model=SubscriptionRow)
def change_subscription(
    school_id: uuid.UUID, body: SubscriptionChange, _: Manage, db: PlatformDb
) -> SubscriptionRow:
    return services.change_subscription(school_id=school_id, body=body, db=db)


# --- the school's side ----------------------------------------------------------------------------
@school_router.get("/billing", response_model=SchoolBilling)
def billing_card(who: BillingViewer, session: DbSession) -> SchoolBilling:
    return services.billing_card(who=who, session=session)


@school_router.get("/invoices", response_model=list[InvoiceRow])
def school_invoices(who: BillingViewer, session: DbSession) -> list[InvoiceRow]:
    return services.school_invoices(who=who, session=session)


@school_router.get("/invoices/{invoice_id}", response_model=InvoiceRow)
def school_invoice(invoice_id: uuid.UUID, who: BillingViewer, session: DbSession) -> InvoiceRow:
    return services.invoice_row(services.school_invoice(invoice_id, who, session))


@school_router.get("/invoices/{invoice_id}/receipt", response_model=Receipt)
def receipt(invoice_id: uuid.UUID, who: BillingViewer, session: DbSession) -> Receipt:
    return services.receipt_of(invoice_id=invoice_id, who=who, session=session)


@school_router.get("/invoices/{invoice_id}/receipt.pdf", response_class=Response)
def receipt_pdf(invoice_id: uuid.UUID, who: BillingViewer, session: DbSession) -> Response:
    return services.receipt_pdf(invoice_id=invoice_id, who=who, session=session)


# No request body: anything the browser sends, such as an amount, is never read (AT-37.2).
@school_router.post(
    "/invoices/{invoice_id}/pay",
    response_model=Checkout,
    dependencies=[Depends(limit_by_ip("invoice-pay", 30, 900))],
)
def pay_invoice(
    invoice_id: uuid.UUID,
    who: Payer,
    session: DbSession,
    gateway: Gateway,
    base_url: Annotated[str, Depends(get_base_url)],
) -> Checkout:
    return services.start_payment(
        invoice_id=invoice_id, who=who, session=session, gateway=gateway, base_url=base_url
    )


@school_router.get("/payments/verify", response_model=PaymentStatus)
def payment_status(
    reference: Annotated[str, Query(min_length=1, max_length=64)],
    who: BillingViewer,
    session: DbSession,
) -> PaymentStatus:
    return services.payment_status(reference=reference, who=who, session=session)


# --- Paystack's webhook (public; its signature is the check) --------------------------------------
async def raw_body(request: Request) -> bytes:
    """The exact bytes Paystack signed, before anything parses them."""
    return await request.body()


@webhook_router.post("/payments", response_model=WebhookAnswer)
def payment_webhook(
    body: Annotated[bytes, Depends(raw_body)],
    secret: Annotated[SecretStr | None, Depends(get_webhook_secret)],
    db: RawPlatformDb,
    background: BackgroundTasks,
    kick: Annotated[processing.Kick, Depends(processing.get_payment_kick)],
    x_paystack_signature: Annotated[str | None, Header()] = None,
) -> WebhookAnswer:
    if not services.signature_matches(body, x_paystack_signature, secret):
        # Nothing is stored and nothing says why (AC19.6).
        raise ProblemError(401, "Not allowed", code="signature_invalid")
    if services.store_event(db, body):
        background.add_task(kick)
    return WebhookAnswer(received=True)
