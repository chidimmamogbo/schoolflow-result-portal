"""The school's own set-up: /school (BUILD_PROMPT 9.2e, first part; SPEC F04, F08, F25).

Settings and branding, the assessment mode and head's title per level,
sessions and terms, classes and arms, departments, subjects and the subjects
each arm takes. Everyone in the school reads; school admins change
(`school.settings`, `assessment_mode.configure`). The database works for the
signed-in membership's school only, so an id from another school is simply
not found (404). Every change is audited in the same transaction.
"""

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from schoolflow_api.audit.log import write_audit
from schoolflow_api.authz.deps import Principal, ensure_level_enabled, found, require
from schoolflow_api.core.deps import DbSession
from schoolflow_api.core.errors import ProblemError
from schoolflow_api.platform.schemas import SchoolDetails
from schoolflow_api.school.schemas import (
    ArmRow,
    ArmSubjects,
    ClassRow,
    DepartmentRow,
    EditSettings,
    EditSubject,
    EditTerm,
    LevelChange,
    LevelName,
    LevelResult,
    LevelRow,
    NewArm,
    NewClass,
    NewDepartment,
    NewSession,
    NewTerm,
    Rename,
    SchoolSettings,
    SessionRow,
    SubjectFields,
    SubjectRow,
    TermFields,
    TermRow,
)
from schoolflow_api.schools.models import Level

router = APIRouter(prefix="/school", tags=["school"])

Member = Annotated[Principal, Depends(require())]
Admin = Annotated[Principal, Depends(require("school.settings"))]

# Unique-name rules from migrations 6 (names compared without capitals).
NAME_RULES = frozenset(
    {
        "ix_classes_unique_name",
        "ix_class_arms_unique_name",
        "ix_departments_unique_name",
        "ix_subjects_unique_name",
        "uq_academic_sessions_school_id_name",
        "uq_terms_session_id_term_number",
    }
)


@contextmanager
def unique_name(session: Session) -> Generator[None]:
    """Turn a clash with an existing name into a clear 409 `name_taken`."""
    try:
        with session.begin_nested():
            yield
    except IntegrityError as error:
        original = error.orig
        rule = original.diag.constraint_name if isinstance(original, psycopg.Error) else None
        if rule in NAME_RULES:
            raise ProblemError(409, "This name is already used.", code="name_taken") from None
        raise


def audit(session: Session, who: Principal, action: str, **details: Any) -> None:
    write_audit(session, who.school_id, who.role.value, action, **details)


def one_id(session: Session, sql: str, row_id: object) -> uuid.UUID:
    """The id of a row this school can see, or 404."""
    try:
        wanted = uuid.UUID(str(row_id))
    except ValueError:
        raise ProblemError(404, "Not Found") from None
    return found(session.scalar(text(sql), {"id": wanted}))


# --- settings and levels -----------------------------------------------------------------


SETTINGS_FIELDS = ("email", "phone", "address", "city", "state", "country", "colour")


def settings_of(session: Session, school_id: uuid.UUID) -> SchoolSettings:
    row = session.execute(
        text(
            "select id, code, name, email, phone, address, city, state, country, colour"
            " from schools where id = :id"
        ),
        {"id": school_id},
    ).one()
    features = {
        str(r.feature): bool(r.enabled)
        for r in session.execute(text("select feature, enabled from school_features"))
    }
    order = [level.value for level in Level]
    levels = sorted(
        (
            LevelRow(
                level=r.level,
                enabled=r.enabled,
                assessment_mode=r.assessment_mode,
                head_title=r.head_title,
            )
            for r in session.execute(
                text("select level, enabled, assessment_mode, head_title from school_levels")
            )
        ),
        key=lambda level: order.index(level.level),
    )
    return SchoolSettings(
        id=str(row.id),
        code=row.code,
        name=row.name,
        email=row.email,
        phone=row.phone,
        address=row.address,
        city=row.city,
        state=row.state,
        country=row.country,
        colour=row.colour,
        features=features,
        levels=levels,
    )


