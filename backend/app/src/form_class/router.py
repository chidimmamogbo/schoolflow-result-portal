"""The form_class routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import (
    DbSession,
    Principal,
    require,
)
from app.src.form_class import services
from app.src.form_class.schemas import (
    AttendanceDays,
    Broadsheet,
    ClassView,
    EntryIn,
    MyClass,
    Preview,
    PupilEntry,
    ReturnBody,
    SectionMove,
)
from app.src.schools.models import Feature

router = APIRouter(tags=["form class"])

Results = Annotated[Principal, Depends(require(feature=Feature.RESULTS))]

Admins = Annotated[Principal, Depends(require("sheets.approve", feature=Feature.RESULTS))]


@router.get("/form-class", response_model=list[MyClass])
def my_classes(who: Results, session: DbSession) -> list[MyClass]:
    return services.my_classes(who=who, session=session)


@router.get("/form-class/{arm_id}", response_model=ClassView)
def get_class(arm_id: uuid.UUID, who: Results, session: DbSession) -> ClassView:
    return services.get_class(arm_id=arm_id, who=who, session=session)


@router.get("/form-class/{arm_id}/broadsheet", response_model=Broadsheet)
def broadsheet(arm_id: uuid.UUID, who: Results, session: DbSession) -> Broadsheet:
    return services.broadsheet(arm_id=arm_id, who=who, session=session)


@router.put("/form-class/{arm_id}/attendance-days", response_model=AttendanceDays)
def set_attendance_days(
    arm_id: uuid.UUID, body: AttendanceDays, who: Results, session: DbSession
) -> AttendanceDays:
    return services.set_attendance_days(arm_id=arm_id, body=body, who=who, session=session)


@router.put("/form-class/{arm_id}/students/{enrolment_id}/entry", response_model=PupilEntry)
def save_entry(
    arm_id: uuid.UUID, enrolment_id: uuid.UUID, body: EntryIn, who: Results, session: DbSession
) -> PupilEntry:
    return services.save_entry(
        arm_id=arm_id, enrolment_id=enrolment_id, body=body, who=who, session=session
    )


@router.get("/form-class/{arm_id}/students/{enrolment_id}/preview", response_model=Preview)
def preview(
    arm_id: uuid.UUID, enrolment_id: uuid.UUID, who: Results, session: DbSession
) -> Preview:
    return services.preview(arm_id=arm_id, enrolment_id=enrolment_id, who=who, session=session)


@router.post("/form-class/{arm_id}/sections/submit", response_model=SectionMove)
def submit_sections(arm_id: uuid.UUID, who: Results, session: DbSession) -> SectionMove:
    return services.submit_sections(arm_id=arm_id, who=who, session=session)


@router.post("/school/classes/{arm_id}/sections/return", response_model=SectionMove)
def return_sections(
    arm_id: uuid.UUID, body: ReturnBody, who: Admins, session: DbSession
) -> SectionMove:
    return services.return_sections(arm_id=arm_id, body=body, who=who, session=session)
