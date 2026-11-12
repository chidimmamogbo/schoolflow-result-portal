"""The school's email statuses (CHANGE 2026-11-12 B).

School admins see their own school's outbox, newest first: type, address,
status, tries and times. Row-level security keeps every other school's rows
out, and only the status columns are readable by the app (migration 17).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.core.dependencies import DbSession, Principal, require
from app.src.emails.schemas import SchoolEmailRow

router = APIRouter(prefix="/school", tags=["emails"])

Admin = Annotated[Principal, Depends(require("school.settings"))]


@router.get("/emails", response_model=list[SchoolEmailRow])
def school_emails(
    _: Admin,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SchoolEmailRow]:
    rows = session.execute(
        text(
            "select id, type, to_address, status, attempts, created_at, sent_at"
            " from email_outbox order by created_at desc, id limit :limit offset :offset"
        ),
        {"limit": limit, "offset": offset},
    )
    return [
        SchoolEmailRow(
            id=str(r.id),
            type=r.type,
            to_address=r.to_address,
            status=r.status,
            attempts=r.attempts,
            created_at=r.created_at,
            sent_at=r.sent_at,
        )
        for r in rows
    ]