@router.get("", response_model=SchoolSettings)
def get_settings(who: Member, session: DbSession) -> SchoolSettings:
    return settings_of(session, found(who.school_id))


@router.patch("", response_model=SchoolSettings)
def edit_settings(body: EditSettings, who: Admin, session: DbSession) -> SchoolSettings:
    school_id = found(who.school_id)
    current = settings_of(session, school_id).model_dump()
    wanted = {field: current[field] for field in ("name", *SETTINGS_FIELDS)}
    wanted.update(body.model_dump(exclude_none=True))
    try:
        SchoolDetails.model_validate(wanted)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from None
    changed = {f: wanted[f] for f in SETTINGS_FIELDS if wanted[f] != current[f]}
    if changed:
        assignments = ", ".join(f"{field} = :{field}" for field in changed)
        session.execute(
            text(f"update schools set {assignments} where id = :id"),  # noqa: S608 (fixed names)
            {**changed, "id": school_id},
        )
        audit(
            session,
            who,
            "school.update",
            target=("schools", school_id),
            old={f: current[f] for f in changed},
            new=changed,
        )
    return settings_of(session, school_id)


@router.put("/levels/{level}", response_model=LevelResult)
def change_level(
    level: LevelName, body: LevelChange, who: Admin, session: DbSession
) -> LevelResult:
    ensure_level_enabled(session, who, Level(level))
    if body.assessment_mode is not None and "assessment_mode.configure" not in who.permissions:
        raise ProblemError(403, "You don't have permission to do this.", code="permission_denied")
    current = session.execute(
        text("select assessment_mode, head_title from school_levels where level = :l"),
        {"l": level},
    ).one()
    changes = body.model_dump(exclude_none=True)
    applies_from = "this_term"
    if changes:
        assignments = ", ".join(f"{field} = :{field}" for field in changes)
        session.execute(
            text(f"update school_levels set {assignments} where level = :l"),  # noqa: S608
            {**changes, "l": level},
        )
    if body.assessment_mode is not None and body.assessment_mode != current.assessment_mode:
        # The active term's structure keeps the mode its entries started with (AC08.6).
        structure = session.execute(
            text(
                "select s.id, s.locked_at is not null as locked from assessment_structures s"
                " join terms t on t.id = s.term_id where t.is_active and s.level = :l"
            ),
            {"l": level},
        ).first()
        if structure is not None and structure.locked:
            applies_from = "next_term"
        elif structure is not None:
            session.execute(
                text("update assessment_structures set assessment_mode = :m where id = :id"),
                {"m": body.assessment_mode, "id": structure.id},
            )
    if changes:
        audit(
            session,
            who,
            "school_levels.update",
            target=("schools", found(who.school_id)),
            old={"level": level, **{f: getattr(current, f) for f in changes}},
            new={"level": level, **changes},
        )
    row = session.execute(
        text("select assessment_mode, head_title from school_levels where level = :l"),
        {"l": level},
    ).one()
    return LevelResult(
        level=level,
        assessment_mode=row.assessment_mode,
        head_title=row.head_title,
        applies_from=applies_from,
    )


# --- sessions and terms -------------------------------------------------------------------


def term_row(row: Any) -> TermRow:
    return TermRow(
        id=str(row.id),
        term_number=row.term_number,
        starts_on=row.starts_on,
        ends_on=row.ends_on,
        next_term_begins=row.next_term_begins,
        is_active=row.is_active,
    )


TERM_SELECT = (
    "select id, session_id, term_number, starts_on, ends_on, next_term_begins, is_active from terms"
)


@router.get("/sessions", response_model=list[SessionRow])
def list_sessions(_: Member, session: DbSession) -> list[SessionRow]:
    terms: dict[uuid.UUID, list[TermRow]] = {}
    for row in session.execute(text(f"{TERM_SELECT} order by term_number")):
        terms.setdefault(row.session_id, []).append(term_row(row))
    return [
        SessionRow(
            id=str(r.id),
            name=r.name,
            starts_on=r.starts_on,
            ends_on=r.ends_on,
            terms=terms.get(r.id, []),
        )
        for r in session.execute(
            text("select id, name, starts_on, ends_on from academic_sessions order by starts_on")
        )
    ]


