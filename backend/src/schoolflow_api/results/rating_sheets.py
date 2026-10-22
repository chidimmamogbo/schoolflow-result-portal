"""Rating sheets for Skill ratings levels (BUILD_PROMPT 9.2h1; SPEC F26 rules 3 and 4; D-168).

One sheet per learning area per arm per term (a result_sheets row with a
learning area instead of a subject). Like score sheets, assignments decide:
the `teacher_subjects` view gives each teacher their learning areas (the
class teacher who teaches all subjects gets every area the class takes), and
class teacher assistants work on every area of their arm. Pupils are rated
on each active skill of the area with a point of the school's scale, plus an
optional short comment per pupil. Submitting needs every skill rated (the
database checks it, AC26.2); the moves are in results/workflow.py.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import Field, StringConstraints
from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.audit.log import write_audit
from schoolflow_api.authz.deps import Principal, ensure_level_enabled, found, require
from schoolflow_api.authz.permissions import Role
from schoolflow_api.core.deps import DbSession
from schoolflow_api.core.errors import ProblemError, problem_response
from schoolflow_api.core.schemas import ApiModel
from schoolflow_api.grading.setup import ensure_defaults
from schoolflow_api.results.sheets import EDITABLE, Reason, active_term, staff_only, term_structure
from schoolflow_api.schools.models import Feature, Level

router = APIRouter(prefix="/rating-sheets", tags=["sheets"])

Results = Annotated[Principal, Depends(require(feature=Feature.RESULTS))]
Comment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class RatingSheetRow(ApiModel):
    id: str | None
    arm_id: str
    learning_area_id: str
    class_name: str
    learning_area_name: str
    level: str
    status: str
    revision: int | None


class OpenRatingSheet(ApiModel):
    arm_id: uuid.UUID
    learning_area_id: uuid.UUID


class SkillOut(ApiModel):
    id: str
    name: str
    description: str | None


class PointOut(ApiModel):
    id: str
    name: str
    code: str
    is_attention: bool


class PupilRatings(ApiModel):
    enrolment_id: str
    admission_number: str
    surname: str
    first_name: str
    ratings: dict[str, str]
    comment: str | None
    missing: list[str]


class RatingCounts(ApiModel):
    complete: int
    missing: int


class RatingSheetView(ApiModel):
    id: str
    class_name: str
    learning_area_name: str
    level: str
    term_id: str
    status: str
    revision: int
    status_comment: str | None
    can_edit: bool
    skills: list[SkillOut]
    scale: list[PointOut]
    rows: list[PupilRatings]
    counts: RatingCounts


class RatingCell(ApiModel):
    enrolment_id: uuid.UUID
    skill_id: uuid.UUID
    point_id: uuid.UUID | None


class CommentCell(ApiModel):
    enrolment_id: uuid.UUID
    comment: Comment | None


class SaveRatings(ApiModel):
    ratings: Annotated[list[RatingCell], Field(max_length=3000)] = Field(
        default_factory=list[RatingCell]
    )
    comments: Annotated[list[CommentCell], Field(max_length=200)] = Field(
        default_factory=list[CommentCell]
    )
    reason: Reason | None = None


# --- who and which -------------------------------------------------------------------------


def my_area_pairs(session: Session, user_id: uuid.UUID) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """(arm, learning area) pairs this person teaches or assists in."""
    rows = session.execute(
        text(
            "select arm_id, learning_area_id from teacher_subjects"
            " where teacher_id = :u and learning_area_id is not null"
            " union select a.arm_id, cla.learning_area_id from class_assistants a"
            " join class_arms ar on ar.id = a.arm_id"
            " join class_learning_areas cla on cla.class_id = ar.class_id"
            " where a.assistant_id = :u"
        ),
        {"u": user_id},
    )
    return {(r.arm_id, r.learning_area_id) for r in rows}


RATING_SELECT = (
    "select r.id, r.arm_id, r.learning_area_id, r.term_id, r.structure_id, r.status, r.revision,"
    " r.status_comment, c.level, c.name || a.name as class_name,"
    " la.name as learning_area_name, t.session_id"
    " from result_sheets r join class_arms a on a.id = r.arm_id"
    " join classes c on c.id = a.class_id join learning_areas la on la.id = r.learning_area_id"
    " join terms t on t.id = r.term_id"
)


def load_rating_sheet(session: Session, who: Principal, sheet_id: uuid.UUID, *, write: bool) -> Any:
    staff_only(who)
    sheet = found(
        session.execute(text(f"{RATING_SELECT} where r.id = :id"), {"id": sheet_id}).first()
    )
    teaches = (sheet.arm_id, sheet.learning_area_id) in my_area_pairs(session, who.user_id)
    if not teaches and who.role is not Role.SCHOOL_ADMIN:
        raise ProblemError(404, "Not Found")
    ensure_level_enabled(session, who, Level(sheet.level))
    if write and not teaches:
        raise ProblemError(403, "Only the class's teachers enter ratings.", code="not_assigned")
    return sheet


# --- my rating sheets and opening one ---------------------------------------------------------


@router.get("", response_model=list[RatingSheetRow])
def my_rating_sheets(who: Results, session: DbSession) -> list[RatingSheetRow]:
    staff_only(who)
    term = active_term(session)
    pairs = my_area_pairs(session, who.user_id)
    if not pairs:
        return []
    rows = session.execute(
        text(
            "select a.id as arm_id, la.id as area_id, c.name || a.name as class_name,"
            " la.name as area_name, c.level, r.id as sheet_id, r.status, r.revision"
            " from class_arms a join classes c on c.id = a.class_id"
            " join school_levels l on l.level = c.level"
            " join class_learning_areas cla on cla.class_id = c.id"
            " join learning_areas la on la.id = cla.learning_area_id"
            " left join result_sheets r on r.arm_id = a.id and r.learning_area_id = la.id"
            "   and r.term_id = :term"
            " where l.enabled and l.assessment_mode = 'skill_ratings'"
            " order by c.name, a.name, la.position"
        ),
        {"term": term.id},
    )
    return [
        RatingSheetRow(
            id=str(r.sheet_id) if r.sheet_id else None,
            arm_id=str(r.arm_id),
            learning_area_id=str(r.area_id),
            class_name=r.class_name,
            learning_area_name=r.area_name,
            level=r.level,
            status=r.status or "not_started",
            revision=r.revision,
        )
        for r in rows
        if (r.arm_id, r.area_id) in pairs
    ]


@router.post("", response_model=RatingSheetView, responses={201: {"model": RatingSheetView}})
def open_rating_sheet(
    body: OpenRatingSheet, who: Results, session: DbSession, response: Response
) -> RatingSheetView:
    staff_only(who)
    if (body.arm_id, body.learning_area_id) not in my_area_pairs(session, who.user_id):
        raise ProblemError(404, "Not Found")
    term = active_term(session)
    level = str(
        found(
            session.scalar(
                text(
                    "select c.level from class_arms a join classes c on c.id = a.class_id"
                    " where a.id = :a"
                ),
                {"a": body.arm_id},
            )
        )
    )
    ensure_level_enabled(session, who, Level(level))
    mode = session.scalar(
        text("select assessment_mode from school_levels where level = :l"), {"l": level}
    )
    if mode != "skill_ratings":
        raise ProblemError(409, "This level uses score sheets.", code="use_score_sheet")
    sheet_id = session.scalar(
        text(
            "select id from result_sheets where arm_id = :a and learning_area_id = :la"
            " and term_id = :t"
        ),
        {"a": body.arm_id, "la": body.learning_area_id, "t": term.id},
    )
    if sheet_id is None:
        structure_id = term_structure(session, who, level, term.id)
        sheet_id = session.scalar(
            text(
                "insert into result_sheets (school_id, term_id, arm_id, structure_id,"
                " learning_area_id) values (:school, :t, :a, :st, :la) returning id"
            ),
            {
                "school": who.school_id,
                "t": term.id,
                "a": body.arm_id,
                "st": structure_id,
                "la": body.learning_area_id,
            },
        )
        write_audit(
            session,
            who.school_id,
            who.role.value,
            "sheets.create",
            target=("result_sheets", sheet_id),
        )
        response.status_code = 201
    return rating_view(session, who, load_rating_sheet(session, who, sheet_id, write=False))


# --- the grid ---------------------------------------------------------------------------------


def skills_of(session: Session, area_id: uuid.UUID) -> list[SkillOut]:
    return [
        SkillOut(id=str(r.id), name=r.name, description=r.description)
        for r in session.execute(
            text(
                "select id, name, description from skills where learning_area_id = :a"
                " and is_active order by position, name"
            ),
            {"a": area_id},
        )
    ]


def scale_of(session: Session, who: Principal) -> list[PointOut]:
    ensure_defaults(session, found(who.school_id), who.role.value)
    return [
        PointOut(id=str(r.id), name=r.name, code=r.code, is_attention=r.is_attention)
        for r in session.execute(
            text("select id, name, code, is_attention from rating_scale_points order by position")
        )
    ]


def pupils_of(session: Session, sheet: Any) -> list[Any]:
    """Every current pupil of the arm in the term's session."""
    return list(
        session.execute(
            text(
                "select e.id as enrolment_id, p.admission_number, p.surname, p.first_name"
                " from enrolments e join students p on p.id = e.student_id"
                " where e.arm_id = :arm and e.session_id = :year and e.left_on is null"
                " order by p.surname, p.first_name, p.admission_number"
            ),
            {"arm": sheet.arm_id, "year": sheet.session_id},
        )
    )


