"""Requests and responses of the verification routes (D-173)."""

import datetime as dt
from typing import Literal

from app.core.schemas import ApiModel


class Verification(ApiModel):
    status: Literal["valid", "superseded", "revoked"]
    school: str
    student: str
    session: str
    term: str
    report_id: str
    revision: int
    published_at: dt.datetime | None
    has_newer_revision: bool
    newer_revision: int | None  # the newest revision, for "A newer version exists (...)"
    newer_published_at: dt.datetime | None
