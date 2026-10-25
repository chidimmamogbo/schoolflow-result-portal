"""The staff routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import DbSession, Principal, require
from app.src.accounts.schemas import CreatedAdmin
from app.src.staff import services
from app.src.staff.schemas import (
    AssignmentRow,
    AssistantRow,
    EditStaff,
    NewAssignment,
    NewAssistant,
    NewScope,
    NewStaff,
    ScopeRow,
    StaffRow,
)

router = APIRouter(prefix="/school", tags=["school"])

Member = Annotated[Principal, Depends(require())]

CreateUsers = Annotated[Principal, Depends(require("users.create"))]

Assign = Annotated[Principal, Depends(require("assignments.manage"))]


@router.get("/staff", response_model=list[StaffRow])
def list_staff(
    _: Member,
    session: DbSession,
    role: Annotated[Literal["teacher", "reviewer"] | None, Query()] = None,
) -> list[StaffRow]:
    return services.list_staff(_=_, session=session, role=role)


@router.post("/staff", status_code=201, response_model=CreatedAdmin)
def create_staff(body: NewStaff, who: CreateUsers, session: DbSession) -> CreatedAdmin:
    return services.create_staff(body=body, who=who, session=session)


@router.patch("/staff/{user_id}", response_model=StaffRow)
def edit_staff(
    user_id: uuid.UUID, body: EditStaff, who: CreateUsers, session: DbSession
) -> StaffRow:
    return services.edit_staff(user_id=user_id, body=body, who=who, session=session)


@router.get("/assignments", response_model=list[AssignmentRow])
def list_assignments(
    _: Member,
    session: DbSession,
    arm_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
) -> list[AssignmentRow]:
    return services.list_assignments(_=_, session=session, arm_id=arm_id, teacher_id=teacher_id)


@router.post("/assignments", status_code=201, response_model=AssignmentRow)
def create_assignment(body: NewAssignment, who: Assign, session: DbSession) -> AssignmentRow:
    return services.create_assignment(body=body, who=who, session=session)


@router.delete("/assignments/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: uuid.UUID, who: Assign, session: DbSession) -> None:
    return services.delete_assignment(assignment_id=assignment_id, who=who, session=session)


# --- class teacher assistants (F06 rule 3) -------------------------------------------------
@router.get("/arms/{arm_id}/assistants", response_model=list[AssistantRow])
def list_assistants(arm_id: uuid.UUID, _: Member, session: DbSession) -> list[AssistantRow]:
    return services.list_assistants(arm_id=arm_id, _=_, session=session)


@router.post("/arms/{arm_id}/assistants", status_code=201, response_model=AssistantRow)
def add_assistant(
    arm_id: uuid.UUID, body: NewAssistant, who: Assign, session: DbSession
) -> AssistantRow:
    return services.add_assistant(arm_id=arm_id, body=body, who=who, session=session)


@router.delete("/arms/{arm_id}/assistants/{user_id}", status_code=204)
def remove_assistant(
    arm_id: uuid.UUID, user_id: uuid.UUID, who: Assign, session: DbSession
) -> None:
    return services.remove_assistant(arm_id=arm_id, user_id=user_id, who=who, session=session)


@router.get("/reviewers/{user_id}/scopes", response_model=list[ScopeRow])
def list_scopes(user_id: uuid.UUID, _: Member, session: DbSession) -> list[ScopeRow]:
    return services.list_scopes(user_id=user_id, _=_, session=session)


@router.post("/reviewers/{user_id}/scopes", status_code=201, response_model=ScopeRow)
def add_scope(user_id: uuid.UUID, body: NewScope, who: Assign, session: DbSession) -> ScopeRow:
    return services.add_scope(user_id=user_id, body=body, who=who, session=session)


@router.delete("/reviewer-scopes/{scope_id}", status_code=204)
def delete_scope(scope_id: uuid.UUID, who: Assign, session: DbSession) -> None:
    return services.delete_scope(scope_id=scope_id, who=who, session=session)
