"""The reports routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse

from app.core.dependencies import DbSession, Principal, require
from app.platform.storage import Storage
from app.src.reports import services
from app.src.reports.schemas import TemplateIn, TemplateOut
from app.src.schools.models import Feature
from app.src.schools.schemas import LevelName

router = APIRouter(prefix="/school", tags=["report cards"])

Publishers = Annotated[Principal, Depends(require("results.publish", feature=Feature.RESULTS))]

Designers = Annotated[Principal, Depends(require("report_templates.manage"))]


@router.get("/reports/{report_id}/card.html", response_class=HTMLResponse)
def school_report_card(
    report_id: uuid.UUID, _: Publishers, session: DbSession, storage: Storage
) -> HTMLResponse:
    return services.school_report_card(report_id=report_id, _=_, session=session, storage=storage)


@router.get("/reports/{report_id}/report.pdf", response_class=Response)
def school_report_pdf(
    report_id: uuid.UUID, _: Publishers, session: DbSession, storage: Storage
) -> Response:
    return services.school_report_pdf(report_id=report_id, _=_, session=session, storage=storage)


@router.get("/report-templates/{level}/preview.html", response_class=HTMLResponse)
def preview_template(
    level: LevelName, who: Designers, session: DbSession, storage: Storage
) -> HTMLResponse:
    return services.preview_template(level=level, who=who, session=session, storage=storage)


# --- templates ----------------------------------------------------------------------
templates_router = APIRouter(prefix="/school", tags=["report templates"])

Member = Annotated[Principal, Depends(require())]

Manage = Annotated[Principal, Depends(require("report_templates.manage"))]


@templates_router.get("/report-templates", response_model=list[TemplateOut])
def list_templates(_: Member, session: DbSession) -> list[TemplateOut]:
    return services.list_templates(_=_, session=session)


@templates_router.put("/report-templates/{level}", response_model=TemplateOut)
def save_template(
    level: LevelName, body: TemplateIn, who: Manage, session: DbSession
) -> TemplateOut:
    return services.save_template(level=level, body=body, who=who, session=session)
