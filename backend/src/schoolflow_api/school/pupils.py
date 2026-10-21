"""Pupils: registration, enrolment, subjects, moves, logins and CSV import (SPEC F05; D-139).

- A pupil has three name fields (D-139) and an admission number unique in
  the school whatever the capitals (another school may reuse it, AC02.6).
- Enrolment is in an arm of the active term's session; the pupil takes the
  arm's subjects, which can then be changed per pupil (only subjects the arm
  takes, checked by the database).
- Moving arms ends the current enrolment and starts a new one, so the
  history stays (the arm of an enrolment never changes).
- A pupil login is a username (unique in the school) and a temporary
  password slip shown once; pupils log in with the school code (F02).
- CSV import: the same file is previewed (every row's problems listed) and
  then committed, all or nothing (AC05.1).
"""

import csv
import io
import uuid
from datetime import date
from typing import Annotated, Any, Literal

import psycopg
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import Field, StringConstraints, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from schoolflow_api.audit.log import write_audit
from schoolflow_api.auth.temporary import issue_temporary_password
from schoolflow_api.authz.deps import Principal, ensure_level_enabled, found, require
from schoolflow_api.core.deps import DbSession
from schoolflow_api.core.errors import ProblemError
from schoolflow_api.core.schemas import ApiModel
from schoolflow_api.platform.schemas import TemporaryPassword, Username
from schoolflow_api.schools.models import Level

router = APIRouter(prefix="/school", tags=["school"])

Member = Annotated[Principal, Depends(require())]
Admin = Annotated[Principal, Depends(require("users.create"))]

NamePart = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
OtherNames = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
AdmissionNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9/._-]{0,29}$")
]
House = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
CSV_COLUMNS = (
    "surname", "first_name", "other_names", "admission_number", "gender", "date_of_birth", "house",
)  # fmt: skip
MAX_ROWS = 1000
MAX_CSV_BYTES = 1024 * 1024


class PupilFields(ApiModel):
    surname: NamePart
    first_name: NamePart
    other_names: OtherNames | None = None
    admission_number: AdmissionNumber
    gender: Literal["female", "male"]
    date_of_birth: date | None = None
    house: House | None = None


class NewPupil(PupilFields):
    department_id: uuid.UUID | None = None
    arm_id: uuid.UUID | None = None


class EditPupil(ApiModel):
    surname: NamePart | None = None
    first_name: NamePart | None = None
    other_names: OtherNames | None = None
    admission_number: AdmissionNumber | None = None
    gender: Literal["female", "male"] | None = None
    date_of_birth: date | None = None
    house: House | None = None
    department_id: uuid.UUID | None = None
    status: Literal["active", "withdrawn", "graduated"] | None = None


class PupilRow(ApiModel):
    id: str
    surname: str
    first_name: str
    other_names: str | None
    admission_number: str
    gender: str
    date_of_birth: date | None
    house: str | None
    department_id: str | None
    status: str
    arm_id: str | None
    has_login: bool


class Move(ApiModel):
    arm_id: uuid.UUID


class PupilSubjects(ApiModel):
    subject_ids: Annotated[list[uuid.UUID], Field(max_length=40)]


class SubjectName(ApiModel):
    id: str
    name: str


class NewLogin(ApiModel):
    username: Username


class ImportRow(ApiModel):
    row: int
    admission_number: str
    surname: str
    first_name: str
    errors: list[str]


class ImportPreview(ApiModel):
    rows: list[ImportRow]
    valid: int
    invalid: int


class Imported(ApiModel):
    created: int


# --- helpers ----------------------------------------------------------------------------


def active_session(session: Session) -> uuid.UUID:
    year = session.scalar(text("select session_id from terms where is_active"))
    if year is None:
        raise ProblemError(409, "Activate a term before enrolling pupils.", code="no_active_term")
    return year


def arm_in_school(session: Session, who: Principal, arm_id: uuid.UUID) -> uuid.UUID:
    level = found(
        session.scalar(
            text(
                "select c.level from class_arms a join classes c on c.id = a.class_id"
                " where a.id = :a"
            ),
            {"a": arm_id},
        )
    )
    ensure_level_enabled(session, who, Level(level))
    return arm_id


