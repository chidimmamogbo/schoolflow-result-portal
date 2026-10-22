"""My class: the form teacher's tools (BUILD_PROMPT 9.2h2; SPEC F22; D-146, D-148, D-169).

The arm's form (class) teacher and its assistants work here; school admins
read it and return submitted sections. Everyone else is told My class is not
for them (403) or, for another arm, that it is not found (404).

- The broadsheet: every pupil against every subject, with each sheet's status
  and the results engine's totals, average and position (F22 rule 2); for a
  Skill ratings level, each learning area's rating sheet status (rule 7).
- Times school opened (once for the class), and for each pupil a comment
  (suggestions come from the remark band of their average), trait ratings on
  the school's 1 to 5 key and times present (rule 5: absent is worked out).
- A preview of a pupil's report data, marked "Preview, not published".
- Submitting the sections (the form teacher only, never an assistant) locks
  them; a school admin returns them with a comment. The database enforces the
  moves, locks and limits too (migration 14).
"""

import uuid
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import Field, StringConstraints
from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.audit.log import write_audit
from schoolflow_api.authz.deps import (
    Principal,
    ensure_level_enabled,
    found,
    require,
    require_status,
)
from schoolflow_api.authz.permissions import Role
from schoolflow_api.core.deps import DbSession
from schoolflow_api.core.errors import ProblemError
from schoolflow_api.core.schemas import ApiModel
from schoolflow_api.grading.setup import ensure_defaults
from schoolflow_api.results.engine import ClassResult, Column, compute_class, grade_for
from schoolflow_api.results.sheets import active_term
from schoolflow_api.school.grading import Band
from schoolflow_api.schools.models import Feature, Level

router = APIRouter(tags=["form class"])

Results = Annotated[Principal, Depends(require(feature=Feature.RESULTS))]
Admins = Annotated[Principal, Depends(require("sheets.approve", feature=Feature.RESULTS))]
Comment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
ReturnComment = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]
PREVIEW_LABEL = "Preview, not published"
EDITABLE = {"open", "returned"}
Place = Literal["form_teacher", "assistant", "admin"]


# --- shapes -------------------------------------------------------------------------------


class MyClass(ApiModel):
    arm_id: str
    class_name: str
    level: str
    status: str
    revision: int
    can_submit: bool


class TraitOut(ApiModel):
    id: str
    name: str
    domain: str


class PupilEntry(ApiModel):
    enrolment_id: str
    admission_number: str
    surname: str
    first_name: str
    comment: str | None
    times_present: int | None
    times_absent: int | None
    ratings: dict[str, int]
    average: Decimal | None
    suggested_comments: list[str]


class EntryCounts(ApiModel):
    pupils: int
    with_comment: int
    with_attendance: int


class ClassView(ApiModel):
    arm_id: str
    class_name: str
    level: str
    term_id: str
    status: str
    revision: int
    status_comment: str | None
    times_school_opened: int | None
    can_edit: bool
    can_submit: bool
    traits: list[TraitOut]
    key: dict[str, str]
    pupils: list[PupilEntry]
    counts: EntryCounts


class BroadsheetSubject(ApiModel):
    id: str
    name: str
    sheet_id: str | None
    status: str


class BroadsheetRow(ApiModel):
    enrolment_id: str
    admission_number: str
    surname: str
    first_name: str
    totals: dict[str, int | None]
    average: Decimal | None
    position: int | None


class Broadsheet(ApiModel):
    kind: Literal["scores", "ratings"]
    subjects: list[BroadsheetSubject]
    rows: list[BroadsheetRow]
    class_average: Decimal | None


class AttendanceDays(ApiModel):
    times_school_opened: Annotated[int, Field(ge=1, le=366)]


class EntryIn(ApiModel):
    comment: Comment | None = None
    times_present: Annotated[int, Field(ge=0, le=366)] | None = None
    ratings: dict[uuid.UUID, Annotated[int, Field(ge=1, le=5)] | None] | None = None