def stored(
    session: Session, sheet_id: uuid.UUID
) -> tuple[dict[tuple[str, str], Any], dict[str, Any]]:
    ratings = {
        (str(r.enrolment_id), str(r.skill_id)): r
        for r in session.execute(
            text(
                "select id, enrolment_id, skill_id, point_id from skill_ratings where sheet_id = :s"
            ),
            {"s": sheet_id},
        )
    }
    comments = {
        str(r.enrolment_id): r
        for r in session.execute(
            text("select id, enrolment_id, comment from area_comments where sheet_id = :s"),
            {"s": sheet_id},
        )
    }
    return ratings, comments


def rating_view(session: Session, who: Principal, sheet: Any) -> RatingSheetView:
    skills = skills_of(session, sheet.learning_area_id)
    ratings, comments = stored(session, sheet.id)
    rows: list[PupilRatings] = []
    for pupil in pupils_of(session, sheet):
        key = str(pupil.enrolment_id)
        given = {k.id: str(ratings[(key, k.id)].point_id) for k in skills if (key, k.id) in ratings}
        rows.append(
            PupilRatings(
                enrolment_id=key,
                admission_number=pupil.admission_number,
                surname=pupil.surname,
                first_name=pupil.first_name,
                ratings=given,
                comment=comments[key].comment if key in comments else None,
                missing=[k.name for k in skills if k.id not in given],
            )
        )
    teaches = (sheet.arm_id, sheet.learning_area_id) in my_area_pairs(session, who.user_id)
    return RatingSheetView(
        id=str(sheet.id),
        class_name=sheet.class_name,
        learning_area_name=sheet.learning_area_name,
        level=sheet.level,
        term_id=str(sheet.term_id),
        status=sheet.status,
        revision=sheet.revision,
        status_comment=sheet.status_comment,
        can_edit=teaches and sheet.status in EDITABLE,
        skills=skills,
        scale=scale_of(session, who),
        rows=rows,
        counts=RatingCounts(
            complete=sum(1 for r in rows if not r.missing),
            missing=sum(1 for r in rows if r.missing),
        ),
    )