def enrol(
    session: Session, who: Principal, student_id: uuid.UUID, arm_id: uuid.UUID, year: uuid.UUID
) -> None:
    """A new enrolment with the arm's subjects."""
    enrolment_id = session.scalar(
        text(
            "insert into enrolments (school_id, student_id, session_id, arm_id)"
            " values (:s, :p, :y, :a) returning id"
        ),
        {"s": who.school_id, "p": student_id, "y": year, "a": arm_id},
    )
    session.execute(
        text(
            "insert into student_subjects (school_id, enrolment_id, subject_id)"
            " select :s, :e, subject_id from arm_subjects where arm_id = :a"
        ),
        {"s": who.school_id, "e": enrolment_id, "a": arm_id},
    )


PUPIL_SELECT = (
    "select p.id, p.surname, p.first_name, p.other_names, p.admission_number, p.gender,"
    " p.date_of_birth, p.house, p.department_id, p.status, p.user_id is not null as has_login,"
    " (select e.arm_id from enrolments e join terms t on t.session_id = e.session_id"
    "   and t.is_active where e.student_id = p.id and e.left_on is null) as arm_id"
    " from students p"
)


def pupil_row(r: Any) -> PupilRow:
    return PupilRow(
        id=str(r.id),
        surname=r.surname,
        first_name=r.first_name,
        other_names=r.other_names,
        admission_number=r.admission_number,
        gender=r.gender,
        date_of_birth=r.date_of_birth,
        house=r.house,
        department_id=str(r.department_id) if r.department_id else None,
        status=r.status,
        arm_id=str(r.arm_id) if r.arm_id else None,
        has_login=r.has_login,
    )


def load_pupil(session: Session, student_id: uuid.UUID) -> Any:
    return found(
        session.execute(text(f"{PUPIL_SELECT} where p.id = :id"), {"id": student_id}).first()
    )


def admission_taken(error: IntegrityError) -> bool:
    original = error.orig
    rule = original.diag.constraint_name if isinstance(original, psycopg.Error) else None
    return rule == "ix_students_unique_admission_number"


TAKEN = ProblemError(
    409, "This admission number is already used in this school.", code="admission_number_taken"
)


def audit(session: Session, who: Principal, action: str, **details: Any) -> None:
    write_audit(session, who.school_id, who.role.value, action, **details)


# --- one pupil -----------------------------------------------------------------------------


@router.get("/students", response_model=list[PupilRow])
def list_pupils(
    _: Member,
    session: DbSession,
    q: Annotated[str | None, Query(max_length=60)] = None,
    arm_id: uuid.UUID | None = None,
    status: Annotated[Literal["active", "withdrawn", "graduated"] | None, Query()] = None,
) -> list[PupilRow]:
    pattern = None if q is None else "%" + q.replace("%", "").replace("_", "").strip() + "%"
    rows = session.execute(
        text(
            f"select * from ({PUPIL_SELECT}) p"  # noqa: S608 (fixed SQL)
            " where (cast(:q as text) is null or p.surname ilike :q or p.first_name ilike :q"
            "        or p.other_names ilike :q or p.admission_number ilike :q)"
            " and (cast(:arm as uuid) is null or p.arm_id = :arm)"
            " and (cast(:status as text) is null or p.status = :status)"
            " order by p.surname, p.first_name, p.admission_number"
        ),
        {"q": pattern, "arm": arm_id, "status": status},
    )
    return [pupil_row(r) for r in rows]


@router.post("/students", status_code=201, response_model=PupilRow)
def create_pupil(body: NewPupil, who: Admin, session: DbSession) -> PupilRow:
    year = arm = None
    if body.arm_id is not None:
        arm = arm_in_school(session, who, body.arm_id)
        year = active_session(session)
    if body.department_id is not None:
        found(
            session.scalar(
                text("select id from departments where id = :d"), {"d": body.department_id}
            )
        )
    try:
        with session.begin_nested():
            student_id: uuid.UUID = session.scalar(
                text(
                    "insert into students (school_id, surname, first_name, other_names,"
                    " admission_number, gender, date_of_birth, house, department_id) values"
                    " (:s, :surname, :first_name, :other_names, :admission_number, :gender,"
                    " :date_of_birth, :house, :department_id) returning id"
                ),
                {"s": who.school_id, **body.model_dump(exclude={"arm_id"})},
            )
    except IntegrityError as error:
        if admission_taken(error):
            raise TAKEN from None
        raise
    if arm is not None and year is not None:
        enrol(session, who, student_id, arm, year)
    audit(
        session,
        who,
        "students.create",
        target=("students", student_id),
        new=body.model_dump(mode="json"),
    )
    return pupil_row(load_pupil(session, student_id))


