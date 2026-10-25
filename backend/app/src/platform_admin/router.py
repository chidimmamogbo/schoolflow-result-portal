"""The platform_admin routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import Principal, require
from app.src.platform_admin import services
from app.src.platform_admin import settings_model as settings_model
from app.src.platform_admin.dependencies import PlatformDb
from app.src.platform_admin.schemas import (
    AdminRow,
    AuditRow,
    Available,
    ChangeCode,
    Code,
    Created,
    CreateSchool,
    Detail,
    EditSchool,
    EmailRow,
    Features,
    LevelsChange,
    LevelsResult,
    Limit,
    NewEmail,
    PaymentRow,
    ResetLink,
    SchoolDetail,
    SchoolRow,
    Suspend,
    TemporaryPassword,
    Usage,
    Username,
)

router = APIRouter(prefix="/platform", tags=["platform"])

Manage = Annotated[Principal, Depends(require("schools.manage"))]

ToggleFeatures = Annotated[Principal, Depends(require("features.toggle"))]

ToggleLevels = Annotated[Principal, Depends(require("report_card_levels.toggle"))]

ResetLogin = Annotated[Principal, Depends(require("school_admins.reset_login"))]

SignOutAll = Annotated[Principal, Depends(require("school_admins.sign_out_all"))]

Settings = Annotated[Principal, Depends(require("platform.settings"))]

AuditLog = Annotated[Principal, Depends(require("platform.audit"))]

EmailLog = Annotated[Principal, Depends(require("platform.email_log"))]

PaymentsLog = Annotated[Principal, Depends(require("platform.payments_log"))]


# --- schools -------------------------------------------------------------------------------
@router.get("/schools/check-code", response_model=Available)
def check_code(code: Annotated[Code, Query()], _: Manage, db: PlatformDb) -> Available:
    return services.check_code(code=code, _=_, db=db)


@router.get("/usernames/check", response_model=Available)
def check_username(username: Annotated[Username, Query()], _: Manage, db: PlatformDb) -> Available:
    return services.check_username(username=username, _=_, db=db)


@router.post("/schools", status_code=201, response_model=Created)
def create_school(body: CreateSchool, _: Manage, db: PlatformDb) -> Created:
    return services.create_school(body=body, _=_, db=db)


@router.get("/schools", response_model=list[SchoolRow])
def list_schools(
    _: Manage,
    db: PlatformDb,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status: Annotated[str | None, Query(pattern="^(active|suspended)$")] = None,
) -> list[SchoolRow]:
    return services.list_schools(_=_, db=db, q=q, status=status)


@router.get("/schools/{school_id}", response_model=SchoolDetail)
def get_school(school_id: uuid.UUID, _: Manage, db: PlatformDb) -> SchoolDetail:
    return services.get_school(school_id=school_id, _=_, db=db)


@router.patch("/schools/{school_id}", response_model=SchoolDetail)
def edit_school(school_id: uuid.UUID, body: EditSchool, _: Manage, db: PlatformDb) -> SchoolDetail:
    return services.edit_school(school_id=school_id, body=body, _=_, db=db)


@router.post("/schools/{school_id}/change-code", response_model=SchoolRow)
def change_code(school_id: uuid.UUID, body: ChangeCode, _: Manage, db: PlatformDb) -> SchoolRow:
    return services.change_code(school_id=school_id, body=body, _=_, db=db)


@router.post("/schools/{school_id}/suspend", status_code=204)
def suspend(school_id: uuid.UUID, body: Suspend, _: Manage, db: PlatformDb) -> None:
    return services.suspend(school_id=school_id, body=body, _=_, db=db)


@router.post("/schools/{school_id}/reactivate", status_code=204)
def reactivate(school_id: uuid.UUID, _: Manage, db: PlatformDb) -> None:
    return services.reactivate(school_id=school_id, _=_, db=db)


@router.post("/schools/{school_id}/resend-setup-email", status_code=202, response_model=Detail)
def resend_setup_email(school_id: uuid.UUID, _: Manage, db: PlatformDb) -> Detail:
    return services.resend_setup_email(school_id=school_id, _=_, db=db)


@router.get("/schools/{school_id}/usage", response_model=Usage)
def usage(school_id: uuid.UUID, _: Manage, db: PlatformDb) -> Usage:
    return services.usage(school_id=school_id, _=_, db=db)


@router.get("/schools/{school_id}/activity", response_model=list[AuditRow])
def activity(school_id: uuid.UUID, _: Manage, db: PlatformDb, limit: Limit = 50) -> list[AuditRow]:
    return services.activity(school_id=school_id, _=_, db=db, limit=limit)


# --- features and report card levels ----------------------------------------------------
@router.put("/schools/{school_id}/features", response_model=Features)
def set_features(
    school_id: uuid.UUID, body: Features, _: ToggleFeatures, db: PlatformDb
) -> Features:
    return services.set_features(school_id=school_id, body=body, _=_, db=db)


@router.put("/schools/{school_id}/levels", response_model=LevelsResult)
def set_levels(
    school_id: uuid.UUID, body: LevelsChange, _: ToggleLevels, db: PlatformDb
) -> LevelsResult:
    return services.set_levels(school_id=school_id, body=body, _=_, db=db)


@router.get("/schools/{school_id}/admins", response_model=list[AdminRow])
def list_admins(school_id: uuid.UUID, _: Manage, db: PlatformDb) -> list[AdminRow]:
    return services.list_admins(school_id=school_id, _=_, db=db)


@router.post(
    "/schools/{school_id}/admins/{user_id}/resend-activation",
    status_code=202,
    response_model=Detail,
)
def resend_activation(
    school_id: uuid.UUID, user_id: uuid.UUID, _: ResetLogin, db: PlatformDb
) -> Detail:
    return services.resend_activation(school_id=school_id, user_id=user_id, _=_, db=db)


@router.patch("/schools/{school_id}/admins/{user_id}/email", response_model=AdminRow)
def change_admin_email(
    school_id: uuid.UUID, user_id: uuid.UUID, body: NewEmail, _: ResetLogin, db: PlatformDb
) -> AdminRow:
    return services.change_admin_email(school_id=school_id, user_id=user_id, body=body, _=_, db=db)


@router.post(
    "/schools/{school_id}/admins/{user_id}/send-reset-link", status_code=202, response_model=Detail
)
def send_reset_link(
    school_id: uuid.UUID, user_id: uuid.UUID, body: ResetLink, _: ResetLogin, db: PlatformDb
) -> Detail:
    return services.send_reset_link(school_id=school_id, user_id=user_id, body=body, _=_, db=db)


@router.post(
    "/schools/{school_id}/admins/{user_id}/temporary-password",
    status_code=201,
    response_model=TemporaryPassword,
)
def temporary_password(
    school_id: uuid.UUID, user_id: uuid.UUID, _: ResetLogin, db: PlatformDb
) -> TemporaryPassword:
    return services.temporary_password(school_id=school_id, user_id=user_id, _=_, db=db)


@router.post("/schools/{school_id}/admins/{user_id}/sign-out-all", status_code=204)
def sign_out_all(school_id: uuid.UUID, user_id: uuid.UUID, _: SignOutAll, db: PlatformDb) -> None:
    return services.sign_out_all(school_id=school_id, user_id=user_id, _=_, db=db)


@router.post("/schools/{school_id}/admins/{user_id}/deactivate", status_code=204)
def deactivate(school_id: uuid.UUID, user_id: uuid.UUID, _: ResetLogin, db: PlatformDb) -> None:
    return services.deactivate(school_id=school_id, user_id=user_id, _=_, db=db)


@router.post("/schools/{school_id}/admins/{user_id}/reactivate", status_code=204)
def reactivate_admin(
    school_id: uuid.UUID, user_id: uuid.UUID, _: ResetLogin, db: PlatformDb
) -> None:
    return services.reactivate_admin(school_id=school_id, user_id=user_id, _=_, db=db)


@router.post("/schools/{school_id}/admins/{user_id}/make-primary", status_code=204)
def make_primary(school_id: uuid.UUID, user_id: uuid.UUID, _: Manage, db: PlatformDb) -> None:
    return services.make_primary(school_id=school_id, user_id=user_id, _=_, db=db)


# --- platform settings and logs -----------------------------------------------------------
@router.get("/settings", response_model=settings_model.PlatformSettings)
def get_settings_page(_: Settings, db: PlatformDb) -> settings_model.PlatformSettings:
    return services.get_settings_page(_=_, db=db)


@router.patch("/settings", response_model=settings_model.PlatformSettings)
def change_settings(
    body: dict[str, Any], principal: Settings, db: PlatformDb
) -> settings_model.PlatformSettings:
    return services.change_settings(body=body, principal=principal, db=db)


@router.get("/audit-log", response_model=list[AuditRow])
def audit_log(
    _: AuditLog,
    db: PlatformDb,
    school_id: uuid.UUID | None = None,
    action: Annotated[str | None, Query(max_length=60)] = None,
    actor_id: uuid.UUID | None = None,
    limit: Limit = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditRow]:
    return services.audit_log(
        _=_,
        db=db,
        school_id=school_id,
        action=action,
        actor_id=actor_id,
        limit=limit,
        offset=offset,
    )


@router.get("/email-log", response_model=list[EmailRow])
def email_log(
    _: EmailLog,
    db: PlatformDb,
    school_id: uuid.UUID | None = None,
    type: Annotated[str | None, Query(max_length=40)] = None,
    limit: Limit = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[EmailRow]:
    return services.email_log(
        _=_, db=db, school_id=school_id, type=type, limit=limit, offset=offset
    )


@router.get("/payments", response_model=list[PaymentRow])
def payments(
    _: PaymentsLog,
    db: PlatformDb,
    school_id: uuid.UUID | None = None,
    limit: Limit = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PaymentRow]:
    return services.payments(_=_, db=db, school_id=school_id, limit=limit, offset=offset)
