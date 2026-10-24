"""The school's audit timeline (BUILD_PROMPT 9.2j; SPEC F11; D-171).

Every change in the school writes an audit event in its own transaction
(`audit/log.write_audit`); here school admins (`audit.view`) read them,
newest first, as a readable timeline: who (name and role at the time), what
(the action, such as `results.publish`), on which record, the values before
and after, the reason and when. Row-level security keeps each school to its
own events, including what the super admin did to it. Filters: the area (the
part of the action before the dot, such as `results`), an exact action, the
person, the record, and a date range; pages of up to 200 events. The super
admin's platform-wide log is `/platform/audit-log`.
"""

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.core.dependencies import DbSession, Principal, found, require
from app.core.schemas import ApiModel

router = APIRouter(prefix="/school", tags=["audit"])

Auditors = Annotated[Principal, Depends(require("audit.view"))]
Word = Annotated[str | None, Query(max_length=60, pattern=r"^[a-z_.]+$")]


class TimelineEvent(ApiModel):
    id: str
    created_at: dt.datetime
    actor_id: str | None
    actor_name: str | None
    actor_role: str
    action: str
    target_table: str | None
    target_id: str | None
    old_values: dict[str, object] | None
    new_values: dict[str, object] | None
    reason: str | None
    revision: int | None


class Timeline(ApiModel):
    events: list[TimelineEvent]
    has_more: bool


@router.get("/audit", response_model=Timeline)
def timeline(
    who: Auditors,
    session: DbSession,
    area: Word = None,
    action: Word = None,
    actor_id: uuid.UUID | None = None,
    target_table: Word = None,
    target_id: uuid.UUID | None = None,
    since: dt.date | None = None,
    until: dt.date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
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