@router.patch("/students/{student_id}", response_model=PupilRow)
def edit_pupil(student_id: uuid.UUID, body: EditPupil, who: Admin, session: DbSession) -> PupilRow:
    current = load_pupil(session, student_id)
    changes = {
        k: v for k, v in body.model_dump(exclude_unset=True).items() if getattr(current, k) != v
    }
    if "department_id" in changes and changes["department_id"] is not None:
        found(
            session.scalar(
                text("select id from departments where id = :d"), {"d": changes["department_id"]}
            )
        )
    if changes:
        assignments = ", ".join(f"{field} = :{field}" for field in changes)
        try:
            with session.begin_nested():
                session.execute(
                    text(f"update students set {assignments} where id = :id"),  # noqa: S608
                    {**changes, "id": student_id},
                )
        except IntegrityError as error:
            if admission_taken(error):
                raise TAKEN from None
            raise
        audit(
            session,
            who,
            "students.update",
            target=("students", student_id),
            old={k: getattr(current, k) for k in changes},
            new=changes,
        )
    return pupil_row(load_pupil(session, student_id))


def current_enrolment(session: Session, student_id: uuid.UUID) -> Any:
    return session.execute(
        text(
            "select e.id, e.arm_id from enrolments e join terms t on t.session_id = e.session_id"
            " and t.is_active where e.student_id = :p and e.left_on is null"
        ),
        {"p": student_id},
    ).first()


@router.post("/students/{student_id}/move", response_model=PupilRow)
def move_pupil(student_id: uuid.UUID, body: Move, who: Admin, session: DbSession) -> PupilRow:
    load_pupil(session, student_id)
    arm = arm_in_school(session, who, body.arm_id)
    year = active_session(session)
    current = current_enrolment(session, student_id)
    if current is not None and current.arm_id == arm:
        return pupil_row(load_pupil(session, student_id))
    if current is not None:
        session.execute(
            text("update enrolments set left_on = current_date where id = :e"), {"e": current.id}
        )
    enrol(session, who, student_id, arm, year)
    audit(
        session,
        who,
        "students.move",
        target=("students", student_id),
        old={"arm_id": current.arm_id if current else None},
        new={"arm_id": arm},
    )
    return pupil_row(load_pupil(session, student_id))


@router.put("/students/{student_id}/subjects", response_model=list[SubjectName])
def set_pupil_subjects(
    student_id: uuid.UUID, body: PupilSubjects, who: Admin, session: DbSession
) -> list[SubjectName]:
    load_pupil(session, student_id)
    enrolment = current_enrolment(session, student_id)
    if enrolment is None:
        raise ProblemError(409, "Enrol this pupil in an arm first.", code="not_enrolled")
    wanted = {
        found(session.scalar(text("select id from subjects where id = :s"), {"s": s}))
        for s in body.subject_ids
    }
    session.execute(
        text("delete from student_subjects where enrolment_id = :e"), {"e": enrolment.id}
    )
    for subject_id in wanted:
        session.execute(
            text(
                "insert into student_subjects (school_id, enrolment_id, subject_id)"
                " values (:s, :e, :subject)"
            ),
            {"s": who.school_id, "e": enrolment.id, "subject": subject_id},
        )
    audit(
        session,
        who,
        "students.subjects",
        target=("students", student_id),
        new={"subjects": sorted(map(str, wanted))},
    )
    return [
        SubjectName(id=str(r.id), name=r.name)
        for r in session.execute(
            text(
                "select s.id, s.name from student_subjects ss join subjects s"
                " on s.id = ss.subject_id where ss.enrolment_id = :e order by s.name"
            ),
            {"e": enrolment.id},
        )
    ]


@router.post("/students/{student_id}/login", status_code=201, response_model=TemporaryPassword)
def give_pupil_login(
    student_id: uuid.UUID, body: NewLogin, who: Admin, session: DbSession
) -> TemporaryPassword:
    current = load_pupil(session, student_id)
    if current.has_login:
        raise ProblemError(409, "This pupil already has a login.", code="already_has_login")
    user_id = uuid.uuid4()
    try:
        with session.begin_nested():
            session.execute(
                text(
                    "insert into users (id, full_name, username, student_school_id)"
                    " values (:id, :name, :username, :school)"
                ),
                {
                    "id": user_id,
                    "name": f"{current.first_name} {current.surname}",
                    "username": body.username,
                    "school": who.school_id,
                },
            )
    except IntegrityError:
        raise ProblemError(
            409, "This username is taken in this school.", code="username_taken"
        ) from None
    session.execute(
        text(
            "insert into school_memberships (user_id, school_id, role, status)"
            " values (:u, :s, 'student', 'active')"
        ),
        {"u": user_id, "s": who.school_id},
    )
    session.execute(
        text("update students set user_id = :u where id = :p"), {"u": user_id, "p": student_id}
    )
    password = issue_temporary_password(session, user_id)
    audit(
        session,
        who,
        "students.login",
        target=("students", student_id),
        new={"username": body.username},
    )
    return TemporaryPassword(temporary_password=password)