@router.post("/sessions", status_code=201, response_model=SessionRow)
def create_session(body: NewSession, who: Admin, session: DbSession) -> SessionRow:
    overlapping = session.scalar(
        text(
            "select exists (select 1 from academic_sessions"
            " where starts_on <= :ends and ends_on >= :starts)"
        ),
        {"starts": body.starts_on, "ends": body.ends_on},
    )
    if overlapping:
        raise ProblemError(409, "This session overlaps another session.", code="sessions_overlap")
    with unique_name(session):
        session_id: uuid.UUID = session.scalar(
            text(
                "insert into academic_sessions (school_id, name, starts_on, ends_on)"
                " values (:school, :name, :starts, :ends) returning id"
            ),
            {
                "school": who.school_id,
                "name": body.name,
                "starts": body.starts_on,
                "ends": body.ends_on,
            },
        )
    audit(
        session,
        who,
        "sessions.create",
        target=("academic_sessions", session_id),
        new=body.model_dump(mode="json"),
    )
    return SessionRow(
        id=str(session_id), name=body.name, starts_on=body.starts_on, ends_on=body.ends_on, terms=[]
    )


def check_term_dates(
    session: Session,
    session_id: uuid.UUID,
    fields: TermFields,
    term_id: uuid.UUID | None = None,
) -> None:
    """Terms sit inside their session and never overlap each other (F04)."""
    year = session.execute(
        text("select starts_on, ends_on from academic_sessions where id = :id"),
        {"id": session_id},
    ).one()
    if fields.starts_on < year.starts_on or fields.ends_on > year.ends_on:
        raise ProblemError(
            422, "A term must fall inside its session's dates.", code="term_outside_session"
        )
    overlapping = session.scalar(
        text(
            "select exists (select 1 from terms where session_id = :session"
            " and id is distinct from :term and starts_on <= :ends and ends_on >= :starts)"
        ),
        {
            "session": session_id,
            "term": term_id,
            "starts": fields.starts_on,
            "ends": fields.ends_on,
        },
    )
    if overlapping:
        raise ProblemError(409, "This term overlaps another term.", code="terms_overlap")


@router.post("/sessions/{session_id}/terms", status_code=201, response_model=TermRow)
def create_term(session_id: str, body: NewTerm, who: Admin, session: DbSession) -> TermRow:
    year_id = one_id(session, "select id from academic_sessions where id = :id", session_id)
    check_term_dates(session, year_id, body)
    with unique_name(session):
        row = session.execute(
            text(
                "insert into terms (school_id, session_id, term_number, starts_on, ends_on,"
                " next_term_begins) values (:school, :session, :number, :starts, :ends, :next)"
                " returning id, term_number, starts_on, ends_on, next_term_begins, is_active"
            ),
            {
                "school": who.school_id,
                "session": year_id,
                "number": body.term_number,
                "starts": body.starts_on,
                "ends": body.ends_on,
                "next": body.next_term_begins,
            },
        ).one()
    audit(session, who, "terms.create", target=("terms", row.id), new=body.model_dump(mode="json"))
    return term_row(row)


def load_term(session: Session, term_id: str) -> Any:
    wanted = one_id(session, "select id from terms where id = :id", term_id)
    return session.execute(text(f"{TERM_SELECT} where id = :id"), {"id": wanted}).one()


@router.patch("/terms/{term_id}", response_model=TermRow)
def edit_term(term_id: str, body: EditTerm, who: Admin, session: DbSession) -> TermRow:
    row = load_term(session, term_id)
    current: dict[str, date | None] = {
        "starts_on": row.starts_on,
        "ends_on": row.ends_on,
        "next_term_begins": row.next_term_begins,
    }
    wanted = {**current, **body.model_dump(exclude_unset=True)}
    try:
        fields = TermFields.model_validate(wanted)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from None
    check_term_dates(session, row.session_id, fields, row.id)
    changed = {k: v for k, v in wanted.items() if current[k] != v}
    if changed:
        assignments = ", ".join(f"{field} = :{field}" for field in changed)
        session.execute(
            text(f"update terms set {assignments} where id = :id"),  # noqa: S608 (fixed names)
            {**changed, "id": row.id},
        )
        audit(
            session,
            who,
            "terms.update",
            target=("terms", row.id),
            old={k: current[k] for k in changed},
            new=changed,
        )
    return term_row(load_term(session, str(row.id)))


