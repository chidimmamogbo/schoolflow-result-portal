"""The accounts routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession, Principal, require
from app.src.accounts import services
from app.src.accounts.schemas import Admins, CreatedAdmin, NewAdmin
from app.src.platform_admin import settings_model as settings_model
from app.src.platform_admin.schemas import Detail, ResetLink, TemporaryPassword

router = APIRouter(prefix="/school", tags=["school"])

Member = Annotated[Principal, Depends(require())]

AddAdmins = Annotated[Principal, Depends(require("school_admins.create"))]

RemoveAdmins = Annotated[Principal, Depends(require("school_admins.remove"))]

Support = Annotated[Principal, Depends(require("users.reset_login"))]


@router.get("/admins", response_model=Admins)
def list_admins(who: Member, session: DbSession) -> Admins:
    return services.list_admins(who=who, session=session)


@router.post("/admins", status_code=201, response_model=CreatedAdmin)
def add_admin(body: NewAdmin, who: AddAdmins, session: DbSession) -> CreatedAdmin:
    return services.add_admin(body=body, who=who, session=session)


@router.delete("/admins/{user_id}", status_code=204)
def remove_admin(user_id: uuid.UUID, who: RemoveAdmins, session: DbSession) -> None:
    return services.remove_admin(user_id=user_id, who=who, session=session)


@router.post("/people/{user_id}/resend-activation", status_code=202, response_model=Detail)
def resend_activation(user_id: uuid.UUID, who: Support, session: DbSession) -> Detail:
    return services.resend_activation(user_id=user_id, who=who, session=session)


@router.post("/people/{user_id}/send-reset-link", status_code=202, response_model=Detail)
def send_reset_link(
    user_id: uuid.UUID, body: ResetLink, who: Support, session: DbSession
) -> Detail:
    return services.send_reset_link(user_id=user_id, body=body, who=who, session=session)


@router.post(
    "/people/{user_id}/temporary-password", status_code=201, response_model=TemporaryPassword
)
def temporary_password(user_id: uuid.UUID, who: Support, session: DbSession) -> TemporaryPassword:
    return services.temporary_password(user_id=user_id, who=who, session=session)


@router.post("/people/{user_id}/sign-out-all", status_code=204)
def sign_out_all(user_id: uuid.UUID, who: Support, session: DbSession) -> None:
    return services.sign_out_all(user_id=user_id, who=who, session=session)


@router.post("/people/{user_id}/deactivate", status_code=204)
def deactivate(user_id: uuid.UUID, who: Support, session: DbSession) -> None:
    return services.deactivate(user_id=user_id, who=who, session=session)


@router.post("/people/{user_id}/reactivate", status_code=204)
def reactivate(user_id: uuid.UUID, who: Support, session: DbSession) -> None:
    return services.reactivate(user_id=user_id, who=who, session=session)
