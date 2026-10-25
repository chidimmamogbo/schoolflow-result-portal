"""The results routes: each takes the request and calls the service (D-173).

The rules live in services.py. See its docstring for what this domain does.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import JSONResponse

from app.core.dependencies import DbSession, Principal, require
from app.src.results import services
from app.src.results.schemas import (
    ImportPreview,
    MoveResult,
    OpenRatingSheet,
    OpenSheet,
    RatingSheetRow,
    RatingSheetView,
    Reason,
    ReturnBody,
    SaveRatings,
    SaveScores,
    SheetRow,
    SheetSummary,
    SheetView,
)
from app.src.schools.models import Feature

router = APIRouter(prefix="/sheets", tags=["sheets"])

Results = Annotated[Principal, Depends(require(feature=Feature.RESULTS))]


# --- my sheets and opening one -------------------------------------------------------------
@router.get("", response_model=list[SheetRow])
def my_sheets(who: Results, session: DbSession) -> list[SheetRow]:
    return services.my_sheets(who=who, session=session)


@router.post("", response_model=SheetView, responses={201: {"model": SheetView}})
def open_sheet(body: OpenSheet, who: Results, session: DbSession, response: Response) -> SheetView:
    return services.open_sheet(body=body, who=who, session=session, response=response)


@router.get("/{sheet_id}", response_model=SheetView)
def get_sheet(sheet_id: uuid.UUID, who: Results, session: DbSession) -> SheetView:
    return services.get_sheet(sheet_id=sheet_id, who=who, session=session)


@router.put("/{sheet_id}/scores", response_model=SheetView)
def save_scores(
    sheet_id: uuid.UUID, body: SaveScores, who: Results, session: DbSession
) -> SheetView | JSONResponse:
    return services.save_scores(sheet_id=sheet_id, body=body, who=who, session=session)


@router.get("/{sheet_id}/template.csv")
def template(sheet_id: uuid.UUID, who: Results, session: DbSession) -> Response:
    return services.template(sheet_id=sheet_id, who=who, session=session)


@router.get("/{sheet_id}/export.csv")
def export(sheet_id: uuid.UUID, who: Results, session: DbSession) -> Response:
    return services.export(sheet_id=sheet_id, who=who, session=session)


@router.post("/{sheet_id}/import", response_model=None)
def import_scores(
    sheet_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    who: Results,
    session: DbSession,
    commit: bool = False,
    reason: Reason | None = None,
) -> ImportPreview | SheetView:
    return services.import_scores(
        sheet_id=sheet_id, file=file, who=who, session=session, commit=commit, reason=reason
    )


@router.post("/{sheet_id}/import/errors.csv")
def import_errors(
    sheet_id: uuid.UUID, file: Annotated[UploadFile, File()], who: Results, session: DbSession
) -> Response:
    return services.import_errors(sheet_id=sheet_id, file=file, who=who, session=session)


# --- rating_sheets ----------------------------------------------------------------------
rating_router = APIRouter(prefix="/rating-sheets", tags=["sheets"])


# --- my rating sheets and opening one ---------------------------------------------------------
@rating_router.get("", response_model=list[RatingSheetRow])
def my_rating_sheets(who: Results, session: DbSession) -> list[RatingSheetRow]:
    return services.my_rating_sheets(who=who, session=session)


@rating_router.post("", response_model=RatingSheetView, responses={201: {"model": RatingSheetView}})
def open_rating_sheet(
    body: OpenRatingSheet, who: Results, session: DbSession, response: Response
) -> RatingSheetView:
    return services.open_rating_sheet(body=body, who=who, session=session, response=response)


@rating_router.get("/{sheet_id}", response_model=RatingSheetView)
def get_rating_sheet(sheet_id: uuid.UUID, who: Results, session: DbSession) -> RatingSheetView:
    return services.get_rating_sheet(sheet_id=sheet_id, who=who, session=session)


@rating_router.put("/{sheet_id}/ratings", response_model=RatingSheetView)
def save_ratings(
    sheet_id: uuid.UUID, body: SaveRatings, who: Results, session: DbSession
) -> RatingSheetView | JSONResponse:
    return services.save_ratings(sheet_id=sheet_id, body=body, who=who, session=session)


# --- workflow ----------------------------------------------------------------------
workflow_router = APIRouter(tags=["sheets"])


Reviewers = Annotated[Principal, Depends(require("sheets.review", feature=Feature.RESULTS))]

Returners = Annotated[Principal, Depends(require("sheets.return", feature=Feature.RESULTS))]

Approvers = Annotated[Principal, Depends(require("sheets.approve", feature=Feature.RESULTS))]


# --- the moves --------------------------------------------------------------------------------
@workflow_router.post("/sheets/{sheet_id}/submit", response_model=MoveResult)
def submit(sheet_id: uuid.UUID, who: Results, session: DbSession) -> MoveResult:
    return services.submit(sheet_id=sheet_id, who=who, session=session)


@workflow_router.post("/sheets/{sheet_id}/return", response_model=MoveResult)
def return_sheet(
    sheet_id: uuid.UUID, body: ReturnBody, who: Returners, session: DbSession
) -> MoveResult:
    return services.return_sheet(sheet_id=sheet_id, body=body, who=who, session=session)


@workflow_router.post("/sheets/{sheet_id}/review", response_model=MoveResult)
def review(sheet_id: uuid.UUID, who: Reviewers, session: DbSession) -> MoveResult:
    return services.review(sheet_id=sheet_id, who=who, session=session)


@workflow_router.post("/sheets/{sheet_id}/approve", response_model=MoveResult)
def approve(sheet_id: uuid.UUID, who: Approvers, session: DbSession) -> MoveResult:
    return services.approve(sheet_id=sheet_id, who=who, session=session)


@workflow_router.get("/reviews", response_model=list[SheetSummary])
def review_queue(who: Reviewers, session: DbSession) -> list[SheetSummary]:
    return services.review_queue(who=who, session=session)


@workflow_router.get("/reviews/{sheet_id}", response_model=None)
def review_sheet(
    sheet_id: uuid.UUID, who: Reviewers, session: DbSession
) -> SheetView | RatingSheetView:
    return services.review_sheet(sheet_id=sheet_id, who=who, session=session)


@workflow_router.get("/school/sheets", response_model=list[SheetSummary])
def school_sheets(who: Approvers, session: DbSession) -> list[SheetSummary]:
    return services.school_sheets(who=who, session=session)
