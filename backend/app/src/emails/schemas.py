"""What the school's Emails page sends (CHANGE 2026-11-12 B)."""

from datetime import datetime

from app.core.schemas import ApiModel


class SchoolEmailRow(ApiModel):
    """Status only (D-083): never the template data, the body or provider error text."""

    id: str
    type: str
    to_address: str
    status: str
    attempts: int
    created_at: datetime
    sent_at: datetime | None
