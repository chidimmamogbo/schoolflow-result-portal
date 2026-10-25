"""The files routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile

from app.core.dependencies import DbSession, Principal, require
from app.platform.storage import Storage
from app.src.files import services
from app.src.files.schemas import StoredFileOut

router = APIRouter(tags=["files"])

Admin = Annotated[Principal, Depends(require("school.settings"))]

Member = Annotated[Principal, Depends(require())]


@router.post("/school/files", status_code=201, response_model=StoredFileOut)
def upload_school_image(
    purpose: Annotated[Literal["logo", "signature", "stamp"], Form()],
    file: Annotated[UploadFile, File()],
    who: Admin,
    session: DbSession,
    storage: Storage,
) -> StoredFileOut:
    return services.upload_school_image(
        purpose=purpose, file=file, who=who, session=session, storage=storage
    )


@router.get("/files/{file_id}")
def download(
    file_id: uuid.UUID, request: Request, _: Member, session: DbSession, storage: Storage
) -> Response:
    return services.download(
        file_id=file_id, request=request, _=_, session=session, storage=storage
    )