@router.post("/terms/{term_id}/activate", response_model=TermRow)
def activate_term(term_id: str, who: Admin, session: DbSession) -> TermRow:
    """AC04.1: activating a term deactivates the previous one."""
    row = load_term(session, term_id)
    previous = session.scalar(text("select id from terms where is_active"))
    if previous != row.id:
        session.execute(text("update terms set is_active = false where is_active"))
        session.execute(text("update terms set is_active = true where id = :id"), {"id": row.id})
        audit(
            session,
            who,
            "terms.activate",
            target=("terms", row.id),
            old={"active_term": previous},
            new={"active_term": row.id},
        )
    return term_row(load_term(session, str(row.id)))


# --- classes and arms -----------------------------------------------------------------------


@router.get("/classes", response_model=list[ClassRow])
def list_classes(_: Member, session: DbSession) -> list[ClassRow]:
    arms: dict[uuid.UUID, list[ArmRow]] = {}
    for row in session.execute(text("select id, class_id, name from class_arms order by name")):
        arms.setdefault(row.class_id, []).append(ArmRow(id=str(row.id), name=row.name))
    order = [level.value for level in Level]
    rows = sorted(
        session.execute(text("select id, level, name from classes")),
        key=lambda r: (order.index(r.level), r.name),
    )
    return [
        ClassRow(id=str(r.id), level=r.level, name=r.name, arms=arms.get(r.id, [])) for r in rows
    ]


@router.post("/classes", status_code=201, response_model=ClassRow)
def create_class(body: NewClass, who: Admin, session: DbSession) -> ClassRow:
    ensure_level_enabled(session, who, Level(body.level))
    with unique_name(session):
        class_id: uuid.UUID = session.scalar(
            text("insert into classes (school_id, level, name) values (:s, :l, :n) returning id"),
            {"s": who.school_id, "l": body.level, "n": body.name},
        )
    audit(
        session,
        who,
        "classes.create",
        target=("classes", class_id),
        new={"level": body.level, "name": body.name},
    )
    return ClassRow(id=str(class_id), level=body.level, name=body.name, arms=[])


def load_class(session: Session, class_id: str) -> Any:
    wanted = one_id(session, "select id from classes where id = :id", class_id)
    return session.execute(
        text("select id, level, name from classes where id = :id"), {"id": wanted}
    ).one()


@router.patch("/classes/{class_id}", response_model=ClassRow)
def rename_class(class_id: str, body: Rename, who: Admin, session: DbSession) -> ClassRow:
    row = load_class(session, class_id)
    if body.name != row.name:
        with unique_name(session):
            session.execute(
                text("update classes set name = :n where id = :id"), {"n": body.name, "id": row.id}
            )
        audit(
            session,
            who,
            "classes.update",
            target=("classes", row.id),
            old={"name": row.name},
            new={"name": body.name},
        )
    arms = [
        ArmRow(id=str(a.id), name=a.name)
        for a in session.execute(
            text("select id, name from class_arms where class_id = :id order by name"),
            {"id": row.id},
        )
    ]
    return ClassRow(id=str(row.id), level=row.level, name=body.name, arms=arms)


@router.delete("/classes/{class_id}", status_code=204)
def delete_class(class_id: str, who: Admin, session: DbSession) -> None:
    row = load_class(session, class_id)
    session.execute(text("delete from classes where id = :id"), {"id": row.id})
    audit(
        session,
        who,
        "classes.delete",
        target=("classes", row.id),
        old={"level": row.level, "name": row.name},
    )