class SectionMove(ApiModel):
    arm_id: str
    status: str
    revision: int
    status_comment: str | None


class ReturnBody(ApiModel):
    comment: ReturnComment


class PreviewSubject(ApiModel):
    name: str
    total: int | None
    grade: str | None


class PreviewTrait(ApiModel):
    name: str
    domain: str
    value: int | None


class Attendance(ApiModel):
    times_school_opened: int | None
    times_present: int | None
    times_absent: int | None


class Preview(ApiModel):
    label: str
    school_name: str
    class_name: str
    pupil_name: str
    admission_number: str
    subjects: list[PreviewSubject]
    average: Decimal | None
    position: int | None
    comment: str | None
    traits: list[PreviewTrait]
    attendance: Attendance


# --- where am I in this class ---------------------------------------------------------------


ARM_SELECT = (
    "select a.id, c.level, c.name || a.name as class_name from class_arms a"
    " join classes c on c.id = a.class_id"
)


def place_in(session: Session, who: Principal, arm_id: uuid.UUID) -> tuple[Any, Place]:
    arm = found(session.execute(text(f"{ARM_SELECT} where a.id = :a"), {"a": arm_id}).first())
    form = session.scalar(
        text(
            "select exists (select 1 from teacher_assignments where arm_id = :a"
            " and teacher_id = :u and is_form_teacher)"
        ),
        {"a": arm_id, "u": who.user_id},
    )
    assists = session.scalar(
        text(
            "select exists (select 1 from class_assistants where arm_id = :a and assistant_id = :u)"
        ),
        {"a": arm_id, "u": who.user_id},
    )
    place: Place
    if form:
        place = "form_teacher"
    elif assists:
        place = "assistant"
    elif who.role is Role.SCHOOL_ADMIN:
        place = "admin"
    else:
        raise ProblemError(404, "Not Found")
    ensure_level_enabled(session, who, Level(arm.level))
    return arm, place


def section_of(session: Session, arm_id: uuid.UUID, term_id: uuid.UUID) -> Any:
    return session.execute(
        text(
            "select id, status, revision, status_comment, times_school_opened"
            " from class_report_sections where arm_id = :a and term_id = :t"
        ),
        {"a": arm_id, "t": term_id},
    ).first()


def ensure_section(session: Session, who: Principal, arm_id: uuid.UUID, term_id: uuid.UUID) -> Any:
    section = section_of(session, arm_id, term_id)
    if section is None:
        session.execute(
            text(
                "insert into class_report_sections (school_id, term_id, arm_id) values (:s, :t, :a)"
            ),
            {"s": who.school_id, "t": term_id, "a": arm_id},
        )
        section = section_of(session, arm_id, term_id)
    return section


@router.get("/form-class", response_model=list[MyClass])
def my_classes(who: Results, session: DbSession) -> list[MyClass]:
    term = active_term(session)
    rows = session.execute(
        text(
            "select a.id, c.level, c.name || a.name as class_name,"
            " exists (select 1 from teacher_assignments t where t.arm_id = a.id"
            "   and t.teacher_id = :u and t.is_form_teacher) as form,"
            " s.status, s.revision"
            " from class_arms a join classes c on c.id = a.class_id"
            " join school_levels l on l.level = c.level and l.enabled"
            " left join class_report_sections s on s.arm_id = a.id and s.term_id = :t"
            " where exists (select 1 from teacher_assignments t where t.arm_id = a.id"
            "   and t.teacher_id = :u and t.is_form_teacher)"
            " or exists (select 1 from class_assistants x where x.arm_id = a.id"
            "   and x.assistant_id = :u)"
            " order by c.name, a.name"
        ),
        {"u": who.user_id, "t": term.id},
    ).all()
    if not rows:
        raise ProblemError(
            403, "My class is for form teachers and their assistants.", code="not_form_teacher"
        )
    return [
        MyClass(
            arm_id=str(r.id),
            class_name=r.class_name,
            level=r.level,
            status=r.status or "open",
            revision=r.revision or 1,
            can_submit=r.form,
        )
        for r in rows
    ]


