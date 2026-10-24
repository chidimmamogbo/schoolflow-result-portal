"""Moving a sheet along SPEC section 8 (BUILD_PROMPT 9.2i first part).

SPEC F10; D-052, D-142, D-168.

For score sheets and rating sheets alike:
- submit (draft to submitted, returned to resubmitted): a teacher the sheet is
  assigned to; assistants enter but never submit (F06 rule 3); the database
  checks completeness (every score, or every skill rated);
- return (comment required) and review: a reviewer whose scope covers the
  sheet; reviewers see their queue and the sheets in it, never change scores;
- approve: a school admin; directly from submitted only when no reviewer's
  scope covers the sheet (D-142); never the person who submitted it (D-052).

The database records every move in approval_actions and refuses any move
section 8 does not allow; these routes add who may ask, with clear answers.
Publishing, reopening and revoking come with publication (9.2i second part).
"""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import StringConstraints
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import (
    DbSession,
    Principal,
    ensure_level_enabled,
    found,
    require,
    require_status,
)
from app.core.errors import ProblemError
from app.core.permissions import Role
from app.core.schemas import ApiModel
from app.src.audit.services import write_audit
from app.src.results import rating_sheets as rating_sheets
from app.src.results import sheets as sheets
from app.src.schools.models import Feature, Level

router = APIRouter(tags=["sheets"])

Results = Annotated[Principal, Depends(require(feature=Feature.RESULTS))]
Reviewers = Annotated[Principal, Depends(require("sheets.review", feature=Feature.RESULTS))]
Returners = Annotated[Principal, Depends(require("sheets.return", feature=Feature.RESULTS))]
Approvers = Annotated[Principal, Depends(require("sheets.approve", feature=Feature.RESULTS))]
Comment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class MoveResult(ApiModel):
    id: str
    status: str
    revision: int
    status_comment: str | None


class ReturnBody(ApiModel):
    comment: Comment


class SheetSummary(ApiModel):
    id: str
    kind: Literal["scores", "ratings"]
    class_name: str
    name: str
    status: str
    revision: int
    needs_review: bool


ANY_SHEET = (
    "select r.id, r.arm_id, r.subject_id, r.learning_area_id, r.status, r.revision,"
    " r.status_comment, c.level, c.name || a.name as class_name,"
    " coalesce(s.name, la.name) as name"
    " from result_sheets r join class_arms a on a.id = r.arm_id"
    " join classes c on c.id = a.class_id"
    " left join subjects s on s.id = r.subject_id"
    " left join learning_areas la on la.id = r.learning_area_id"
)

# The same coverage rule the database uses for D-142 (check_sheet_transition).
COVERED = (
    "exists (select 1 from reviewer_scopes rs left join subjects sx on sx.id = r.subject_id"
    " where rs.reviewer_id = coalesce(cast(:reviewer as uuid), rs.reviewer_id)"
    " and ((rs.department_id is not null and rs.department_id = sx.department_id)"
    "  or (rs.department_id is null"
    "      and (rs.subject_id is null or rs.subject_id = r.subject_id)"
    "      and (rs.class_id is null or rs.class_id = a.class_id))))"
)


def load(session: Session, who: Principal, sheet_id: uuid.UUID) -> Any:
    sheet = found(session.execute(text(f"{ANY_SHEET} where r.id = :id"), {"id": sheet_id}).first())
    ensure_level_enabled(session, who, Level(sheet.level))
    return sheet


def in_scope(session: Session, who: Principal, sheet_id: uuid.UUID) -> bool:
    return bool(
        session.scalar(
            text(
                f"select {COVERED} from result_sheets r join class_arms a on a.id = r.arm_id"  # noqa: S608
                " where r.id = :id"
            ),
            {"id": sheet_id, "reviewer": who.user_id},
        )
    )


def move(session: Session, who: Principal, sheet: Any, to: str, comment: str | None = None) -> Any:
    session.execute(
        text("update result_sheets set status = :to, status_comment = :c where id = :id"),
        {"to": to, "c": comment, "id": sheet.id},
    )
    write_audit(
        session,
        who.school_id,
        who.role.value,
        f"sheets.{to}",
        target=("result_sheets", sheet.id),
        old={"status": sheet.status},
        new={"status": to},
        reason=comment,
    )
    return session.execute(
        text("select id, status, revision, status_comment from result_sheets where id = :id"),
        {"id": sheet.id},
    ).one()


def result(row: Any) -> MoveResult:
    return MoveResult(
        id=str(row.id), status=row.status, revision=row.revision, status_comment=row.status_comment
    )


# --- the moves --------------------------------------------------------------------------------


