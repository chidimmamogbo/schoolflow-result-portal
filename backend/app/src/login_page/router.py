"""The login page routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.dependencies import DbSession, Principal, require
from app.platform.storage import Storage
from app.src.login_page import services
from app.src.login_page.schemas import LoginPage, LoginPageChange
from app.src.platform_admin.dependencies import PlatformDb

router = APIRouter(tags=["login page"])

Admin = Annotated[Principal, Depends(require("school.settings"))]

Manage = Annotated[Principal, Depends(require("schools.manage"))]


@router.get("/school/login-page", response_model=LoginPage)
def get_page(who: Admin, session: DbSession) -> LoginPage:
    return services.get_page(who=who, session=session)


@router.put("/school/login-page", response_model=LoginPage)
def edit_page(body: LoginPageChange, who: Admin, session: DbSession) -> LoginPage:
    return services.edit_page(body=body, who=who, session=session)


@router.post("/school/login-page/photo", response_model=LoginPage)
def upload_photo(
    file: Annotated[UploadFile, File()], who: Admin, session: DbSession, storage: Storage
) -> LoginPage:
    return services.upload_photo(file=file, who=who, session=session, storage=storage)


@router.get("/platform/schools/{school_id}/login-page", response_model=LoginPage)
def platform_get_page(school_id: uuid.UUID, _: Manage, db: PlatformDb) -> LoginPage:
    return services.platform_get_page(school_id=school_id, db=db)


@router.put("/platform/schools/{school_id}/login-page", response_model=LoginPage)
def platform_edit_page(
    school_id: uuid.UUID, body: LoginPageChange, _: Manage, db: PlatformDb
) -> LoginPage:
    return services.platform_edit_page(school_id=school_id, body=body, db=db)
