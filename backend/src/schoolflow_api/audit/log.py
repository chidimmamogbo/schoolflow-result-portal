"""Writing audit events (SPEC F11; D-156).

The app writes one event in the same transaction as each change, so the
change and its record succeed or fail together. The database fills in who
did it (the signed-in user) and when; never pass a password, token or hash
in the values (the table refuses those keys).
"""

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

_INSERT = text(
    "insert into audit_events (school_id, actor_role, action, target_table, target_id,"
    " old_values, new_values, reason) values (:school, :role, :action, :table, :target,"
    " cast(:old as jsonb), cast(:new as jsonb), :reason)"
)


def write_audit(
    session: Session,
    school_id: uuid.UUID | None,
    actor_role: str,
    action: str,
    *,
    target: tuple[str, uuid.UUID] | None = None,
    old: dict[str, Any] | None = None,
    new: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    session.execute(
        _INSERT,
        {
            "school": school_id,
            "role": actor_role,
            "action": action,
            "table": target[0] if target else None,
            "target": target[1] if target else None,
            "old": json.dumps(old, default=str) if old is not None else None,
            "new": json.dumps(new, default=str) if new is not None else None,
            "reason": reason,
        },
    )
