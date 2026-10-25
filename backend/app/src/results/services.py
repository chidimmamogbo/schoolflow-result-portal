"""Score sheets: my sheets, the grid, saving scores and CSV (BUILD_PROMPT 9.2h; SPEC F09; D-167).

Who may do what follows teaching assignments, not roles (D-144, D-049):
- a sheet's teacher is whoever the `teacher_subjects` view gives that subject
  in that arm (a subject assignment, or the form teacher who teaches all
  subjects); class teacher assistants work on every subject sheet of their
  arm (F06 rule 3);
- they open (create) the draft, see it and save scores while it is a draft or
  returned for correction (the database refuses anything else);
- school admins read every sheet of their school but enter scores only where
  they teach (403 `not_assigned`);
- anyone else, or another school, gets 404 (D-047).

Totals, grades and flags come from the results engine; scores themselves are
the only thing stored. Workflow moves (submit, review, approve) are 9.2i.

Rating sheets for Skill ratings levels (BUILD_PROMPT 9.2h1; SPEC F26 rules 3 and 4; D-168).

One sheet per learning area per arm per term (a result_sheets row with a
learning area instead of a subject). Like score sheets, assignments decide:
the `teacher_subjects` view gives each teacher their learning areas (the
class teacher who teaches all subjects gets every area the class takes), and
class teacher assistants work on every area of their arm. Pupils are rated
on each active skill of the area with a point of the school's scale, plus an
optional short comment per pupil. Submitting needs every skill rated (the
database checks it, AC26.2); the moves are in results/workflow.py.

Moving a sheet along SPEC section 8 (BUILD_PROMPT 9.2i first part).

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

import csv
import io
import uuid
from typing import Annotated, Any

from fastapi import File, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import (
    Principal,
    ensure_level_enabled,
    found,
    require_status,
)
from app.core.errors import ProblemError, problem_response
from app.core.permissions import Role
from app.src.audit.services import write_audit
from app.src.grading.schemas import Band
from app.src.grading.services import ensure_defaults, structure_of
from app.src.results.engine import Column, duplicates, grade_for, subject_total
from app.src.results.schemas import (
    Cell,
    ColumnOut,
    Counts,
    ImportPreview,
    ImportRow,
    MoveResult,
    OpenRatingSheet,
    OpenSheet,
    PointOut,
    PupilRatings,
    PupilRow,
    RatingCounts,
    RatingSheetRow,
    RatingSheetView,
    Reason,
    ReturnBody,
    SaveRatings,
    SaveScores,
    SheetRow,
    SheetSummary,
    SheetView,
    SkillOut,
)
from app.src.schools.models import Level

STAFF = {Role.SCHOOL_ADMIN, Role.REVIEWER, Role.TEACHER}

EDITABLE = {"draft", "returned_for_correction"}

NAME_COLUMNS = ["admission_number", "surname", "first_name"]

MAX_CSV_BYTES = 1024 * 1024


# --- who may see and change a sheet --------------------------------------------------------
def my_pairs(session: Session, user_id: uuid.UUID) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """(arm, subject) pairs this person teaches or assists in."""
    rows = session.execute(
        text(
            "select arm_id, subject_id from teacher_subjects where teacher_id = :u"
            " union select a.arm_id, s.subject_id from class_assistants a"
            " join arm_subjects s on s.arm_id = a.arm_id where a.assistant_id = :u"
        ),
        {"u": user_id},
    )
    return {(r.arm_id, r.subject_id) for r in rows}


def staff_only(who: Principal) -> None:
    if who.role not in STAFF:
        raise ProblemError(403, "You don't have permission to do this.", code="permission_denied")


def active_term(session: Session) -> Any:
    term = session.execute(text("select id, session_id from terms where is_active")).first()
    if term is None:
        raise ProblemError(409, "Activate a term first.", code="no_active_term")
    return term


SHEET_SELECT = (
    "select r.id, r.arm_id, r.subject_id, r.term_id, r.structure_id, r.status, r.revision,"
    " r.status_comment, c.level, c.name || a.name as class_name, s.name as subject_name,"
    " t.session_id"
    " from result_sheets r join class_arms a on a.id = r.arm_id"
    " join classes c on c.id = a.class_id join subjects s on s.id = r.subject_id"
    " join terms t on t.id = r.term_id"
)


def load_sheet(session: Session, who: Principal, sheet_id: uuid.UUID, *, write: bool) -> Any:
    staff_only(who)
    sheet = found(
        session.execute(text(f"{SHEET_SELECT} where r.id = :id"), {"id": sheet_id}).first()
    )
    teaches = (sheet.arm_id, sheet.subject_id) in my_pairs(session, who.user_id)
    if not teaches and who.role is not Role.SCHOOL_ADMIN:
        raise ProblemError(404, "Not Found")
    ensure_level_enabled(session, who, Level(sheet.level))
    if write and not teaches:
        raise ProblemError(
            403, "Only the subject's teacher or an assistant enters scores.", code="not_assigned"
        )
    return sheet


def my_sheets(
    who: Principal,
    session: Session,
) -> list[SheetRow]:
    staff_only(who)
    term = active_term(session)
    pairs = my_pairs(session, who.user_id)
    if not pairs:
        return []
    rows = session.execute(
        text(
            "select a.id as arm_id, s.id as subject_id, c.name || a.name as class_name,"
            " s.name as subject_name, c.level, r.id as sheet_id, r.status, r.revision"
            " from class_arms a join classes c on c.id = a.class_id"
            " join school_levels l on l.level = c.level"
            " cross join subjects s"
            " left join result_sheets r on r.arm_id = a.id and r.subject_id = s.id"
            "   and r.term_id = :term"
            " where l.enabled and l.assessment_mode = 'scores'"
            " order by c.name, a.name, s.name"
        ),
        {"term": term.id},
    )
    return [
        SheetRow(
            id=str(r.sheet_id) if r.sheet_id else None,
            arm_id=str(r.arm_id),
            subject_id=str(r.subject_id),
            class_name=r.class_name,
            subject_name=r.subject_name,
            level=r.level,
            status=r.status or "not_started",
            revision=r.revision,
        )
        for r in rows
        if (r.arm_id, r.subject_id) in pairs
    ]


def term_structure(session: Session, who: Principal, level: str, term_id: uuid.UUID) -> uuid.UUID:
    """The term's structure for the level, saved now from the suggestion if needed."""
    existing = session.scalar(
        text("select id from assessment_structures where level = :l and term_id = :t"),
        {"l": level, "t": term_id},
    )
    if existing is not None:
        return existing
    suggestion = structure_of(session, level, term_id)
    structure_id: uuid.UUID = session.scalar(
        text(
            "insert into assessment_structures (school_id, level, term_id, assessment_mode)"
            " values (:s, :l, :t, :m) returning id"
        ),
        {"s": who.school_id, "l": level, "t": term_id, "m": suggestion.assessment_mode},
    )
    for position, column in enumerate(suggestion.components, start=1):
        session.execute(
            text(
                "insert into assessment_components (school_id, structure_id, position, name,"
                " label, max_score) values (:s, :st, :p, :n, :lb, :m)"
            ),
            {
                "s": who.school_id,
                "st": structure_id,
                "p": position,
                "n": column.name,
                "lb": column.label,
                "m": column.max_score,
            },
        )
    return structure_id