@router.post("/classes/{class_id}/arms", status_code=201, response_model=ArmRow)
def create_arm(class_id: str, body: NewArm, who: Admin, session: DbSession) -> ArmRow:
    row = load_class(session, class_id)
    with unique_name(session):
        arm_id: uuid.UUID = session.scalar(
            text(
                "insert into class_arms (school_id, class_id, name) values (:s, :c, :n)"
                " returning id"
            ),
            {"s": who.school_id, "c": row.id, "n": body.name},
        )
    audit(
        session,
        who,
        "class_arms.create",
        target=("class_arms", arm_id),
        new={"class": row.name, "name": body.name},
    )
    return ArmRow(id=str(arm_id), name=body.name)


def load_arm(session: Session, arm_id: str) -> Any:
    wanted = one_id(session, "select id from class_arms where id = :id", arm_id)
    return session.execute(
        text("select id, class_id, name from class_arms where id = :id"), {"id": wanted}
    ).one()


@router.patch("/arms/{arm_id}", response_model=ArmRow)
def rename_arm(arm_id: str, body: NewArm, who: Admin, session: DbSession) -> ArmRow:
    row = load_arm(session, arm_id)
    if body.name != row.name:
        with unique_name(session):
            session.execute(
                text("update class_arms set name = :n where id = :id"),
                {"n": body.name, "id": row.id},
            )
        audit(
            session,
            who,
            "class_arms.update",
            target=("class_arms", row.id),
            old={"name": row.name},
            new={"name": body.name},
        )
    return ArmRow(id=str(row.id), name=body.name)


@router.delete("/arms/{arm_id}", status_code=204)
def delete_arm(arm_id: str, who: Admin, session: DbSession) -> None:
    row = load_arm(session, arm_id)
    session.execute(text("delete from class_arms where id = :id"), {"id": row.id})
    audit(session, who, "class_arms.delete", target=("class_arms", row.id), old={"name": row.name})


def subjects_of_arm(session: Session, arm_id: uuid.UUID) -> list[SubjectRow]:
    return [
        SubjectRow(
            id=str(r.id),
            name=r.name,
            department_id=str(r.department_id) if r.department_id else None,
            category=r.category,
        )
        for r in session.execute(
            text(
                "select s.id, s.name, s.department_id, s.category from arm_subjects a"
                " join subjects s on s.id = a.subject_id where a.arm_id = :arm order by s.name"
            ),
            {"arm": arm_id},
        )
    ]


@router.put("/arms/{arm_id}/subjects", response_model=list[SubjectRow])
def set_arm_subjects(
    arm_id: str, body: ArmSubjects, who: Admin, session: DbSession
) -> list[SubjectRow]:
    arm = load_arm(session, arm_id)
    wanted = {
        one_id(session, "select id from subjects where id = :id", s) for s in body.subject_ids
    }
    current = set(
        session.scalars(
            text("select subject_id from arm_subjects where arm_id = :arm"), {"arm": arm.id}
        )
    )
    for subject_id in current - wanted:
        session.execute(
            text("delete from arm_subjects where arm_id = :arm and subject_id = :s"),
            {"arm": arm.id, "s": subject_id},
        )
    for subject_id in wanted - current:
        session.execute(
            text(
                "insert into arm_subjects (school_id, arm_id, subject_id)"
                " values (:school, :arm, :s)"
            ),
            {"school": who.school_id, "arm": arm.id, "s": subject_id},
        )
    if wanted != current:
        audit(
            session,
            who,
            "arm_subjects.update",
            target=("class_arms", arm.id),
            old={"subjects": sorted(map(str, current))},
            new={"subjects": sorted(map(str, wanted))},
        )
    return subjects_of_arm(session, arm.id)


# --- departments and subjects ----------------------------------------------------------------


@router.get("/departments", response_model=list[DepartmentRow])
def list_departments(_: Member, session: DbSession) -> list[DepartmentRow]:
    return [
        DepartmentRow(id=str(r.id), name=r.name)
        for r in session.execute(text("select id, name from departments order by name"))
    ]


@router.post("/departments", status_code=201, response_model=DepartmentRow)
def create_department(body: NewDepartment, who: Admin, session: DbSession) -> DepartmentRow:
    with unique_name(session):
        department_id: uuid.UUID = session.scalar(
            text("insert into departments (school_id, name) values (:s, :n) returning id"),
            {"s": who.school_id, "n": body.name},
        )
    audit(
        session,
        who,
        "departments.create",
        target=("departments", department_id),
        new={"name": body.name},
    )
    return DepartmentRow(id=str(department_id), name=body.name)


