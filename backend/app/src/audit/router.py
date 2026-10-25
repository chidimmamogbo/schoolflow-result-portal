"""The audit routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DbSession, Principal, require
from app.src.audit import services
from app.src.audit.schemas import Timeline
from app.src.audit.services import Word

router = APIRouter(prefix="/school", tags=["audit"])

Auditors = Annotated[Principal, Depends(require("audit.view"))]


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
    return services.timeline(
        who=who,
        session=session,
        area=area,
        action=action,
        actor_id=actor_id,
        target_table=target_table,
        target_id=target_id,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
