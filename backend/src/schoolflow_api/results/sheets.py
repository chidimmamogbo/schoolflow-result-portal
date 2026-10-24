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
"""

import csv
import io
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import Field, StrictInt, StringConstraints
from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.audit.log import write_audit
from schoolflow_api.authz.deps import Principal, ensure_level_enabled, found, require
from schoolflow_api.authz.permissions import Role
from schoolflow_api.core.deps import DbSession
from schoolflow_api.core.errors import ProblemError, problem_response
from schoolflow_api.core.schemas import ApiModel
from schoolflow_api.grading.setup import ensure_defaults
from schoolflow_api.results.engine import Column, duplicates, grade_for, subject_total
from schoolflow_api.school.grading import Band, structure_of
from schoolflow_api.schools.models import Feature, Level

router = APIRouter(prefix="/sheets", tags=["sheets"])

Results = Annotated[Principal, Depends(require(feature=Feature.RESULTS))]
STAFF = {Role.SCHOOL_ADMIN, Role.REVIEWER, Role.TEACHER}
EDITABLE = {"draft", "returned_for_correction"}
NAME_COLUMNS = ["admission_number", "surname", "first_name"]
MAX_CSV_BYTES = 1024 * 1024
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


# --- shapes ---------------------------------------------------------------------------------


class SheetRow(ApiModel):
    id: str | None
    arm_id: str
    subject_id: str
    class_name: str
    subject_name: str
    level: str
    status: str
    revision: int | None


class OpenSheet(ApiModel):
    arm_id: uuid.UUID
    subject_id: uuid.UUID


class ColumnOut(ApiModel):
    id: str
    label: str
    name: str
    max_score: int


class PupilRow(ApiModel):
    enrolment_id: str
    admission_number: str
    surname: str
    first_name: str
    scores: dict[str, int]
    total: int | None
    grade: str | None
    missing: list[str]
    out_of_range: list[str]


class Counts(ApiModel):
    complete: int
    missing: int
    errors: int


class SheetView(ApiModel):
    id: str
    class_name: str
    subject_name: str
    level: str
    term_id: str
    status: str
    revision: int
    status_comment: str | None
    can_edit: bool
    columns: list[ColumnOut]
    rows: list[PupilRow]
    counts: Counts


class Cell(ApiModel):
    enrolment_id: uuid.UUID
    component_id: uuid.UUID
    # Whole numbers only: 15.5 and "15" are refused (AT-11.2). None removes a score.
    value: StrictInt | None


class SaveScores(ApiModel):
    scores: Annotated[list[Cell], Field(max_length=2000)]
    reason: Reason | None = None


class ImportRow(ApiModel):
    row: int
    admission_number: str
    errors: list[str]


class ImportPreview(ApiModel):
    rows: list[ImportRow]
    valid: int
    invalid: int


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


# --- my sheets and opening one -------------------------------------------------------------


@router.get("", response_model=list[SheetRow])
def my_sheets(who: Results, session: DbSession) -> list[SheetRow]:
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


@router.post("", response_model=SheetView, responses={201: {"model": SheetView}})
def open_sheet(body: OpenSheet, who: Results, session: DbSession, response: Response) -> SheetView:
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


@router.get("/{sheet_id}", response_model=SheetView)
def get_sheet(sheet_id: uuid.UUID, who: Results, session: DbSession) -> SheetView:
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


@router.put("/{sheet_id}/scores", response_model=SheetView)
def save_scores(
    sheet_id: uuid.UUID, body: SaveScores, who: Results, session: DbSession
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


@router.get("/{sheet_id}/template.csv")
def template(sheet_id: uuid.UUID, who: Results, session: DbSession) -> Response:
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


@router.get("/{sheet_id}/export.csv")
def export(sheet_id: uuid.UUID, who: Results, session: DbSession) -> Response:
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


@router.post("/{sheet_id}/import", response_model=None)
def import_scores(
    sheet_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    who: Results,
    session: DbSession,
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


@router.post("/{sheet_id}/import/errors.csv")
def import_errors(
    sheet_id: uuid.UUID, file: Annotated[UploadFile, File()], who: Results, session: DbSession
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