# --- results for the class ----------------------------------------------------------------------


def pupils_of(session: Session, arm_id: uuid.UUID, session_id: uuid.UUID) -> list[Any]:
    return list(
        session.execute(
            text(
                "select e.id as enrolment_id, p.admission_number, p.surname, p.first_name"
                " from enrolments e join students p on p.id = e.student_id"
                " where e.arm_id = :a and e.session_id = :y and e.left_on is null"
                " order by p.surname, p.first_name, p.admission_number"
            ),
            {"a": arm_id, "y": session_id},
        )
    )


def bands_of(session: Session, table: str, level: str) -> list[Any]:
    return list(
        session.execute(
            text(f"select * from {table} where level = :l order by min_score desc"),  # noqa: S608 (fixed names)
            {"l": level},
        )
    )


def class_results(session: Session, who: Principal, arm: Any, term: Any) -> ClassResult | None:
    """The engine's results over the arm's score sheets this term (None for Skill ratings)."""
    mode = session.scalar(
        text("select assessment_mode from school_levels where level = :l"), {"l": arm.level}
    )
    structure = session.scalar(
        text("select id from assessment_structures where level = :l and term_id = :t"),
        {"l": arm.level, "t": term.id},
    )
    if mode != "scores" or structure is None:
        return None
    columns = [
        Column(str(r.id), r.label, r.max_score)
        for r in session.execute(
            text(
                "select id, label, max_score from assessment_components where structure_id = :s"
                " order by position"
            ),
            {"s": structure},
        )
    ]
    if sum(c.max_score for c in columns) != 100:
        return None
    sheets: dict[str, dict[str, dict[str, int | None]]] = {}
    for r in session.execute(
        text(
            "select ss.subject_id, e.id as enrolment_id from enrolments e"
            " join student_subjects ss on ss.enrolment_id = e.id"
            " where e.arm_id = :a and e.session_id = :y and e.left_on is null"
        ),
        {"a": arm.id, "y": term.session_id},
    ):
        sheets.setdefault(str(r.subject_id), {})[str(r.enrolment_id)] = {}
    for r in session.execute(
        text(
            "select r.subject_id, sc.enrolment_id, sc.component_id, sc.value from scores sc"
            " join result_sheets r on r.id = sc.sheet_id"
            " where r.arm_id = :a and r.term_id = :t and r.subject_id is not null"
        ),
        {"a": arm.id, "t": term.id},
    ):
        pupil = sheets.get(str(r.subject_id), {}).get(str(r.enrolment_id))
        if pupil is not None:
            pupil[str(r.component_id)] = r.value
    ensure_defaults(session, found(who.school_id), who.role.value)
    bands = [
        Band(grade=b.grade, min_score=b.min_score, max_score=b.max_score, remark=b.remark)
        for b in bands_of(session, "grade_bands", arm.level)
    ]
    pass_mark = int(session.scalar(text("select pass_mark from school_settings")) or 40)
    return compute_class(sheets, columns, bands, pass_mark=pass_mark)


def suggestions(remarks: list[Any], average: Decimal | None) -> list[str]:
    if average is None:
        return []
    for band in remarks:
        if band.min_score <= average < band.max_score + 1:
            return list(band.comments)
    return []


# --- the class view ---------------------------------------------------------------------------


def traits_of(session: Session) -> list[TraitOut]:
    return [
        TraitOut(id=str(r.id), name=r.name, domain=r.domain)
        for r in session.execute(
            text(
                "select id, name, domain from rating_traits where is_active"
                " order by domain, position, name"
            )
        )
    ]


