"""The structure routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession, Principal, require
from app.src.structure import services
from app.src.structure.schemas import (
    ArmRow,
    ArmSubjects,
    ClassRow,
    DepartmentRow,
    EditSubject,
    EditTerm,
    NewArm,
    NewClass,
    NewDepartment,
    NewSession,
    NewTerm,
    Rename,
    SessionRow,
    SubjectFields,
    SubjectRow,
    TermRow,
)

router = APIRouter(prefix="/school", tags=["school"])

Member = Annotated[Principal, Depends(require())]

Admin = Annotated[Principal, Depends(require("school.settings"))]


@router.get("/sessions", response_model=list[SessionRow])
def list_sessions(_: Member, session: DbSession) -> list[SessionRow]:
    return services.list_sessions(_=_, session=session)


@router.post("/sessions", status_code=201, response_model=SessionRow)
def create_session(body: NewSession, who: Admin, session: DbSession) -> SessionRow:
    return services.create_session(body=body, who=who, session=session)


@router.post("/sessions/{session_id}/terms", status_code=201, response_model=TermRow)
def create_term(session_id: str, body: NewTerm, who: Admin, session: DbSession) -> TermRow:
    return services.create_term(session_id=session_id, body=body, who=who, session=session)


@router.patch("/terms/{term_id}", response_model=TermRow)
def edit_term(term_id: str, body: EditTerm, who: Admin, session: DbSession) -> TermRow:
    return services.edit_term(term_id=term_id, body=body, who=who, session=session)


@router.post("/terms/{term_id}/activate", response_model=TermRow)
def activate_term(term_id: str, who: Admin, session: DbSession) -> TermRow:
    return services.activate_term(term_id=term_id, who=who, session=session)


# --- classes and arms -----------------------------------------------------------------------
@router.get("/classes", response_model=list[ClassRow])
def list_classes(_: Member, session: DbSession) -> list[ClassRow]:
    return services.list_classes(_=_, session=session)


@router.post("/classes", status_code=201, response_model=ClassRow)
def create_class(body: NewClass, who: Admin, session: DbSession) -> ClassRow:
    return services.create_class(body=body, who=who, session=session)


@router.patch("/classes/{class_id}", response_model=ClassRow)
def rename_class(class_id: str, body: Rename, who: Admin, session: DbSession) -> ClassRow:
    return services.rename_class(class_id=class_id, body=body, who=who, session=session)


@router.delete("/classes/{class_id}", status_code=204)
def delete_class(class_id: str, who: Admin, session: DbSession) -> None:
    return services.delete_class(class_id=class_id, who=who, session=session)


@router.post("/classes/{class_id}/arms", status_code=201, response_model=ArmRow)
def create_arm(class_id: str, body: NewArm, who: Admin, session: DbSession) -> ArmRow:
    return services.create_arm(class_id=class_id, body=body, who=who, session=session)


@router.patch("/arms/{arm_id}", response_model=ArmRow)
def rename_arm(arm_id: str, body: NewArm, who: Admin, session: DbSession) -> ArmRow:
    return services.rename_arm(arm_id=arm_id, body=body, who=who, session=session)


@router.delete("/arms/{arm_id}", status_code=204)
def delete_arm(arm_id: str, who: Admin, session: DbSession) -> None:
    return services.delete_arm(arm_id=arm_id, who=who, session=session)


@router.put("/arms/{arm_id}/subjects", response_model=list[SubjectRow])
def set_arm_subjects(
    arm_id: str, body: ArmSubjects, who: Admin, session: DbSession
) -> list[SubjectRow]:
    return services.set_arm_subjects(arm_id=arm_id, body=body, who=who, session=session)


# --- departments and subjects ----------------------------------------------------------------
@router.get("/departments", response_model=list[DepartmentRow])
def list_departments(_: Member, session: DbSession) -> list[DepartmentRow]:
    return services.list_departments(_=_, session=session)


@router.post("/departments", status_code=201, response_model=DepartmentRow)
def create_department(body: NewDepartment, who: Admin, session: DbSession) -> DepartmentRow:
    return services.create_department(body=body, who=who, session=session)


@router.patch("/departments/{department_id}", response_model=DepartmentRow)
def rename_department(
    department_id: str, body: NewDepartment, who: Admin, session: DbSession
) -> DepartmentRow:
    return services.rename_department(
        department_id=department_id, body=body, who=who, session=session
    )


@router.delete("/departments/{department_id}", status_code=204)
def delete_department(department_id: str, who: Admin, session: DbSession) -> None:
    return services.delete_department(department_id=department_id, who=who, session=session)


@router.get("/subjects", response_model=list[SubjectRow])
def list_subjects(_: Member, session: DbSession) -> list[SubjectRow]:
    return services.list_subjects(_=_, session=session)


@router.post("/subjects", status_code=201, response_model=SubjectRow)
def create_subject(body: SubjectFields, who: Admin, session: DbSession) -> SubjectRow:
    return services.create_subject(body=body, who=who, session=session)


@router.patch("/subjects/{subject_id}", response_model=SubjectRow)
def edit_subject(subject_id: str, body: EditSubject, who: Admin, session: DbSession) -> SubjectRow:
    return services.edit_subject(subject_id=subject_id, body=body, who=who, session=session)


@router.delete("/subjects/{subject_id}", status_code=204)
def delete_subject(subject_id: str, who: Admin, session: DbSession) -> None:
    return services.delete_subject(subject_id=subject_id, who=who, session=session)