@router.post("/sheets/{sheet_id}/submit", response_model=MoveResult)
def submit(sheet_id: uuid.UUID, who: Results, session: DbSession) -> MoveResult:
    sheets.staff_only(who)
    sheet = load(session, who, sheet_id)
    teaches = bool(
        session.scalar(
            text(
                "select exists (select 1 from teacher_subjects where teacher_id = :u"
                " and arm_id = :a and (subject_id = :s or learning_area_id = :la))"
            ),
            {
                "u": who.user_id,
                "a": sheet.arm_id,
                "s": sheet.subject_id,
                "la": sheet.learning_area_id,
            },
        )
    )
    if not teaches:
        assists = session.scalar(
            text(
                "select exists (select 1 from class_assistants where arm_id = :a"
                " and assistant_id = :u)"
            ),
            {"a": sheet.arm_id, "u": who.user_id},
        )
        if assists:
            raise ProblemError(
                403,
                "Assistants enter scores and ratings; the class teacher submits.",
                code="assistants_cannot_submit",
            )
        if who.role is Role.SCHOOL_ADMIN:
            raise ProblemError(403, "Only the sheet's teacher submits it.", code="not_assigned")
        raise ProblemError(404, "Not Found")
    require_status(sheet.status, "draft", "returned_for_correction")
    to = "submitted" if sheet.status == "draft" else "resubmitted"
    return result(move(session, who, sheet, to))


def reviewer_sheet(session: Session, who: Principal, sheet_id: uuid.UUID) -> Any:
    sheet = load(session, who, sheet_id)
    if not in_scope(session, who, sheet_id):
        raise ProblemError(404, "Not Found")
    return sheet


@router.post("/sheets/{sheet_id}/return", response_model=MoveResult)
def return_sheet(
    sheet_id: uuid.UUID, body: ReturnBody, who: Returners, session: DbSession
) -> MoveResult:
    sheet = reviewer_sheet(session, who, sheet_id)
    require_status(sheet.status, "submitted", "resubmitted")
    return result(move(session, who, sheet, "returned_for_correction", body.comment))


@router.post("/sheets/{sheet_id}/review", response_model=MoveResult)
def review(sheet_id: uuid.UUID, who: Reviewers, session: DbSession) -> MoveResult:
    sheet = reviewer_sheet(session, who, sheet_id)
    require_status(sheet.status, "submitted", "resubmitted")
    return result(move(session, who, sheet, "reviewed"))


@router.post("/sheets/{sheet_id}/approve", response_model=MoveResult)
def approve(sheet_id: uuid.UUID, who: Approvers, session: DbSession) -> MoveResult:
    sheet = load(session, who, sheet_id)
    require_status(sheet.status, "submitted", "resubmitted", "reviewed")
    return result(move(session, who, sheet, "approved"))


# --- queues ----------------------------------------------------------------------------------


def summary(r: Any) -> SheetSummary:
    return SheetSummary(
        id=str(r.id),
        kind="scores" if r.subject_id else "ratings",
        class_name=r.class_name,
        name=r.name,
        status=r.status,
        revision=r.revision,
        needs_review=bool(r.covered),
    )


def term_sheets(session: Session, *, reviewer: uuid.UUID | None, waiting: bool) -> list[Any]:
    term = sheets.active_term(session)
    return list(
        session.execute(
            text(
                f"select * from (select x.*, {COVERED} as covered"  # noqa: S608 (fixed SQL)
                f" from ({ANY_SHEET} where r.term_id = :term) x"
                " join result_sheets r on r.id = x.id join class_arms a on a.id = r.arm_id"
                " join school_levels l on l.level = x.level and l.enabled) y"
                " where (not cast(:waiting as boolean) or y.status in ('submitted', 'resubmitted'))"
                " and (cast(:reviewer as uuid) is null or y.covered)"
                " order by y.class_name, y.name"
            ),
            {"term": term.id, "reviewer": reviewer, "waiting": waiting},
        )
    )


@router.get("/reviews", response_model=list[SheetSummary])
def review_queue(who: Reviewers, session: DbSession) -> list[SheetSummary]:
    """The reviewer's sheets waiting for review, in their scope only (AT-13.4)."""
    return [summary(r) for r in term_sheets(session, reviewer=who.user_id, waiting=True)]


@router.get("/reviews/{sheet_id}", response_model=None)
def review_sheet(
    sheet_id: uuid.UUID, who: Reviewers, session: DbSession
) -> sheets.SheetView | rating_sheets.RatingSheetView:
    sheet = reviewer_sheet(session, who, sheet_id)
    if sheet.subject_id is not None:
        full = session.execute(
            text(f"{sheets.SHEET_SELECT} where r.id = :id"), {"id": sheet_id}
        ).one()
        return sheets.view(session, who, full)
    full = session.execute(
        text(f"{rating_sheets.RATING_SELECT} where r.id = :id"), {"id": sheet_id}
    ).one()
    return rating_sheets.rating_view(session, who, full)


@router.get("/school/sheets", response_model=list[SheetSummary])
def school_sheets(who: Approvers, session: DbSession) -> list[SheetSummary]:
    """Every sheet of the active term, with whether a reviewer covers it (D-142)."""
    return [summary(r) for r in term_sheets(session, reviewer=None, waiting=False)]
