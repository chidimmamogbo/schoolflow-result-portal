"""The schools routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession, Principal, require
from app.src.schools import services
from app.src.schools.schemas import (
    EditSettings,
    LevelChange,
    LevelName,
    LevelResult,
    SchoolSettings,
)

router = APIRouter(prefix="/school", tags=["school"])

Member = Annotated[Principal, Depends(require())]

Admin = Annotated[Principal, Depends(require("school.settings"))]


@router.get("", response_model=SchoolSettings)
def get_settings(who: Member, session: DbSession) -> SchoolSettings:
    return services.get_settings(who=who, session=session)


@router.patch("", response_model=SchoolSettings)
def edit_settings(body: EditSettings, who: Admin, session: DbSession) -> SchoolSettings:
    return services.edit_settings(body=body, who=who, session=session)


@router.put("/levels/{level}", response_model=LevelResult)
def change_level(
    level: LevelName, body: LevelChange, who: Admin, session: DbSession
) -> LevelResult:
    return services.change_level(level=level, body=body, who=who, session=session)