# --- CSV import (AC05.1) ----------------------------------------------------------------


@router.get("/students/import/template", response_class=PlainTextResponse)
def import_template(_: Admin) -> PlainTextResponse:
    return PlainTextResponse(",".join(CSV_COLUMNS) + "\n", media_type="text/csv")


def read_rows(raw: bytes) -> list[dict[str, str]]:
    if len(raw) > MAX_CSV_BYTES:
        raise ProblemError(413, "The file must be 1 MB or smaller.", code="file_too_large")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ProblemError(422, "Save the file as CSV (UTF-8).", code="csv_encoding") from None
    reader = csv.DictReader(io.StringIO(content))
    columns = [name.strip().lower() for name in (reader.fieldnames or [])]
    if sorted(columns) != sorted(CSV_COLUMNS):
        raise ProblemError(
            422,
            "Use the columns of the template: " + ", ".join(CSV_COLUMNS) + ".",
            code="csv_columns",
        )
    rows = [{k.strip().lower(): (v or "").strip() for k, v in row.items() if k} for row in reader]
    if len(rows) > MAX_ROWS:
        raise ProblemError(422, f"Import at most {MAX_ROWS} pupils at a time.", code="csv_rows")
    return rows


def check_rows(
    session: Session, rows: list[dict[str, str]]
) -> tuple[list[ImportRow], list[PupilFields]]:
    existing = {
        str(number).lower()
        for number in session.scalars(text("select admission_number from students"))
    }
    seen: dict[str, int] = {}
    previews: list[ImportRow] = []
    valid: list[PupilFields] = []
    for index, row in enumerate(rows, start=2):  # row 1 is the header
        errors: list[str] = []
        values = {k: (v or None) for k, v in row.items()}
        try:
            fields = PupilFields.model_validate(values)
        except ValidationError as error:
            fields = None
            errors.extend(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
        number = (row.get("admission_number") or "").lower()
        if number and number in existing:
            errors.append("Admission number already used in this school.")
        if number and number in seen:
            errors.append(f"Admission number appears twice in this file (row {seen[number]}).")
        seen.setdefault(number, index)
        previews.append(
            ImportRow(
                row=index,
                admission_number=row.get("admission_number", ""),
                surname=row.get("surname", ""),
                first_name=row.get("first_name", ""),
                errors=errors,
            )
        )
        if fields is not None and not errors:
            valid.append(fields)
    return previews, valid


@router.post("/students/import", response_model=None)
def import_pupils(
    file: Annotated[UploadFile, File()],
    arm_id: uuid.UUID,
    who: Admin,
    session: DbSession,
    response: Response,
    commit: bool = False,
) -> ImportPreview | Imported:
    arm = arm_in_school(session, who, arm_id)
    year = active_session(session)
    rows = read_rows(file.file.read(MAX_CSV_BYTES + 1))
    previews, valid = check_rows(session, rows)
    invalid = sum(1 for p in previews if p.errors)
    if not commit:
        return ImportPreview(rows=previews, valid=len(valid), invalid=invalid)
    if invalid or not valid:
        raise ProblemError(
            422, "Fix the rows with problems; nothing was saved.", code="import_has_errors"
        )
    for fields in valid:
        student_id: uuid.UUID = session.scalar(
            text(
                "insert into students (school_id, surname, first_name, other_names,"
                " admission_number, gender, date_of_birth, house) values (:s, :surname,"
                " :first_name, :other_names, :admission_number, :gender, :date_of_birth, :house)"
                " returning id"
            ),
            {"s": who.school_id, **fields.model_dump()},
        )
        enrol(session, who, student_id, arm, year)
    audit(session, who, "students.import", target=("class_arms", arm), new={"created": len(valid)})
    response.status_code = 201
    return Imported(created=len(valid))