def entries_of(
    session: Session, section_id: uuid.UUID | None
) -> tuple[dict[str, Any], dict[str, dict[str, int]]]:
    if section_id is None:
        return {}, {}
    entries = {
        str(r.enrolment_id): r
        for r in session.execute(
            text(
                "select id, enrolment_id, form_teacher_comment, times_present"
                " from student_term_entries where section_id = :s"
            ),
            {"s": section_id},
        )
    }
    ratings: dict[str, dict[str, int]] = {}
    for r in session.execute(
        text(
            "select e.enrolment_id, t.trait_id, t.value from student_trait_ratings t"
            " join student_term_entries e on e.id = t.entry_id where e.section_id = :s"
        ),
        {"s": section_id},
    ):
        ratings.setdefault(str(r.enrolment_id), {})[str(r.trait_id)] = r.value
    return entries, ratings


def pupil_entry(
    pupil: Any,
    entry: Any,
    ratings: dict[str, int],
    opened: int | None,
    average: Decimal | None,
    remarks: list[Any],
) -> PupilEntry:
    present = entry.times_present if entry else None
    return PupilEntry(
        enrolment_id=str(pupil.enrolment_id),
        admission_number=pupil.admission_number,
        surname=pupil.surname,
        first_name=pupil.first_name,
        comment=entry.form_teacher_comment if entry else None,
        times_present=present,
        times_absent=opened - present if opened is not None and present is not None else None,
        ratings=ratings,
        average=average,
        suggested_comments=suggestions(remarks, average),
    )


def class_view(session: Session, who: Principal, arm: Any, place: Place) -> ClassView:
    term = active_term(session)
    section = section_of(session, arm.id, term.id)
    entries, ratings = entries_of(session, section.id if section else None)
    results = class_results(session, who, arm, term)
    remarks = bands_of(session, "remark_bands", arm.level)
    opened = section.times_school_opened if section else None
    pupils = [
        pupil_entry(
            p,
            entries.get(str(p.enrolment_id)),
            ratings.get(str(p.enrolment_id), {}),
            opened,
            results.pupils[str(p.enrolment_id)].average
            if results and str(p.enrolment_id) in results.pupils
            else None,
            remarks,
        )
        for p in pupils_of(session, arm.id, term.session_id)
    ]
    status = section.status if section else "open"
    key = {
        str(r.value): r.label
        for r in session.execute(
            text("select value, label from trait_scale_points order by value desc")
        )
    }
    return ClassView(
        arm_id=str(arm.id),
        class_name=arm.class_name,
        level=arm.level,
        term_id=str(term.id),
        status=status,
        revision=section.revision if section else 1,
        status_comment=section.status_comment if section else None,
        times_school_opened=opened,
        can_edit=place != "admin" and status in EDITABLE,
        can_submit=place == "form_teacher" and status in EDITABLE,
        traits=traits_of(session),
        key=key,
        pupils=pupils,
        counts=EntryCounts(
            pupils=len(pupils),
            with_comment=sum(1 for p in pupils if p.comment),
            with_attendance=sum(1 for p in pupils if p.times_present is not None),
        ),
    )


@router.get("/form-class/{arm_id}", response_model=ClassView)
def get_class(arm_id: uuid.UUID, who: Results, session: DbSession) -> ClassView:
    arm, place = place_in(session, who, arm_id)
    ensure_defaults(session, found(who.school_id), who.role.value)
    return class_view(session, who, arm, place)


