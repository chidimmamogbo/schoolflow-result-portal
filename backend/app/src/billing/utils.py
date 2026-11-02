"""How money and dates read in emails, notices and receipts (design rules: ₦321,000, 5 Jan 2027)."""

import datetime as dt
from typing import Any, cast


def money(kobo: int) -> str:
    naira, cents = divmod(kobo, 100)
    return f"₦{naira:,}.{cents:02d}" if cents else f"₦{naira:,}"


def nice_date(day: dt.date) -> str:
    return f"{day.day} {day:%b %Y}"


def field_of(data: object, name: str) -> Any:
    """A field of a webhook's JSON object; None for anything else."""
    return cast(dict[str, Any], data).get(name) if isinstance(data, dict) else None
