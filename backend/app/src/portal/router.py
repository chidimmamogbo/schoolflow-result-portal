"""The portal routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse

from app.core.dependencies import DbSession, Principal, require
from app.platform import pdf as pdf
from app.platform.storage import Storage
from app.src.portal import services
from app.src.portal.schemas import ReportRow, ReportView, SchoolChildren
from app.src.schools.models import Feature

router = APIRouter(prefix="/me", tags=["my children"])

Families = Annotated[Principal, Depends(require("reports.view"))]

Readers = Annotated[Principal, Depends(require("reports.view", feature=Feature.PARENT_PORTAL))]


@router.get("/children", response_model=list[SchoolChildren])
def my_children(who: Families, session: DbSession) -> list[SchoolChildren]:
    return services.my_children(who=who, session=session)


@router.get("/students/{student_id}/reports", response_model=list[ReportRow])
def student_reports(student_id: uuid.UUID, who: Readers, session: DbSession) -> list[ReportRow]:
    return services.student_reports(student_id=student_id, who=who, session=session)


@router.get("/reports/{report_id}", response_model=ReportView)
def report_view(report_id: uuid.UUID, who: Readers, session: DbSession) -> ReportView:
    return services.report_view(report_id=report_id, who=who, session=session)


@router.get("/reports/{report_id}/card.html", response_class=HTMLResponse)
def report_card(
    report_id: uuid.UUID, who: Readers, session: DbSession, storage: Storage
) -> HTMLResponse:
    return services.report_card(report_id=report_id, who=who, session=session, storage=storage)


@router.get("/reports/{report_id}/report.pdf", response_class=Response)
def report_pdf(
    report_id: uuid.UUID, who: Readers, session: DbSession, storage: Storage
) -> Response:
    return services.report_pdf(report_id=report_id, who=who, session=session, storage=storage)
