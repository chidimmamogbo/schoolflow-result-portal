"""Queueing emails in the outbox (SPEC F18; D-080, D-081, D-083).

The sender writes and sends them soon after the request commits (trigger.py,
D-177). Template data never
holds a password, token, link or score (the table refuses those keys); links
are made by the sender at send time.
"""

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.platform.email.trigger import note_queued

_INSERT = text(
    "insert into email_outbox (school_id, type, to_address, template, template_data,"
    " priority, idempotency_key) values (:school, :template, :to, :template,"
    " cast(:data as jsonb), :priority, :key)"
)


def queue_email(
    session: Session,
    school_id: uuid.UUID | None,
    template: str,
    to_address: str,
    data: dict[str, Any],
    *,
    priority: int = 1,
) -> None:
    """Queue one email; every call is a new event (a resend is a new email)."""
    session.execute(
        _INSERT,
        {
            "school": school_id,
            "template": template,
            "to": to_address,
            "data": json.dumps(data),
            "priority": priority,
            "key": f"{template}:{school_id}:{uuid.uuid4()}",
        },
    )
    note_queued(session)
