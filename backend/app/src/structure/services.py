"""The school's structure: /school (BUILD_PROMPT 9.2e, first part; SPEC F04, F08).

Sessions and terms, classes and arms, departments, subjects and the subjects
each arm takes. Everyone in the school reads; school admins change
(`school.settings`). The database works for the signed-in membership's school
only, so an id from another school is simply not found (404). Every change is
audited in the same transaction.
"""

import uuid
from datetime import date
from typing import Any

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import Principal, ensure_level_enabled
from app.core.errors import ProblemError
from app.src.schools.models import Level
from app.src.schools.services import audit, one_id, unique_name
from app.src.structure.schemas import (
    ArmRow,
    ArmSubjects,
    ClassRow,
    DepartmentRow,
    EditSubject,
    EditTerm,
    NewArm,
    NewClass,
    NewDepartment,
    NewSession,
    NewTerm,
    Rename,
    SessionRow,
    SubjectFields,
    SubjectRow,
    TermFields,
    TermRow,
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


def list_sessions(
    _: Principal,
    session: Session,
) -> list[SessionRow]:
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


def create_session(
    body: NewSession,
    who: Principal,
    session: Session,
) -> SessionRow:
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


def create_term(
    session_id: str,
    body: NewTerm,
    who: Principal,
    session: Session,
) -> TermRow:
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


def edit_term(
    term_id: str,
    body: EditTerm,
    who: Principal,
    session: Session,
) -> TermRow:
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


def activate_term(
    term_id: str,
    who: Principal,
    session: Session,
) -> TermRow:
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


def list_classes(
    _: Principal,
    session: Session,
) -> list[ClassRow]:
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


def create_class(
    body: NewClass,
    who: Principal,
    session: Session,
) -> ClassRow:
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


def rename_class(
    class_id: str,
    body: Rename,
    who: Principal,
    session: Session,
) -> ClassRow:
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


def delete_class(
    class_id: str,
    who: Principal,
    session: Session,
) -> None:
    row = load_class(session, class_id)
    session.execute(text("delete from classes where id = :id"), {"id": row.id})
    audit(
        session,
        who,
        "classes.delete",
        target=("classes", row.id),
        old={"level": row.level, "name": row.name},
    )


def create_arm(
    class_id: str,
    body: NewArm,
    who: Principal,
    session: Session,
) -> ArmRow:
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


def rename_arm(
    arm_id: str,
    body: NewArm,
    who: Principal,
    session: Session,
) -> ArmRow:
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


def delete_arm(
    arm_id: str,
    who: Principal,
    session: Session,
) -> None:
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


def set_arm_subjects(
    arm_id: str,
    body: ArmSubjects,
    who: Principal,
    session: Session,
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


def list_departments(
    _: Principal,
    session: Session,
) -> list[DepartmentRow]:
    return [
        DepartmentRow(id=str(r.id), name=r.name)
        for r in session.execute(text("select id, name from departments order by name"))
    ]


def create_department(
    body: NewDepartment,
    who: Principal,
    session: Session,
) -> DepartmentRow:
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


def rename_department(
    department_id: str,
    body: NewDepartment,
    who: Principal,
    session: Session,
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


def delete_department(
    department_id: str,
    who: Principal,
    session: Session,
) -> None:
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


def list_subjects(
    _: Principal,
    session: Session,
) -> list[SubjectRow]:
    return [subject_row(r) for r in session.execute(text(f"{SUBJECT_SELECT} order by name"))]


def department_or_none(session: Session, department_id: str | None) -> uuid.UUID | None:
    if department_id is None:
        return None
    return one_id(session, "select id from departments where id = :id", department_id)


def create_subject(
    body: SubjectFields,
    who: Principal,
    session: Session,
) -> SubjectRow:
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


def edit_subject(
    subject_id: str,
    body: EditSubject,
    who: Principal,
    session: Session,
) -> SubjectRow:
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


def delete_subject(
    subject_id: str,
    who: Principal,
    session: Session,
) -> None:
    wanted = one_id(session, "select id from subjects where id = :id", subject_id)
    session.execute(text("delete from subjects where id = :id"), {"id": wanted})
    audit(session, who, "subjects.delete", target=("subjects", wanted))
