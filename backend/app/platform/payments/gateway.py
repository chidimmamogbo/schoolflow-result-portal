"""The payment gateway: Paystack in test mode (SPEC F19 rule 11; D-087, D-093, D-094).

Two calls, both with the secret key, both only from the server:

- initialize: "this school is about to pay this amount under this reference";
  Paystack answers with a checkout page address. The amount always comes from
  our invoice, never the browser.
- verify: "what really happened to this reference?" A webhook only tells us
  to look; this answer is the proof.

Paystack API, Accept payments and Webhooks pages, read through Context7 on
2026-11-02 (paystack.com blocks automated reading).
"""

from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import quote

import httpx

API = "https://api.paystack.co"


class GatewayError(Exception):
    def __init__(self, detail: str, *, temporary: bool) -> None:
        super().__init__(detail)
        self.temporary = temporary


@dataclass(frozen=True)
class Verified:
    """What Paystack says happened (amount in kobo)."""

    status: str
    amount_kobo: int
    currency: str
    reference: str
    gateway_id: str


class PaymentGateway(Protocol):
    def initialize(
        self, *, email: str, amount_kobo: int, reference: str, callback_url: str
    ) -> str: ...

    def verify(self, reference: str) -> Verified: ...


class PaystackGateway:
    def __init__(self, secret_key: str, client: httpx.Client | None = None) -> None:
        self._headers = {"Authorization": f"Bearer {secret_key}"}
        self._client = client or httpx.Client(timeout=10)

    def _answer(self, method: str, path: str, **options: Any) -> dict[str, Any]:
        try:
            response = self._client.request(
                method, f"{API}{path}", headers=self._headers, **options
            )
        except httpx.HTTPError as error:
            raise GatewayError(type(error).__name__, temporary=True) from error
        if response.status_code == 429 or response.status_code >= 500:
            raise GatewayError(f"Paystack answered {response.status_code}", temporary=True)
        if response.status_code >= 400:
            raise GatewayError(f"Paystack answered {response.status_code}", temporary=False)
        try:
            body: dict[str, Any] = response.json()
            data: dict[str, Any] = body["data"]
        except (ValueError, KeyError, TypeError) as error:
            raise GatewayError("Paystack sent an unreadable answer", temporary=True) from error
        return data

    def initialize(self, *, email: str, amount_kobo: int, reference: str, callback_url: str) -> str:
        data = self._answer(
            "POST",
            "/transaction/initialize",
            json={
                "email": email,
                # Paystack takes the amount in kobo, as a string in its examples.
                "amount": str(amount_kobo),
                "currency": "NGN",
                "reference": reference,
                "callback_url": callback_url,
            },
        )
        return str(data["authorization_url"])

    def verify(self, reference: str) -> Verified:
        data = self._answer("GET", f"/transaction/verify/{quote(reference, safe='')}")
        try:
            return Verified(
                status=str(data["status"]),
                amount_kobo=int(data["amount"]),
                currency=str(data["currency"]),
                reference=str(data["reference"]),
                gateway_id=str(data["id"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise GatewayError("Paystack sent an unreadable answer", temporary=True) from error


@dataclass
class RecordingGateway:
    """For tests and local runs: no network; answers what it is told to."""

    answers: dict[str, Verified | GatewayError] = field(default_factory=dict[str, Any])
    fail_initialize: GatewayError | None = None
    started: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    verified: list[str] = field(default_factory=list[str])

    def initialize(self, *, email: str, amount_kobo: int, reference: str, callback_url: str) -> str:
        if self.fail_initialize is not None:
            raise self.fail_initialize
        self.started.append(
            {
                "email": email,
                "amount_kobo": amount_kobo,
                "reference": reference,
                "callback_url": callback_url,
            }
        )
        return f"https://checkout.example/{reference}"

    def verify(self, reference: str) -> Verified:
        self.verified.append(reference)
        answer = self.answers.get(reference)
        if answer is None:
            raise GatewayError("Paystack answered 404", temporary=False)
        if isinstance(answer, GatewayError):
            raise answer
        return answer
