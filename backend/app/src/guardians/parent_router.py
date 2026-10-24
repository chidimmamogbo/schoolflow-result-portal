"""A parent answers schools' link requests (D-138, D-140; AT-31.4, AT-31.5, AC03.8).

The requests belong to the schools that sent them, so the signed-in parent
reads and answers them through the narrow owner-run functions of migration
24, which match the request's email with the parent's own verified email.
Anyone else, a teacher or a pupil included, sees nothing and gets "not
found". Accepting adds a parent link to that school at once.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.core.dependencies import DbSession, Principal, found, require
from app.core.schemas import ApiModel

router = APIRouter(prefix="/me", tags=["me"])

SignedIn = Annotated[Principal, Depends(require())]


class LinkRequestRow(ApiModel):
    id: str
    school_id: str
    school_name: str
    school_code: str
    guardian_name: str
    created_at: datetime
    expires_at: datetime


class Accepted(ApiModel):
    school_id: str


@router.get("/link-requests", response_model=list[LinkRequestRow])
def my_link_requests(_: SignedIn, session: DbSession) -> list[LinkRequestRow]:
    return [
        LinkRequestRow(
            id=str(r.id),
            school_id=str(r.school_id),
            school_name=r.school_name,
            school_code=r.school_code,
            guardian_name=r.guardian_name,
            created_at=r.created_at,
            expires_at=r.expires_at,
        )
        for r in session.execute(text("select * from my_parent_link_requests()"))
    ]


@router.post("/link-requests/{request_id}/accept", response_model=Accepted)
def accept(request_id: uuid.UUID, _: SignedIn, session: DbSession) -> Accepted:
    school_id = found(
        session.scalar(text("select accept_parent_link_request(:r)"), {"r": request_id})
    )
    return Accepted(school_id=str(school_id))


@router.post("/link-requests/{request_id}/decline", status_code=204)
def decline(request_id: uuid.UUID, _: SignedIn, session: DbSession) -> None:
    if not session.scalar(text("select decline_parent_link_request(:r)"), {"r": request_id}):
        found(None)
