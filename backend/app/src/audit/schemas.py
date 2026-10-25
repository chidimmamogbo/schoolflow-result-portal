"""Requests and responses of the audit routes (D-173)."""

import datetime as dt

from app.core.schemas import ApiModel


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