@router.patch("/departments/{department_id}", response_model=DepartmentRow)
def rename_department(
    department_id: str, body: NewDepartment, who: Admin, session: DbSession
) -> DepartmentRow:
    wanted = one_id(session, "select id from departments where id = :id", department_id)
    old = session.scalar(text("select name from departments where id = :id"), {"id": wanted})
    if body.name != old:
        with unique_name(session):
            session.execute(
                text("update departments set name = :n where id = :id"),
                {"n": body.name, "id": wanted},
            )
        audit(
            session,
            who,
            "departments.update",
            target=("departments", wanted),
            old={"name": old},
            new={"name": body.name},
        )
    return DepartmentRow(id=str(wanted), name=body.name)


@router.delete("/departments/{department_id}", status_code=204)
def delete_department(department_id: str, who: Admin, session: DbSession) -> None:
    wanted = one_id(session, "select id from departments where id = :id", department_id)
    session.execute(text("delete from departments where id = :id"), {"id": wanted})
    audit(session, who, "departments.delete", target=("departments", wanted))


SUBJECT_SELECT = "select id, name, department_id, category from subjects"


def subject_row(r: Any) -> SubjectRow:
    return SubjectRow(
        id=str(r.id),
        name=r.name,
        department_id=str(r.department_id) if r.department_id else None,
        category=r.category,
    )


@router.get("/subjects", response_model=list[SubjectRow])
def list_subjects(_: Member, session: DbSession) -> list[SubjectRow]:
    return [subject_row(r) for r in session.execute(text(f"{SUBJECT_SELECT} order by name"))]


def department_or_none(session: Session, department_id: str | None) -> uuid.UUID | None:
    if department_id is None:
        return None
    return one_id(session, "select id from departments where id = :id", department_id)


@router.post("/subjects", status_code=201, response_model=SubjectRow)
def create_subject(body: SubjectFields, who: Admin, session: DbSession) -> SubjectRow:
    department = department_or_none(session, body.department_id)
    with unique_name(session):
        row = session.execute(
            text(
                "insert into subjects (school_id, name, department_id, category)"
                " values (:s, :n, :d, :c) returning id, name, department_id, category"
            ),
            {"s": who.school_id, "n": body.name, "d": department, "c": body.category},
        ).one()
    audit(session, who, "subjects.create", target=("subjects", row.id), new=body.model_dump())
    return subject_row(row)


@router.patch("/subjects/{subject_id}", response_model=SubjectRow)
def edit_subject(subject_id: str, body: EditSubject, who: Admin, session: DbSession) -> SubjectRow:
    wanted = one_id(session, "select id from subjects where id = :id", subject_id)
    current = session.execute(text(f"{SUBJECT_SELECT} where id = :id"), {"id": wanted}).one()
    changes = body.model_dump(exclude_unset=True)
    if "department_id" in changes:
        changes["department_id"] = department_or_none(session, changes["department_id"])
    if changes:
        assignments = ", ".join(f"{field} = :{field}" for field in changes)
        with unique_name(session):
            session.execute(
                text(f"update subjects set {assignments} where id = :id"),  # noqa: S608
                {**changes, "id": wanted},
            )
        audit(
            session,
            who,
            "subjects.update",
            target=("subjects", wanted),
            old={f: getattr(current, f) for f in changes},
            new=changes,
        )
    return subject_row(
        session.execute(text(f"{SUBJECT_SELECT} where id = :id"), {"id": wanted}).one()
    )


@router.delete("/subjects/{subject_id}", status_code=204)
def delete_subject(subject_id: str, who: Admin, session: DbSession) -> None:
    wanted = one_id(session, "select id from subjects where id = :id", subject_id)
    session.execute(text("delete from subjects where id = :id"), {"id": wanted})
    audit(session, who, "subjects.delete", target=("subjects", wanted))