@router.get("/{sheet_id}", response_model=RatingSheetView)
def get_rating_sheet(sheet_id: uuid.UUID, who: Results, session: DbSession) -> RatingSheetView:
    return rating_view(session, who, load_rating_sheet(session, who, sheet_id, write=False))


# --- saving -------------------------------------------------------------------------------------


def check(session: Session, who: Principal, sheet: Any, body: SaveRatings) -> list[dict[str, Any]]:
    on_sheet = {str(p.enrolment_id) for p in pupils_of(session, sheet)}
    skills = {k.id for k in skills_of(session, sheet.learning_area_id)}
    points = {p.id for p in scale_of(session, who)}
    errors: list[dict[str, Any]] = []
    for index, cell in enumerate(body.ratings):
        problem = None
        if str(cell.enrolment_id) not in on_sheet:
            problem = "This pupil is not on this sheet."
        elif str(cell.skill_id) not in skills:
            problem = "This is not an active skill of this learning area."
        elif cell.point_id is not None and str(cell.point_id) not in points:
            problem = "This is not a point of the school's rating scale."
        if problem:
            errors.append(
                {"loc": ["body", "ratings", index], "msg": problem, "type": "invalid_rating"}
            )
    for index, cell in enumerate(body.comments):
        if str(cell.enrolment_id) not in on_sheet:
            errors.append(
                {
                    "loc": ["body", "comments", index],
                    "msg": "This pupil is not on this sheet.",
                    "type": "invalid_rating",
                }
            )
    return errors


