"""The publication routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import (
    DbSession,
    Principal,
    require,
)
from app.src.publication import services
from app.src.publication.schemas import (
    HeadComments,
    Published,
    Readiness,
    ReopenBody,
    ReportRow,
    RevokeBody,
    Revoked,
)
from app.src.schools.models import Feature

router = APIRouter(prefix="/school", tags=["publication"])

Publishers = Annotated[Principal, Depends(require("results.publish", feature=Feature.RESULTS))]

Commenters = Annotated[
    Principal, Depends(require("results.principal_comments", feature=Feature.RESULTS))
]

Revokers = Annotated[Principal, Depends(require("results.revoke", feature=Feature.RESULTS))]

Reopeners = Annotated[Principal, Depends(require("results.reopen", feature=Feature.RESULTS))]


@router.get("/publications/{arm_id}", response_model=Readiness)
def get_readiness(arm_id: uuid.UUID, who: Publishers, session: DbSession) -> Readiness:
    return services.get_readiness(arm_id=arm_id, who=who, session=session)


@router.put("/publications/{arm_id}/principal-comments", response_model=Readiness)
def principal_comments(
    arm_id: uuid.UUID, body: HeadComments, who: Commenters, session: DbSession
) -> Readiness:
    return services.principal_comments(arm_id=arm_id, body=body, who=who, session=session)


@router.post("/publications/{arm_id}/publish", response_model=Published)
def publish(arm_id: uuid.UUID, who: Publishers, session: DbSession) -> Published:
    return services.publish(arm_id=arm_id, who=who, session=session)


# --- reports: list and revoke --------------------------------------------------------------------
@router.get("/reports", response_model=list[ReportRow])
def list_reports(
    who: Publishers,
    session: DbSession,
    arm_id: uuid.UUID | None = None,
    term_id: uuid.UUID | None = None,
) -> list[ReportRow]:
    return services.list_reports(who=who, session=session, arm_id=arm_id, term_id=term_id)


@router.post("/reports/{report_id}/revoke", response_model=Revoked)
def revoke(report_id: uuid.UUID, body: RevokeBody, who: Revokers, session: DbSession) -> Revoked:
    return services.revoke(report_id=report_id, body=body, who=who, session=session)


@router.post("/publications/{arm_id}/reopen", response_model=Readiness)
def reopen(arm_id: uuid.UUID, body: ReopenBody, who: Reopeners, session: DbSession) -> Readiness:
    return services.reopen(arm_id=arm_id, body=body, who=who, session=session)