@router.get("/form-class/{arm_id}/broadsheet", response_model=Broadsheet)
def broadsheet(arm_id: uuid.UUID, who: Results, session: DbSession) -> Broadsheet:
    arm, _ = place_in(session, who, arm_id)
    term = active_term(session)
    mode = session.scalar(
        text("select assessment_mode from school_levels where level = :l"), {"l": arm.level}
    )
    if mode == "skill_ratings":
        areas = session.execute(
            text(
                "select la.id, la.name, r.id as sheet_id, r.status from class_arms a"
                " join class_learning_areas cla on cla.class_id = a.class_id"
                " join learning_areas la on la.id = cla.learning_area_id"
                " left join result_sheets r on r.arm_id = a.id and r.learning_area_id = la.id"
                "   and r.term_id = :t where a.id = :a order by la.position, la.name"
            ),
            {"a": arm_id, "t": term.id},
        )
        subjects = [
            BroadsheetSubject(
                id=str(r.id),
                name=r.name,
                sheet_id=str(r.sheet_id) if r.sheet_id else None,
                status=r.status or "not_started",
            )
            for r in areas
        ]
        rows = [
            BroadsheetRow(
                enrolment_id=str(p.enrolment_id),
                admission_number=p.admission_number,
                surname=p.surname,
                first_name=p.first_name,
                totals={},
                average=None,
                position=None,
            )
            for p in pupils_of(session, arm_id, term.session_id)
        ]
        return Broadsheet(kind="ratings", subjects=subjects, rows=rows, class_average=None)
    subject_rows = session.execute(
        text(
            "select s.id, s.name, r.id as sheet_id, r.status from arm_subjects x"
            " join subjects s on s.id = x.subject_id"
            " left join result_sheets r on r.arm_id = x.arm_id and r.subject_id = s.id"
            "   and r.term_id = :t where x.arm_id = :a order by s.name"
        ),
        {"a": arm_id, "t": term.id},
    ).all()
    results = class_results(session, who, arm, term)
    rows: list[BroadsheetRow] = []
    for p in pupils_of(session, arm_id, term.session_id):
        key = str(p.enrolment_id)
        totals: dict[str, int | None] = {}
        for s in subject_rows:
            subject = results.subjects.get(str(s.id)) if results else None
            row = subject.pupils.get(key) if subject else None
            totals[str(s.id)] = row.total if row else None
        overall = results.pupils.get(key) if results else None
        rows.append(
            BroadsheetRow(
                enrolment_id=key,
                admission_number=p.admission_number,
                surname=p.surname,
                first_name=p.first_name,
                totals=totals,
                average=overall.average if overall else None,
                position=overall.position if overall else None,
            )
        )
    return Broadsheet(
        kind="scores",
        subjects=[
            BroadsheetSubject(
                id=str(s.id),
                name=s.name,
                sheet_id=str(s.sheet_id) if s.sheet_id else None,
                status=s.status or "not_started",
            )
            for s in subject_rows
        ],
        rows=rows,
        class_average=results.class_average if results else None,
    )


# --- entries ----------------------------------------------------------------------------------


def editor(session: Session, who: Principal, arm_id: uuid.UUID) -> tuple[Any, Any, Any]:
    arm, place = place_in(session, who, arm_id)
    if place == "admin":
        raise ProblemError(
            403, "School admins read My class; the class's teachers enter.", code="not_assigned"
        )
    term = active_term(session)
    return arm, term, ensure_section(session, who, arm_id, term.id)


@router.put("/form-class/{arm_id}/attendance-days", response_model=AttendanceDays)
def set_attendance_days(
    arm_id: uuid.UUID, body: AttendanceDays, who: Results, session: DbSession
) -> AttendanceDays:
    _, _, section = editor(session, who, arm_id)
    most = session.scalar(
        text("select max(times_present) from student_term_entries where section_id = :s"),
        {"s": section.id},
    )
    if most is not None and body.times_school_opened < most:
        raise ProblemError(
            422,
            "Times school opened cannot be less than a pupil's times present.",
            code="opened_below_present",
        )
    session.execute(
        text("update class_report_sections set times_school_opened = :o where id = :s"),
        {"o": body.times_school_opened, "s": section.id},
    )
    write_audit(
        session,
        who.school_id,
        who.role.value,
        "form_class.attendance_days",
        target=("class_report_sections", section.id),
        old={"times_school_opened": section.times_school_opened},
        new={"times_school_opened": body.times_school_opened},
    )
    return body