@router.put("/{sheet_id}/ratings", response_model=RatingSheetView)
def save_ratings(
    sheet_id: uuid.UUID, body: SaveRatings, who: Results, session: DbSession
) -> RatingSheetView | JSONResponse:
    sheet = load_rating_sheet(session, who, sheet_id, write=True)
    errors = check(session, who, sheet, body)
    if errors:
        return problem_response(
            422, "Check the highlighted ratings", code="invalid_ratings", errors=errors
        )
    ratings, comments = stored(session, sheet.id)
    changed: list[dict[str, Any]] = []
    latest = {(str(c.enrolment_id), str(c.skill_id)): c for c in body.ratings}
    for key, cell in latest.items():
        before = ratings.get(key)
        old = str(before.point_id) if before else None
        new = str(cell.point_id) if cell.point_id else None
        if new is None and before is not None:
            session.execute(text("delete from skill_ratings where id = :id"), {"id": before.id})
        elif before is None and new is not None:
            session.execute(
                text(
                    "insert into skill_ratings (school_id, sheet_id, enrolment_id, skill_id,"
                    " point_id) values (:school, :sheet, :e, :k, :p)"
                ),
                {
                    "school": who.school_id,
                    "sheet": sheet.id,
                    "e": cell.enrolment_id,
                    "k": cell.skill_id,
                    "p": cell.point_id,
                },
            )
        elif before is not None and old != new:
            session.execute(
                text("update skill_ratings set point_id = :p, change_reason = :r where id = :id"),
                {"p": cell.point_id, "r": body.reason, "id": before.id},
            )
        if old != new:
            changed.append({"cell": list(key), "old": old, "new": new})
    for cell in {str(c.enrolment_id): c for c in body.comments}.values():
        key = str(cell.enrolment_id)
        before = comments.get(key)
        if cell.comment is None and before is not None:
            session.execute(text("delete from area_comments where id = :id"), {"id": before.id})
        elif before is None and cell.comment is not None:
            session.execute(
                text(
                    "insert into area_comments (school_id, sheet_id, enrolment_id, comment)"
                    " values (:school, :sheet, :e, :c)"
                ),
                {
                    "school": who.school_id,
                    "sheet": sheet.id,
                    "e": cell.enrolment_id,
                    "c": cell.comment,
                },
            )
        elif before is not None and cell.comment is not None and before.comment != cell.comment:
            session.execute(
                text("update area_comments set comment = :c where id = :id"),
                {"c": cell.comment, "id": before.id},
            )
    if changed or body.comments:
        write_audit(
            session,
            who.school_id,
            who.role.value,
            "ratings.save",
            target=("result_sheets", sheet.id),
            new={"cells": changed, "comments": len(body.comments)},
            reason=body.reason,
        )
    return rating_view(session, who, sheet)
