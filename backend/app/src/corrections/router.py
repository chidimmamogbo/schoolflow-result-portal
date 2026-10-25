"""The corrections routes: each takes the request and calls the service (D-173, D-174).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile

from app.core.dependencies import DbSession, Principal, require
from app.platform.storage import Storage
from app.src.corrections import services
from app.src.corrections.schemas import (
    Attachment,
    Move,
    NewRequest,
    RequestDetail,
    Requests,
    Status,
)
from app.src.schools.models import Feature

router = APIRouter(prefix="/corrections", tags=["corrections"])

Queue = Annotated[Principal, Depends(require(feature=Feature.CORRECTION_QUEUE))]
Raisers = Annotated[
    Principal, Depends(require("corrections.create", feature=Feature.CORRECTION_QUEUE))
]


@router.get("", response_model=Requests)
def list_requests(who: Queue, session: DbSession, status: Status | None = None) -> Requests:
    return services.list_requests(session, who, status)


@router.post("", status_code=201, response_model=RequestDetail)
def raise_request(body: NewRequest, who: Raisers, session: DbSession) -> RequestDetail:
    return services.raise_request(session, who, body)


@router.get("/{request_id}", response_model=RequestDetail)
def get_request(request_id: uuid.UUID, who: Queue, session: DbSession) -> RequestDetail:
    return services.detail(session, who, request_id)


@router.post("/{request_id}/move", response_model=RequestDetail)
def move_request(
    request_id: uuid.UUID, body: Move, who: Queue, session: DbSession
) -> RequestDetail:
    return services.move_request(session, who, request_id, body)


@router.post("/{request_id}/attachment", status_code=201, response_model=Attachment)
def add_attachment(
    request_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    who: Raisers,
    session: DbSession,
    storage: Storage,
) -> Attachment:
    return services.add_attachment(session, who, request_id, file, storage)


@router.get("/{request_id}/attachment", response_class=Response)
def get_attachment(
    request_id: uuid.UUID, who: Queue, session: DbSession, storage: Storage
) -> Response:
    content, content_type, name = services.attachment_file(session, who, request_id, storage)
    return Response(
        content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "private, no-store",
        },
    )
