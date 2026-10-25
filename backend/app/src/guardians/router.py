"""The guardians routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession, Principal, require
from app.src.guardians import services
from app.src.guardians.schemas import (
    Accepted,
    EditGuardian,
    GuardianCreated,
    GuardianRow,
    LinkRequestRow,
    NewGuardian,
    WardLink,
)
from app.src.platform_admin.schemas import Detail

router = APIRouter(prefix="/school", tags=["school"])

Member = Annotated[Principal, Depends(require())]

Admin = Annotated[Principal, Depends(require("guardian_links.manage"))]


# --- routes -----------------------------------------------------------------------------
@router.get("/guardians", response_model=list[GuardianRow])
def list_guardians(_: Member, session: DbSession) -> list[GuardianRow]:
    return services.list_guardians(_=_, session=session)


@router.post("/guardians", status_code=201, response_model=GuardianCreated)
def create_guardian(body: NewGuardian, who: Admin, session: DbSession) -> GuardianCreated:
    return services.create_guardian(body=body, who=who, session=session)


@router.patch("/guardians/{guardian_id}", response_model=GuardianRow)
def edit_guardian(
    guardian_id: uuid.UUID, body: EditGuardian, who: Admin, session: DbSession
) -> GuardianRow:
    return services.edit_guardian(guardian_id=guardian_id, body=body, who=who, session=session)


@router.post("/guardians/{guardian_id}/wards", status_code=201, response_model=Detail)
def add_ward(guardian_id: uuid.UUID, body: WardLink, who: Admin, session: DbSession) -> Detail:
    return services.add_ward(guardian_id=guardian_id, body=body, who=who, session=session)


@router.delete("/guardians/{guardian_id}/wards/{student_id}", status_code=204)
def remove_ward(
    guardian_id: uuid.UUID, student_id: uuid.UUID, who: Admin, session: DbSession
) -> None:
    return services.remove_ward(
        guardian_id=guardian_id, student_id=student_id, who=who, session=session
    )


@router.post("/guardians/{guardian_id}/link-request/resend", status_code=202, response_model=Detail)
def resend_link_request(guardian_id: uuid.UUID, who: Admin, session: DbSession) -> Detail:
    return services.resend_link_request(guardian_id=guardian_id, who=who, session=session)


@router.delete("/guardians/{guardian_id}/link-request", status_code=204)
def cancel_link_request(guardian_id: uuid.UUID, who: Admin, session: DbSession) -> None:
    return services.cancel_link_request(guardian_id=guardian_id, who=who, session=session)


@router.post("/guardians/{guardian_id}/pause", status_code=204)
def pause_link(guardian_id: uuid.UUID, who: Admin, session: DbSession) -> None:
    return services.pause_link(guardian_id=guardian_id, who=who, session=session)


@router.post("/guardians/{guardian_id}/resume", status_code=204)
def resume_link(guardian_id: uuid.UUID, who: Admin, session: DbSession) -> None:
    return services.resume_link(guardian_id=guardian_id, who=who, session=session)


@router.delete("/guardians/{guardian_id}/login", status_code=204)
def remove_link(guardian_id: uuid.UUID, who: Admin, session: DbSession) -> None:
    return services.remove_link(guardian_id=guardian_id, who=who, session=session)


# --- parent_router ----------------------------------------------------------------------
parent_router = APIRouter(prefix="/me", tags=["me"])

SignedIn = Annotated[Principal, Depends(require())]


@parent_router.get("/link-requests", response_model=list[LinkRequestRow])
def my_link_requests(_: SignedIn, session: DbSession) -> list[LinkRequestRow]:
    return services.my_link_requests(_=_, session=session)


@parent_router.post("/link-requests/{request_id}/accept", response_model=Accepted)
def accept(request_id: uuid.UUID, _: SignedIn, session: DbSession) -> Accepted:
    return services.accept(request_id=request_id, _=_, session=session)


@parent_router.post("/link-requests/{request_id}/decline", status_code=204)
def decline(request_id: uuid.UUID, _: SignedIn, session: DbSession) -> None:
    return services.decline(request_id=request_id, _=_, session=session)
