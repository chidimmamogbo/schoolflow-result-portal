"""The students routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import PlainTextResponse

from app.core.dependencies import DbSession, Principal, require
from app.src.platform_admin.schemas import TemporaryPassword
from app.src.students import services
from app.src.students.schemas import (
    EditPupil,
    Imported,
    ImportPreview,
    Move,
    NewLogin,
    PupilRow,
    PupilSubjects,
    SubjectName,
)
from app.src.students.services import NewPupil

router = APIRouter(prefix="/school", tags=["school"])

Member = Annotated[Principal, Depends(require())]

Admin = Annotated[Principal, Depends(require("users.create"))]


# --- one pupil -----------------------------------------------------------------------------
@router.get("/students", response_model=list[PupilRow])
def list_pupils(
    _: Member,
    session: DbSession,
    q: Annotated[str | None, Query(max_length=60)] = None,
    arm_id: uuid.UUID | None = None,
    status: Annotated[Literal["active", "withdrawn", "graduated"] | None, Query()] = None,
) -> list[PupilRow]:
    return services.list_pupils(_=_, session=session, q=q, arm_id=arm_id, status=status)


@router.post("/students", status_code=201, response_model=PupilRow)
def create_pupil(body: NewPupil, who: Admin, session: DbSession) -> PupilRow:
    return services.create_pupil(body=body, who=who, session=session)


@router.patch("/students/{student_id}", response_model=PupilRow)
def edit_pupil(student_id: uuid.UUID, body: EditPupil, who: Admin, session: DbSession) -> PupilRow:
    return services.edit_pupil(student_id=student_id, body=body, who=who, session=session)


@router.post("/students/{student_id}/move", response_model=PupilRow)
def move_pupil(student_id: uuid.UUID, body: Move, who: Admin, session: DbSession) -> PupilRow:
    return services.move_pupil(student_id=student_id, body=body, who=who, session=session)


@router.put("/students/{student_id}/subjects", response_model=list[SubjectName])
def set_pupil_subjects(
    student_id: uuid.UUID, body: PupilSubjects, who: Admin, session: DbSession
) -> list[SubjectName]:
    return services.set_pupil_subjects(student_id=student_id, body=body, who=who, session=session)


@router.post("/students/{student_id}/login", status_code=201, response_model=TemporaryPassword)
def give_pupil_login(
    student_id: uuid.UUID, body: NewLogin, who: Admin, session: DbSession
) -> TemporaryPassword:
    return services.give_pupil_login(student_id=student_id, body=body, who=who, session=session)


# --- CSV import (AC05.1) ----------------------------------------------------------------
@router.get("/students/import/template", response_class=PlainTextResponse)
def import_template(_: Admin) -> PlainTextResponse:
    return services.import_template(_=_)


@router.post("/students/import", response_model=None)
def import_pupils(
    file: Annotated[UploadFile, File()],
    arm_id: uuid.UUID,
    who: Admin,
    session: DbSession,
    response: Response,
    commit: bool = False,
) -> ImportPreview | Imported:
    return services.import_pupils(
        file=file, arm_id=arm_id, who=who, session=session, response=response, commit=commit
    )
