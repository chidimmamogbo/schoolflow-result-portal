"""The notice board routes: each takes the request and calls the service (D-173, D-175).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.dependencies import DbSession, Principal, require
from app.src.notices import services
from app.src.notices.schemas import (
    Board,
    EditNotice,
    NewNotice,
    SchoolNotice,
    SchoolNotices,
    Unread,
)
from app.src.schools.models import Feature

# Readers: every school's own switch is checked inside, so one school's
# board being off never hides another school's notices from a parent.
router = APIRouter(prefix="/notices", tags=["notices"])
school_router = APIRouter(prefix="/school/notices", tags=["notices"])

Readers = Annotated[Principal, Depends(require("notices.read"))]
Posters = Annotated[Principal, Depends(require("notices.post", feature=Feature.NOTICE_BOARD))]


@router.get("", response_model=Board)
def board(who: Readers, session: DbSession) -> Board:
    return services.board(session, who)


@router.get("/unread-count", response_model=Unread)
def unread_count(who: Readers, session: DbSession) -> Unread:
    return services.unread(session, who)


@router.post("/{notice_id}/read", status_code=204, response_class=Response)
def mark_read(notice_id: uuid.UUID, who: Readers, session: DbSession) -> Response:
    services.mark_read(session, who, notice_id)
    return Response(status_code=204)


@school_router.get("", response_model=SchoolNotices)
def school_notices(_: Posters, session: DbSession) -> SchoolNotices:
    return services.list_school_notices(session)


@school_router.post("", status_code=201, response_model=SchoolNotice)
def post_notice(body: NewNotice, who: Posters, session: DbSession) -> SchoolNotice:
    return services.post_notice(session, who, body)


@school_router.patch("/{notice_id}", response_model=SchoolNotice)
def edit_notice(
    notice_id: uuid.UUID, body: EditNotice, who: Posters, session: DbSession
) -> SchoolNotice:
    return services.edit_notice(session, who, notice_id, body)


@school_router.post("/{notice_id}/archive", response_model=SchoolNotice)
def archive_notice(notice_id: uuid.UUID, who: Posters, session: DbSession) -> SchoolNotice:
    return services.archive_notice(session, who, notice_id)
