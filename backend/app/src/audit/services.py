"""Writing audit events (SPEC F11; D-156).

The app writes one event in the same transaction as each change, so the
change and its record succeed or fail together. The database fills in who
did it (the signed-in user) and when; never pass a password, token or hash
in the values (the table refuses those keys).
"""

import datetime as dt
import json
import uuid
from typing import Annotated, Any

from fastapi import Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import Principal, found
from app.src.audit.schemas import Timeline, TimelineEvent

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


Word = Annotated[str | None, Query(max_length=60, pattern=r"^[a-z_.]+$")]


def timeline(
    who: Principal,
    session: Session,
    area: Word = None,
    action: Word = None,
    actor_id: uuid.UUID | None = None,
    target_table: Word = None,
    target_id: uuid.UUID | None = None,
    since: dt.date | None = None,
    until: dt.date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Timeline:
    found(who.school_id)  # the super admin reads the platform log instead
    rows = list(
        session.execute(
            text(
                "select a.id, a.created_at, a.actor_id, u.full_name as actor_name, a.actor_role,"
                " a.action, a.target_table, a.target_id, a.old_values, a.new_values, a.reason,"
                " a.revision from audit_events a left join users u on u.id = a.actor_id"
                " where a.school_id = :school"
                " and (cast(:area as text) is null or split_part(a.action, '.', 1) = :area)"
                " and (cast(:action as text) is null or a.action = :action)"
                " and (cast(:actor as uuid) is null or a.actor_id = :actor)"
                " and (cast(:table as text) is null or a.target_table = :table)"
                " and (cast(:target as uuid) is null or a.target_id = :target)"
                " and (cast(:since as date) is null or a.created_at >= cast(:since as date))"
                " and (cast(:until as date) is null"
                "      or a.created_at < cast(:until as date) + 1)"
                " order by a.created_at desc, a.id desc limit :limit offset :offset"
            ),
            {
                "school": who.school_id,
                "area": area,
                "action": action,
                "actor": actor_id,
                "table": target_table,
                "target": target_id,
                "since": since,
                "until": until,
                "limit": limit + 1,
                "offset": offset,
            },
        )
    )
    return Timeline(
        events=[
            TimelineEvent(
                id=str(r.id),
                created_at=r.created_at,
                actor_id=str(r.actor_id) if r.actor_id else None,
                actor_name=r.actor_name,
                actor_role=r.actor_role,
                action=r.action,
                target_table=r.target_table,
                target_id=str(r.target_id) if r.target_id else None,
                old_values=r.old_values,
                new_values=r.new_values,
                reason=r.reason,
                revision=r.revision,
            )
            for r in rows[:limit]
        ],
        has_more=len(rows) > limit,
    )