def open_sheet(
    body: OpenSheet,
    who: Principal,
    session: Session,
    response: Response,
) -> SheetView:
    staff_only(who)
    if (body.arm_id, body.subject_id) not in my_pairs(session, who.user_id):
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
    if mode != "scores":
        raise ProblemError(409, "This level uses rating sheets.", code="use_rating_sheet")
    sheet_id = session.scalar(
        text("select id from result_sheets where arm_id = :a and subject_id = :s and term_id = :t"),
        {"a": body.arm_id, "s": body.subject_id, "t": term.id},
    )
    if sheet_id is None:
        structure_id = term_structure(session, who, level, term.id)
        sheet_id = session.scalar(
            text(
                "insert into result_sheets (school_id, term_id, arm_id, structure_id, subject_id)"
                " values (:school, :t, :a, :st, :s) returning id"
            ),
            {
                "school": who.school_id,
                "t": term.id,
                "a": body.arm_id,
                "st": structure_id,
                "s": body.subject_id,
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
    return view(session, who, load_sheet(session, who, sheet_id, write=False))


# --- the grid --------------------------------------------------------------------------------
def columns_of(session: Session, structure_id: uuid.UUID) -> list[ColumnOut]:
    return [
        ColumnOut(id=str(r.id), label=r.label, name=r.name, max_score=r.max_score)
        for r in session.execute(
            text(
                "select id, label, name, max_score from assessment_components"
                " where structure_id = :s order by position"
            ),
            {"s": structure_id},
        )
    ]


def pupils_of(session: Session, sheet: Any) -> list[Any]:
    """The arm's current pupils in the term's session who take the subject (AC05.2)."""
    return list(
        session.execute(
            text(
                "select e.id as enrolment_id, p.admission_number, p.surname, p.first_name"
                " from enrolments e join students p on p.id = e.student_id"
                " join student_subjects ss on ss.enrolment_id = e.id and ss.subject_id = :subject"
                " where e.arm_id = :arm and e.session_id = :year and e.left_on is null"
                " order by p.surname, p.first_name, p.admission_number"
            ),
            {"subject": sheet.subject_id, "arm": sheet.arm_id, "year": sheet.session_id},
        )
    )


def stored_scores(session: Session, sheet_id: uuid.UUID) -> dict[tuple[str, str], tuple[Any, int]]:
    return {
        (str(r.enrolment_id), str(r.component_id)): (r.id, r.value)
        for r in session.execute(
            text("select id, enrolment_id, component_id, value from scores where sheet_id = :s"),
            {"s": sheet_id},
        )
    }


def bands_for(session: Session, who: Principal, level: str) -> list[Band]:
    ensure_defaults(session, found(who.school_id), who.role.value)
    return [
        Band(grade=r.grade, min_score=r.min_score, max_score=r.max_score, remark=r.remark)
        for r in session.execute(
            text(
                "select grade, min_score, max_score, remark from grade_bands"
                " where level = :l order by min_score desc"
            ),
            {"l": level},
        )
    ]


def view(session: Session, who: Principal, sheet: Any) -> SheetView:
    cols = columns_of(session, sheet.structure_id)
    engine_columns = [Column(c.id, c.label, c.max_score) for c in cols]
    bands = bands_for(session, who, sheet.level)
    scores = stored_scores(session, sheet.id)
    rows: list[PupilRow] = []
    for pupil in pupils_of(session, sheet):
        key = str(pupil.enrolment_id)
        mine = {c.id: scores[(key, c.id)][1] for c in cols if (key, c.id) in scores}
        result = subject_total(mine, engine_columns)
        grade = grade_for(result.total, bands) if result.total is not None else None
        rows.append(
            PupilRow(
                enrolment_id=key,
                admission_number=pupil.admission_number,
                surname=pupil.surname,
                first_name=pupil.first_name,
                scores=mine,
                total=result.total,
                grade=grade.grade if grade else None,
                missing=list(result.missing),
                out_of_range=list(result.out_of_range),
            )
        )
    teaches = (sheet.arm_id, sheet.subject_id) in my_pairs(session, who.user_id)
    return SheetView(
        id=str(sheet.id),
        class_name=sheet.class_name,
        subject_name=sheet.subject_name,
        level=sheet.level,
        term_id=str(sheet.term_id),
        status=sheet.status,
        revision=sheet.revision,
        status_comment=sheet.status_comment,
        can_edit=teaches and sheet.status in EDITABLE,
        columns=cols,
        rows=rows,
        counts=Counts(
            complete=sum(1 for r in rows if r.total is not None),
            missing=sum(1 for r in rows if r.missing),
            errors=sum(1 for r in rows if r.out_of_range),
        ),
    )


def get_sheet(
    sheet_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> SheetView:
    return view(session, who, load_sheet(session, who, sheet_id, write=False))


# --- saving scores -----------------------------------------------------------------------------
def check_cells(session: Session, sheet: Any, cells: list[Cell]) -> list[dict[str, Any]]:
    maximum = {c.id: (c.label, c.max_score) for c in columns_of(session, sheet.structure_id)}
    on_sheet = {str(p.enrolment_id) for p in pupils_of(session, sheet)}
    errors: list[dict[str, Any]] = []
    for index, cell in enumerate(cells):
        problem = None
        column = maximum.get(str(cell.component_id))
        if str(cell.enrolment_id) not in on_sheet:
            problem = "This pupil is not on this sheet."
        elif column is None:
            problem = "This column is not part of the sheet."
        elif cell.value is not None and not 0 <= cell.value <= column[1]:
            problem = f"{column[0]} must be a whole number from 0 to {column[1]}."
        if problem:
            errors.append(
                {"loc": ["body", "scores", index], "msg": problem, "type": "invalid_score"}
            )
    return errors


def apply_cells(
    session: Session, who: Principal, sheet: Any, cells: list[Cell], reason: str | None
) -> None:
    stored = stored_scores(session, sheet.id)
    changed: list[dict[str, Any]] = []
    # The same cell twice in one save: the last value wins.
    latest = {(str(c.enrolment_id), str(c.component_id)): c for c in cells}
    for key, cell in latest.items():
        before = stored.get(key)
        if cell.value is None:
            if before is not None:
                session.execute(text("delete from scores where id = :id"), {"id": before[0]})
                changed.append({"cell": list(key), "old": before[1], "new": None})
        elif before is None:
            session.execute(
                text(
                    "insert into scores (school_id, sheet_id, enrolment_id, component_id,"
                    " value) values (:school, :sheet, :e, :c, :v)"
                ),
                {
                    "school": who.school_id,
                    "sheet": sheet.id,
                    "e": cell.enrolment_id,
                    "c": cell.component_id,
                    "v": cell.value,
                },
            )
            changed.append({"cell": list(key), "old": None, "new": cell.value})
        elif before[1] != cell.value:
            session.execute(
                text("update scores set value = :v, change_reason = :r where id = :id"),
                {"v": cell.value, "r": reason, "id": before[0]},
            )
            changed.append({"cell": list(key), "old": before[1], "new": cell.value})
    if changed:
        write_audit(
            session,
            who.school_id,
            who.role.value,
            "scores.save",
            target=("result_sheets", sheet.id),
            new={"cells": changed},
            reason=reason,
        )


def save_scores(
    sheet_id: uuid.UUID,
    body: SaveScores,
    who: Principal,
    session: Session,
) -> SheetView | JSONResponse:
    sheet = load_sheet(session, who, sheet_id, write=True)
    errors = check_cells(session, sheet, body.scores)
    if errors:
        return problem_response(
            422, "Check the highlighted scores", code="invalid_scores", errors=errors
        )
    apply_cells(session, who, sheet, body.scores, body.reason)
    return view(session, who, sheet)


# --- CSV ----------------------------------------------------------------------------------------
# A spreadsheet runs a cell that starts with one of these as a formula.
FORMULA_STARTS = ("=", "+", "-", "@", chr(9), chr(13))


def safe_cell(value: str) -> str:
    """A cell a spreadsheet shows as text (names and comments come from the school)."""
    return f"'{value}" if value[:1] in FORMULA_STARTS else value


def csv_text(rows: list[list[str]]) -> str:
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows([[safe_cell(c) for c in r] for r in rows])
    return out.getvalue()


def template(
    sheet_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> Response:
    sheet = load_sheet(session, who, sheet_id, write=False)
    current = view(session, who, sheet)
    header = NAME_COLUMNS + [c.label for c in current.columns]
    rows = [header] + [
        [
            r.admission_number,
            r.surname,
            r.first_name,
            *(str(r.scores[c.id]) if c.id in r.scores else "" for c in current.columns),
        ]
        for r in current.rows
    ]
    return Response(csv_text(rows), media_type="text/csv")


def export(
    sheet_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> Response:
    sheet = load_sheet(session, who, sheet_id, write=False)
    current = view(session, who, sheet)
    header = NAME_COLUMNS + [c.label for c in current.columns] + ["total", "grade"]
    rows = [header] + [
        [
            r.admission_number,
            r.surname,
            r.first_name,
            *(str(r.scores[c.id]) if c.id in r.scores else "" for c in current.columns),
            "" if r.total is None else str(r.total),
            r.grade or "",
        ]
        for r in current.rows
    ]
    return Response(csv_text(rows), media_type="text/csv")


def parse_import(
    session: Session, who: Principal, sheet: Any, raw: bytes
) -> tuple[list[ImportRow], list[Cell], list[list[str]]]:
    """Every row's problems, the cells to save, and the raw rows (for the error file)."""
    if len(raw) > MAX_CSV_BYTES:
        raise ProblemError(413, "The file must be 1 MB or smaller.", code="file_too_large")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ProblemError(422, "Save the file as CSV (UTF-8).", code="csv_encoding") from None
    table = list(csv.reader(io.StringIO(content)))
    cols = columns_of(session, sheet.structure_id)
    header = NAME_COLUMNS + [c.label for c in cols]
    if not table or [h.strip() for h in table[0]] != header:
        raise ProblemError(
            422,
            "Use the columns of this sheet's template: " + ", ".join(header) + ".",
            code="csv_columns",
        )
    body = [row for row in table[1:] if any(cell.strip() for cell in row)]
    by_admission = {
        p.admission_number.lower(): str(p.enrolment_id) for p in pupils_of(session, sheet)
    }
    repeated = {
        number for numbers in duplicates([(row[0],) for row in body]).values() for number in numbers
    }
    previews: list[ImportRow] = []
    cells: list[Cell] = []
    for index, row in enumerate(body, start=1):
        row = (row + [""] * len(header))[: len(header)]
        errors: list[str] = []
        enrolment = by_admission.get(row[0].strip().lower())
        if enrolment is None:
            errors.append("This pupil is not on this sheet.")
        if index in repeated:
            errors.append("This pupil appears more than once in this file.")
        row_cells: list[Cell] = []
        for column, value in zip(cols, row[3:], strict=True):
            value = value.strip()
            if not value:
                continue  # a blank leaves the score as it is
            if not value.isdigit():
                errors.append(f"{column.label}: a whole number is needed.")
            elif int(value) > column.max_score:
                errors.append(f"{column.label}: at most {column.max_score}.")
            elif enrolment is not None:
                row_cells.append(
                    Cell(
                        enrolment_id=uuid.UUID(enrolment),
                        component_id=uuid.UUID(column.id),
                        value=int(value),
                    )
                )
        previews.append(ImportRow(row=index + 1, admission_number=row[0], errors=errors))
        if not errors:
            cells.extend(row_cells)
    return previews, cells, [header, *body]


def import_scores(
    sheet_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    who: Principal,
    session: Session,
    commit: bool = False,
    reason: Reason | None = None,
) -> ImportPreview | SheetView:
    sheet = load_sheet(session, who, sheet_id, write=True)
    previews, cells, _ = parse_import(session, who, sheet, file.file.read(MAX_CSV_BYTES + 1))
    invalid = sum(1 for p in previews if p.errors)
    if not commit:
        return ImportPreview(rows=previews, valid=len(previews) - invalid, invalid=invalid)
    if invalid:
        raise ProblemError(
            422, "Fix the rows with problems; nothing was saved.", code="import_has_errors"
        )
    apply_cells(session, who, sheet, cells, reason)
    return view(session, who, sheet)


def import_errors(
    sheet_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    who: Principal,
    session: Session,
) -> Response:
    sheet = load_sheet(session, who, sheet_id, write=True)
    previews, _, table = parse_import(session, who, sheet, file.file.read(MAX_CSV_BYTES + 1))
    header, body = table[0], table[1:]
    width = len(header)
    rows = [[*header, "errors"]] + [
        [*(row + [""] * width)[:width], " ".join(preview.errors)]
        for preview, row in zip(previews, body, strict=True)
        if preview.errors
    ]
    return Response(csv_text(rows), media_type="text/csv")


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


def my_rating_sheets(
    who: Principal,
    session: Session,
) -> list[RatingSheetRow]:
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


def open_rating_sheet(
    body: OpenRatingSheet,
    who: Principal,
    session: Session,
    response: Response,
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


def rating_pupils_of(session: Session, sheet: Any) -> list[Any]:
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
    for pupil in rating_pupils_of(session, sheet):
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


def get_rating_sheet(
    sheet_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> RatingSheetView:
    return rating_view(session, who, load_rating_sheet(session, who, sheet_id, write=False))


# --- saving -------------------------------------------------------------------------------------
def check(session: Session, who: Principal, sheet: Any, body: SaveRatings) -> list[dict[str, Any]]:
    on_sheet = {str(p.enrolment_id) for p in rating_pupils_of(session, sheet)}
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


def save_ratings(
    sheet_id: uuid.UUID,
    body: SaveRatings,
    who: Principal,
    session: Session,
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


def submit(
    sheet_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> MoveResult:
    staff_only(who)
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


def return_sheet(
    sheet_id: uuid.UUID,
    body: ReturnBody,
    who: Principal,
    session: Session,
) -> MoveResult:
    sheet = reviewer_sheet(session, who, sheet_id)
    require_status(sheet.status, "submitted", "resubmitted")
    return result(move(session, who, sheet, "returned_for_correction", body.comment))


def review(
    sheet_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> MoveResult:
    sheet = reviewer_sheet(session, who, sheet_id)
    require_status(sheet.status, "submitted", "resubmitted")
    return result(move(session, who, sheet, "reviewed"))


def approve(
    sheet_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> MoveResult:
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
    term = active_term(session)
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


def review_queue(
    who: Principal,
    session: Session,
) -> list[SheetSummary]:
    """The reviewer's sheets waiting for review, in their scope only (AT-13.4)."""
    return [summary(r) for r in term_sheets(session, reviewer=who.user_id, waiting=True)]


def review_sheet(
    sheet_id: uuid.UUID,
    who: Principal,
    session: Session,
) -> SheetView | RatingSheetView:
    sheet = reviewer_sheet(session, who, sheet_id)
    if sheet.subject_id is not None:
        full = session.execute(text(f"{SHEET_SELECT} where r.id = :id"), {"id": sheet_id}).one()
        return view(session, who, full)
    full = session.execute(text(f"{RATING_SELECT} where r.id = :id"), {"id": sheet_id}).one()
    return rating_view(session, who, full)


def school_sheets(
    who: Principal,
    session: Session,
) -> list[SheetSummary]:
    """Every sheet of the active term, with whether a reviewer covers it (D-142)."""
    return [summary(r) for r in term_sheets(session, reviewer=None, waiting=False)]
