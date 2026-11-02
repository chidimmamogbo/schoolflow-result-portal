"""The receipt page, for PDFs from the WeasyPrint pipeline (D-060, D-095). Always light."""

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from app.src.billing.schemas import Receipt
from app.src.billing.utils import money, nice_date

environment = Environment(
    loader=PackageLoader("app.src.billing", "html"),
    autoescape=select_autoescape(default=True, default_for_string=True),
    undefined=StrictUndefined,
)


def receipt_html(receipt: Receipt) -> str:
    return environment.get_template("receipt.html").render(
        receipt=receipt,
        amount=money(receipt.amount_kobo),
        paid_on=nice_date(receipt.paid_at.date()),
    )
