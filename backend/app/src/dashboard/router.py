"""The dashboard routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import DbSession, Principal, require
from app.src.dashboard import services
from app.src.dashboard.schemas import Reminded, Reminder, SchoolDashboard, StaffDashboard
from app.src.schools.models import Feature

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# No feature on the school dashboard: the billing card stays when Results is off.
SchoolAdmins = Annotated[Principal, Depends(require("sheets.approve"))]
Staff = Annotated[Principal, Depends(require("attention.view", feature=Feature.RESULTS))]
Reminders = Annotated[Principal, Depends(require("sheets.approve", feature=Feature.RESULTS))]


@router.get("/school", response_model=SchoolDashboard)
def school_dashboard(who: SchoolAdmins, session: DbSession) -> SchoolDashboard:
    return services.school_dashboard(who=who, session=session)


@router.get("/staff", response_model=StaffDashboard)
def staff_dashboard(who: Staff, session: DbSession) -> StaffDashboard:
    return services.staff_dashboard(who=who, session=session)


@router.post("/reminders", response_model=Reminded)
def remind(body: Reminder, who: Reminders, session: DbSession) -> Reminded:
    return services.remind(body=body, who=who, session=session)