@router.put("/form-class/{arm_id}/students/{enrolment_id}/entry", response_model=PupilEntry)
def save_entry(
    arm_id: uuid.UUID, enrolment_id: uuid.UUID, body: EntryIn, who: Results, session: DbSession
) -> PupilEntry:
    _, term, section = editor(session, who, arm_id)
    pupil = found(
        next(
            (
                p
                for p in pupils_of(session, arm_id, term.session_id)
                if p.enrolment_id == enrolment_id
            ),
            None,
        )
    )
    changes = body.model_dump(exclude_unset=True)
    if "times_present" in changes and body.times_present is not None:
        opened = section.times_school_opened
        if opened is None or body.times_present > opened:
            raise ProblemError(
                422,
                "Times present cannot be more than times school opened.",
                code="present_over_opened",
            )
    active = {uuid.UUID(t.id) for t in traits_of(session)}
    if body.ratings and any(trait not in active for trait in body.ratings):
        raise ProblemError(422, "Rate only the school's active traits.", code="unknown_trait")
    entries, _ = entries_of(session, section.id)
    current = entries.get(str(enrolment_id))
    fields = {"comment": "form_teacher_comment", "times_present": "times_present"}
    values = {fields[k]: v for k, v in changes.items() if k in fields}
    if current is None:
        entry_id = session.scalar(
            text(
                "insert into student_term_entries (school_id, section_id, enrolment_id,"
                " form_teacher_comment, times_present) values (:s, :sec, :e, :c, :p)"
                " returning id"
            ),
            {
                "s": who.school_id,
                "sec": section.id,
                "e": enrolment_id,
                "c": values.get("form_teacher_comment"),
                "p": values.get("times_present"),
            },
        )
    else:
        entry_id = current.id
        if values:
            assignments = ", ".join(f"{column} = :{column}" for column in values)
            session.execute(
                text(f"update student_term_entries set {assignments} where id = :id"),  # noqa: S608
                {**values, "id": entry_id},
            )
    for trait, value in (body.ratings or {}).items():
        existing = session.scalar(
            text("select value from student_trait_ratings where entry_id = :e and trait_id = :t"),
            {"e": entry_id, "t": trait},
        )
        if value is None and existing is not None:
            session.execute(
                text("delete from student_trait_ratings where entry_id = :e and trait_id = :t"),
                {"e": entry_id, "t": trait},
            )
        elif value is not None and existing is None:
            session.execute(
                text(
                    "insert into student_trait_ratings (school_id, entry_id, trait_id, value)"
                    " values (:s, :e, :t, :v)"
                ),
                {"s": who.school_id, "e": entry_id, "t": trait, "v": value},
            )
        elif value is not None and existing != value:
            session.execute(
                text(
                    "update student_trait_ratings set value = :v where entry_id = :e"
                    " and trait_id = :t"
                ),
                {"v": value, "e": entry_id, "t": trait},
            )
    write_audit(
        session,
        who.school_id,
        who.role.value,
        "form_class.entry",
        target=("student_term_entries", entry_id),
        new={k: v for k, v in changes.items() if k != "ratings"}
        | {"ratings": len(body.ratings or {})},
    )
    entries, ratings = entries_of(session, section.id)
    refreshed = section_of(session, arm_id, term.id)
    return pupil_entry(
        pupil,
        entries.get(str(enrolment_id)),
        ratings.get(str(enrolment_id), {}),
        refreshed.times_school_opened,
        None,
        [],
    )


@router.get("/form-class/{arm_id}/students/{enrolment_id}/preview", response_model=Preview)
def preview(
    arm_id: uuid.UUID, enrolment_id: uuid.UUID, who: Results, session: DbSession
) -> Preview:
    arm, _ = place_in(session, who, arm_id)
    term = active_term(session)
    pupil = found(
        next(
            (
                p
                for p in pupils_of(session, arm_id, term.session_id)
                if p.enrolment_id == enrolment_id
            ),
            None,
        )
    )
    section = section_of(session, arm_id, term.id)
    entries, ratings = entries_of(session, section.id if section else None)
    entry = entries.get(str(enrolment_id))
    results = class_results(session, who, arm, term)
    key = str(enrolment_id)
    subjects: list[PreviewSubject] = []
    if results is not None:
        names = {str(r.id): r.name for r in session.execute(text("select id, name from subjects"))}
        bands = [
            Band(grade=b.grade, min_score=b.min_score, max_score=b.max_score, remark=b.remark)
            for b in bands_of(session, "grade_bands", arm.level)
        ]
        for subject_id, subject in sorted(results.subjects.items(), key=lambda x: names[x[0]]):
            row = subject.pupils.get(key)
            if row is not None:
                grade = grade_for(row.total, bands) if row.total is not None else None
                subjects.append(
                    PreviewSubject(
                        name=names[subject_id],
                        total=row.total,
                        grade=grade.grade if grade else None,
                    )
                )
    overall = results.pupils.get(key) if results else None
    given = ratings.get(key, {})
    opened = section.times_school_opened if section else None
    present = entry.times_present if entry else None
    school_name = str(session.scalar(text("select name from schools")))
    return Preview(
        label=PREVIEW_LABEL,
        school_name=school_name,
        class_name=arm.class_name,
        pupil_name=f"{pupil.first_name} {pupil.surname}",
        admission_number=pupil.admission_number,
        subjects=subjects,
        average=overall.average if overall else None,
        position=overall.position if overall else None,
        comment=entry.form_teacher_comment if entry else None,
        traits=[
            PreviewTrait(name=t.name, domain=t.domain, value=given.get(t.id))
            for t in traits_of(session)
        ],
        attendance=Attendance(
            times_school_opened=opened,
            times_present=present,
            times_absent=opened - present if opened is not None and present is not None else None,
        ),
    )


# --- submit and return ------------------------------------------------------------------------


def section_move(
    session: Session,
    who: Principal,
    section: Any,
    arm_id: uuid.UUID,
    to: str,
    comment: str | None = None,
) -> SectionMove:
    session.execute(
        text("update class_report_sections set status = :to, status_comment = :c where id = :s"),
        {"to": to, "c": comment, "s": section.id},
    )
    write_audit(
        session,
        who.school_id,
        who.role.value,
        f"form_class.{to}",
        target=("class_report_sections", section.id),
        old={"status": section.status},
        new={"status": to},
        reason=comment,
    )
    row = session.execute(
        text("select status, revision, status_comment from class_report_sections where id = :s"),
        {"s": section.id},
    ).one()
    return SectionMove(
        arm_id=str(arm_id),
        status=row.status,
        revision=row.revision,
        status_comment=row.status_comment,
    )


@router.post("/form-class/{arm_id}/sections/submit", response_model=SectionMove)
def submit_sections(arm_id: uuid.UUID, who: Results, session: DbSession) -> SectionMove:
    _, place = place_in(session, who, arm_id)
    if place == "assistant":
        raise ProblemError(
            403, "Assistants enter; the form teacher submits.", code="assistants_cannot_submit"
        )
    if place == "admin":
        raise ProblemError(403, "The form teacher submits the class sections.", code="not_assigned")
    term = active_term(session)
    section = ensure_section(session, who, arm_id, term.id)
    require_status(section.status, "open", "returned")
    return section_move(session, who, section, arm_id, "submitted")


@router.post("/school/classes/{arm_id}/sections/return", response_model=SectionMove)
def return_sections(
    arm_id: uuid.UUID, body: ReturnBody, who: Admins, session: DbSession
) -> SectionMove:
    place_in(session, who, arm_id)
    term = active_term(session)
    section = found(section_of(session, arm_id, term.id))
    require_status(section.status, "submitted")
    return section_move(session, who, section, arm_id, "returned", body.comment)
