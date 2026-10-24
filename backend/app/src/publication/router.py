"""Publishing a class's results (BUILD_PROMPT 9.2i part 2; SPEC F10, F12, F13, F17, F18, F23).

Decision D-170.

Readiness, in the order the principal fixes things: every subject sheet (or
rating sheet) of the arm approved; for the blocks the class's template shows,
the form teacher's sections submitted and complete; the principal's comments
written. Publishing then happens in one transaction:
1. the sheets and the sections become Published (the database checks each move);
2. each pupil gets a report document: a frozen snapshot (results from the
   results engine, the structure, the bands, the template version, the
   calculation version), a report ID and a verification code; the database
   numbers the revision, hashes the snapshot, masks the name and stores only
   the code's hash for verification;
3. Students needing attention are recorded from the same results (F23);
4. one notice goes to the class's audience only, and one email to each of
   its pupils and parents with an email address, never with scores (F17, F18).
A report is revoked only with a reason.

Reopening (F10, section 8): a school admin reopens chosen sheets of a
published class, or its class sections, with a reason (and optionally the
correction request that prompted it); each becomes a new revision in Draft
(or Open) and goes through the workflow again, while the pupils' Valid
reports stay in place. Republishing issues a new revision only for pupils
whose snapshot changed (the database supersedes the old one and keeps the
report ID), records their attention entries afresh, and tells only them,
their parents and the class's staff (D-171).
"""

import json
import re
import secrets
import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import Field, StringConstraints
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
from app.core.schemas import ApiModel
from app.platform.email.queue import queue_email
from app.src.audit.services import write_audit
from app.src.form_class.router import class_results, ensure_section, pupils_of
from app.src.grading.router import Band
from app.src.grading.services import ensure_defaults
from app.src.reports.templates import Settings, current, shown, template_for_publication
from app.src.results.engine import CALCULATION_VERSION, ClassResult, grade_for
from app.src.results.sheets import active_term
from app.src.schools.models import Feature, Level

router = APIRouter(prefix="/school", tags=["publication"])

Publishers = Annotated[Principal, Depends(require("results.publish", feature=Feature.RESULTS))]
Commenters = Annotated[
    Principal, Depends(require("results.principal_comments", feature=Feature.RESULTS))
]
Revokers = Annotated[Principal, Depends(require("results.revoke", feature=Feature.RESULTS))]
Reopeners = Annotated[Principal, Depends(require("results.reopen", feature=Feature.RESULTS))]
Comment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]

# D-072: Crockford Base32 without I, L, O or U.
CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
TERM_NAMES = {1: "First Term", 2: "Second Term", 3: "Third Term"}
NOT_SUBMITTED = "Form teacher comments are not submitted"


class Readiness(ApiModel):
    ready: bool
    problems: list[str]
    class_name: str
    status: str


class HeadComment(ApiModel):
    enrolment_id: uuid.UUID
    comment: Comment


class HeadComments(ApiModel):
    comments: Annotated[list[HeadComment], Field(min_length=1, max_length=200)]


class PublishedReport(ApiModel):
    enrolment_id: str
    admission_number: str
    report_code: str
    revision: int
    verification_code: str


class Published(ApiModel):
    published: int
    reports: list[PublishedReport]


class ReportRow(ApiModel):
    id: str
    enrolment_id: str
    admission_number: str
    pupil_name: str
    report_code: str
    revision: int
    status: str
    verification_code: str


class RevokeBody(ApiModel):
    reason: Reason


class Revoked(ApiModel):
    id: str
    status: str


class ReopenBody(ApiModel):
    reason: Reason
    sheet_ids: Annotated[list[uuid.UUID], Field(max_length=100)] = Field(
        default_factory=list[uuid.UUID]
    )
    sections: bool = False
    correction_request_id: uuid.UUID | None = None


# --- the class and its readiness --------------------------------------------------------------


def load_arm(session: Session, who: Principal, arm_id: uuid.UUID) -> Any:
    arm = found(
        session.execute(
            text(
                "select a.id, a.class_id, c.level, c.name as class_label,"
                " c.name || a.name as class_name from class_arms a"
                " join classes c on c.id = a.class_id where a.id = :a"
            ),
            {"a": arm_id},
        ).first()
    )
    ensure_level_enabled(session, who, Level(arm.level))
    return arm


def needed_sheets(session: Session, arm: Any, term: Any, card: str) -> list[Any]:
    """Every sheet the class needs: subjects someone takes, or the class's learning areas."""
    if card == "skills":
        sql = (
            "select la.id, la.name, r.id as sheet_id, r.status from class_learning_areas cla"
            " join learning_areas la on la.id = cla.learning_area_id"
            " left join result_sheets r on r.arm_id = :a and r.learning_area_id = la.id"
            "   and r.term_id = :t where cla.class_id = :c order by la.position, la.name"
        )
    else:
        sql = (
            "select s.id, s.name, r.id as sheet_id, r.status from subjects s"
            " left join result_sheets r on r.arm_id = :a and r.subject_id = s.id"
            "   and r.term_id = :t where exists (select 1 from enrolments e"
            "   join student_subjects ss on ss.enrolment_id = e.id and ss.subject_id = s.id"
            "   where e.arm_id = :a and e.session_id = :y and e.left_on is null)"
            " order by s.name"
        )
    return list(
        session.execute(
            text(sql), {"a": arm.id, "t": term.id, "c": arm.class_id, "y": term.session_id}
        )
    )


def plural(count: int) -> str:
    return f"{count} student" if count == 1 else f"{count} students"


def published_before(session: Session, arm: Any, term: Any) -> bool:
    return bool(
        session.scalar(
            text(
                "select exists (select 1 from report_documents where arm_id = :a and term_id = :t)"
            ),
            {"a": arm.id, "t": term.id},
        )
    )


def readiness(session: Session, arm: Any, term: Any, settings: Settings) -> Readiness:
    """What still stops publication; on a republish, parts not reopened stay Published."""
    sheets = needed_sheets(session, arm, term, settings.card)
    section = session.execute(
        text(
            "select id, status, times_school_opened from class_report_sections"
            " where arm_id = :a and term_id = :t"
        ),
        {"a": arm.id, "t": term.id},
    ).first()
    again = published_before(session, arm, term)
    reopened = any(s.status != "published" for s in sheets) or (
        again and section is not None and section.status != "published"
    )
    if sheets and not reopened:
        return Readiness(
            ready=False,
            problems=["Already published"],
            class_name=arm.class_name,
            status="published",
        )
    problems = [
        f"{s.name}: {(s.status or 'not started').replace('_', ' ')}"
        for s in sheets
        if s.status not in ("approved", "published")  # published: not reopened this time
    ]
    if not sheets:
        problems.append("No subjects or learning areas to publish")
    status = "approved" if not problems else "in_progress"

    comments = shown(settings, "comments")
    needs_comment = comments and settings.comments.form_teacher
    needs_attendance = shown(settings, "attendance")
    needs_traits = (
        settings.card == "scores"
        and shown(settings, "affective_psychomotor")
        and (settings.affective_psychomotor.affective or settings.affective_psychomotor.psychomotor)
    )
    pupils = pupils_of(session, arm.id, term.session_id)
    entries = {
        r.enrolment_id: r
        for r in session.execute(
            text(
                "select e.id, e.enrolment_id, e.form_teacher_comment, e.times_present,"
                " e.head_comment, (select count(*) from student_trait_ratings t"
                "   where t.entry_id = e.id) as ratings"
                " from student_term_entries e where e.section_id = :s"
            ),
            {"s": section.id if section else None},
        )
    }
    unchanged = again and section is not None and section.status == "published"
    if (needs_comment or needs_attendance or needs_traits) and not unchanged:
        if section is None or section.status != "submitted":
            problems.append(NOT_SUBMITTED if needs_comment else "Class sections are not submitted")
        else:
            missing_comment = sum(
                1
                for p in pupils
                if not getattr(entries.get(p.enrolment_id), "form_teacher_comment", None)
            )
            if needs_comment and missing_comment:
                problems.append(f"Form teacher comments are missing for {plural(missing_comment)}")
            if needs_attendance and section.times_school_opened is None:
                problems.append("Times school opened is not set")
            missing_present = sum(
                1
                for p in pupils
                if getattr(entries.get(p.enrolment_id), "times_present", None) is None
            )
            if needs_attendance and missing_present:
                problems.append(f"Times present is missing for {plural(missing_present)}")
            traits = int(
                session.scalar(text("select count(*) from rating_traits where is_active")) or 0
            )
            missing_traits = sum(
                1 for p in pupils if getattr(entries.get(p.enrolment_id), "ratings", 0) < traits
            )
            if needs_traits and missing_traits:
                problems.append(f"Trait ratings are missing for {plural(missing_traits)}")
    if comments and settings.comments.principal:
        missing_head = sum(
            1 for p in pupils if not getattr(entries.get(p.enrolment_id), "head_comment", None)
        )
        if missing_head:
            problems.append(f"Principal's comments are missing for {plural(missing_head)}")
    return Readiness(
        ready=not problems, problems=problems, class_name=arm.class_name, status=status
    )


@router.get("/publications/{arm_id}", response_model=Readiness)
def get_readiness(arm_id: uuid.UUID, who: Publishers, session: DbSession) -> Readiness:
    arm = load_arm(session, who, arm_id)
    ensure_defaults(session, found(who.school_id), who.role.value)
    _, _, settings = current(session, arm.level)
    return readiness(session, arm, active_term(session), settings)


@router.put("/publications/{arm_id}/principal-comments", response_model=Readiness)
def principal_comments(
    arm_id: uuid.UUID, body: HeadComments, who: Commenters, session: DbSession
) -> Readiness:
    arm = load_arm(session, who, arm_id)
    term = active_term(session)
    in_class = {p.enrolment_id for p in pupils_of(session, arm.id, term.session_id)}
    if any(c.enrolment_id not in in_class for c in body.comments):
        raise ProblemError(404, "Not Found")
    section = ensure_section(session, who, arm.id, term.id)
    for item in body.comments:
        updated = session.scalar(
            text(
                "update student_term_entries set head_comment = :c where section_id = :s"
                " and enrolment_id = :e returning id"
            ),
            {"c": item.comment, "s": section.id, "e": item.enrolment_id},
        )
        if updated is None:
            session.execute(
                text(
                    "insert into student_term_entries (school_id, section_id, enrolment_id,"
                    " head_comment) values (:school, :s, :e, :c)"
                ),
                {
                    "school": who.school_id,
                    "s": section.id,
                    "e": item.enrolment_id,
                    "c": item.comment,
                },
            )
    write_audit(
        session,
        who.school_id,
        who.role.value,
        "results.principal_comments",
        target=("class_report_sections", section.id),
        new={"count": len(body.comments)},
    )
    ensure_defaults(session, found(who.school_id), who.role.value)
    _, _, settings = current(session, arm.level)
    return readiness(session, arm, term, settings)


# --- publishing -------------------------------------------------------------------------------


def new_verification_code() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def compact(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def report_codes(
    school_code: str,
    session_name: str,
    term_number: int,
    class_name: str,
    admissions: list[str],
    kept: dict[str, str] | None = None,
    taken: set[str] | None = None,
) -> dict[str, str]:
    """GMC-2627-T1-JSS1A-014 (AT-16.2), different for every pupil.

    The last part of the admission number, or the whole of it when two pupils
    share that part; if an ID is still in use (by a classmate, or by another
    pupil of the school this term, `taken`), it gets -2, -3 and so on. A pupil
    who already has an ID this term keeps it (`kept`): the database requires
    the same ID in every revision.
    """
    kept = kept or {}
    years = session_name.split("/")
    prefix = f"{school_code}-{years[0][-2:]}{years[-1][-2:]}-T{term_number}-{compact(class_name)}"
    parts = {a: re.findall(r"[A-Z0-9]+", a.upper()) or ["PUPIL"] for a in admissions}
    counts: dict[str, int] = {}
    for found_parts in parts.values():
        counts[found_parts[-1]] = counts.get(found_parts[-1], 0) + 1
    codes = {a: kept[a] for a in admissions if a in kept}
    used = set(taken or set()) | set(codes.values())
    for admission in sorted(a for a in admissions if a not in kept):
        tail = parts[admission][-1]
        ending = tail if counts[tail] == 1 else "-".join(parts[admission])
        base = f"{prefix}-{ending}"[:64].rstrip("-")
        code, number = base, 2
        while code in used:
            suffix = f"-{number}"
            code = base[: 64 - len(suffix)].rstrip("-") + suffix
            number += 1
        used.add(code)
        codes[admission] = code
    return codes


def as_text(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def score_subjects(
    session: Session,
    arm: Any,
    term: Any,
    results: ClassResult,
    bands: list[Band],
    pass_mark: int,
    enrolment: str,
) -> list[dict[str, Any]]:
    columns = list(
        session.execute(
            text(
                "select c.id, c.label from assessment_components c join assessment_structures s"
                " on s.id = c.structure_id where s.level = :l and s.term_id = :t"
                " order by c.position"
            ),
            {"l": arm.level, "t": term.id},
        )
    )
    scores: dict[tuple[str, str], dict[str, int]] = {}
    for r in session.execute(
        text(
            "select r.subject_id, sc.enrolment_id, sc.component_id, sc.value from scores sc"
            " join result_sheets r on r.id = sc.sheet_id where r.arm_id = :a and r.term_id = :t"
            " and sc.enrolment_id = :e"
        ),
        {"a": arm.id, "t": term.id, "e": enrolment},
    ):
        label = next(c.label for c in columns if c.id == r.component_id)
        scores.setdefault((str(r.subject_id), str(r.enrolment_id)), {})[label] = r.value
    subjects = {
        str(r.id): r
        for r in session.execute(
            text(
                "select s.id, s.name, s.category, (select u.full_name from teacher_subjects ts"
                "  join users u on u.id = ts.teacher_id where ts.arm_id = :a"
                "  and ts.subject_id = s.id limit 1) as teacher from subjects s"
            ),
            {"a": arm.id},
        )
    }
    rows: list[dict[str, Any]] = []
    for subject_id, result in results.subjects.items():
        mine = result.pupils.get(enrolment)
        if mine is None:
            continue
        grade = grade_for(mine.total, bands) if mine.total is not None else None
        rows.append(
            {
                "subject_id": subject_id,
                "name": subjects[subject_id].name,
                "category": subjects[subject_id].category,
                "teacher": subjects[subject_id].teacher,
                "scores": scores.get((subject_id, enrolment), {}),
                "total": mine.total,
                "grade": grade.grade if grade else None,
                "remark": grade.remark if grade else None,
                "position": mine.position,
                "class_average": as_text(result.average),
                "highest": result.highest,
                "lowest": result.lowest,
                "below_pass_mark": mine.total is not None and mine.total < pass_mark,
            }
        )
    return sorted(rows, key=lambda r: r["name"])


def skills_areas(session: Session, arm: Any, term: Any, enrolment: str) -> list[dict[str, Any]]:
    areas: list[dict[str, Any]] = []
    for area in session.execute(
        text(
            "select r.id as sheet_id, la.id, la.name from result_sheets r"
            " join learning_areas la on la.id = r.learning_area_id"
            " where r.arm_id = :a and r.term_id = :t order by la.position, la.name"
        ),
        {"a": arm.id, "t": term.id},
    ):
        ratings = [
            {
                "skill_id": str(r.skill_id),
                "skill": r.skill,
                "description": r.description,
                "rating": r.point,
                "code": r.code,
                "attention": r.attention,
            }
            for r in session.execute(
                text(
                    "select k.id as skill_id, k.name as skill, k.description, p.name as point,"
                    " p.code, p.position >= (select q.position from rating_scale_points q"
                    "   where q.is_attention) as attention"
                    " from skill_ratings sr join skills k on k.id = sr.skill_id"
                    " join rating_scale_points p on p.id = sr.point_id"
                    " where sr.sheet_id = :s and sr.enrolment_id = :e order by k.position"
                ),
                {"s": area.sheet_id, "e": enrolment},
            )
        ]
        comment = session.scalar(
            text("select comment from area_comments where sheet_id = :s and enrolment_id = :e"),
            {"s": area.sheet_id, "e": enrolment},
        )
        areas.append(
            {
                "learning_area_id": str(area.id),
                "name": area.name,
                "comment": comment,
                "skills": ratings,
            }
        )
    return areas


@router.post("/publications/{arm_id}/publish", response_model=Published)
def publish(arm_id: uuid.UUID, who: Publishers, session: DbSession) -> Published:
    arm = load_arm(session, who, arm_id)
    school_id = found(who.school_id)
    ensure_defaults(session, school_id, who.role.value)
    term = session.execute(
        text(
            "select t.id, t.session_id, t.term_number, t.starts_on, t.ends_on, t.next_term_begins,"
            " s.name as session_name"
            " from terms t join academic_sessions s on s.id = t.session_id where t.is_active"
        )
    ).first()
    if term is None:
        raise ProblemError(409, "Activate a term first.", code="no_active_term")
    template, settings = template_for_publication(session, who, arm.level)
    ready = readiness(session, arm, term, settings)
    if not ready.ready:
        raise ProblemError(
            409, "This class is not ready to publish.", "; ".join(ready.problems), code="not_ready"
        )

    results = class_results(session, who, arm, term) if settings.card == "scores" else None
    session.execute(
        text(
            "update result_sheets set status = 'published' where arm_id = :a"
            " and term_id = :t and status = 'approved'"
        ),
        {"a": arm.id, "t": term.id},
    )
    section = session.execute(
        text(
            "select id, status, times_school_opened"
            " from class_report_sections where arm_id = :a and term_id = :t"
        ),
        {"a": arm.id, "t": term.id},
    ).first()
    if section is not None and section.status == "submitted":
        session.execute(
            text("update class_report_sections set status = 'published' where id = :s"),
            {"s": section.id},
        )

    school = session.execute(
        text(
            "select id, name, code, address, city, state, phone, email,"
            " colour, logo_file_id from schools where id = :s"
        ),
        {"s": school_id},
    ).one()
    level = session.execute(
        text("select head_title from school_levels where level = :l"), {"l": arm.level}
    ).one()
    form_teacher = session.scalar(
        text(
            "select u.full_name from teacher_assignments t join users u on u.id = t.teacher_id"
            " where t.arm_id = :a and t.is_form_teacher"
        ),
        {"a": arm.id},
    )
    pass_mark = int(session.scalar(text("select pass_mark from school_settings")) or 40)
    bands = [
        Band(grade=b.grade, min_score=b.min_score, max_score=b.max_score, remark=b.remark)
        for b in session.execute(
            text(
                "select grade, min_score, max_score, remark"
                " from grade_bands where level = :l"
                " order by min_score desc"
            ),
            {"l": arm.level},
        )
    ]
    structure = [
        {"label": r.label, "max_score": r.max_score}
        for r in session.execute(
            text(
                "select c.label, c.max_score from assessment_components c"
                " join assessment_structures s on s.id = c.structure_id"
                " where s.level = :l and s.term_id = :t order by c.position"
            ),
            {"l": arm.level, "t": term.id},
        )
    ]
    traits = list(
        session.execute(
            text(
                "select id, name, domain from rating_traits"
                " where is_active order by domain, position"
            )
        )
    )
    key = {
        str(r.value): r.label
        for r in session.execute(
            text("select value, label from trait_scale_points order by value desc")
        )
    }
    scale = [
        {"name": r.name, "code": r.code, "description": r.description, "attention": r.is_attention}
        for r in session.execute(
            text(
                "select name, code, description, is_attention from rating_scale_points"
                " order by position"
            )
        )
    ]
    pupils = list(
        session.execute(
            text(
                "select e.id as enrolment_id, p.id as student_id, p.admission_number, p.surname,"
                " p.first_name, p.other_names, p.gender, p.date_of_birth, p.house"
                " from enrolments e join students p on p.id = e.student_id"
                " where e.arm_id = :a and e.session_id = :y and e.left_on is null"
                " order by p.surname, p.first_name"
            ),
            {"a": arm.id, "y": term.session_id},
        )
    )
    earlier = {
        str(r.enrolment_id): r.report_code
        for r in session.execute(
            text(
                "select distinct enrolment_id, report_code from report_documents where term_id = :t"
            ),
            {"t": term.id},
        )
    }
    in_class = {str(p.enrolment_id): p.admission_number for p in pupils}
    codes = report_codes(
        school.code,
        term.session_name,
        term.term_number,
        arm.class_name,
        list(in_class.values()),
        kept={in_class[e]: code for e, code in earlier.items() if e in in_class},
        taken={code for e, code in earlier.items() if e not in in_class},
    )
    teacher_of = {
        str(r.subject_id): r.teacher_id
        for r in session.execute(
            text(
                "select subject_id, teacher_id from teacher_subjects where arm_id = :a"
                " and subject_id is not null"
            ),
            {"a": arm.id},
        )
    }
    averages: list[Decimal] = []
    if results is not None:
        averages = [r.average for r in results.pupils.values() if r.average is not None]
    valid = {
        str(r.enrolment_id): r.snapshot
        for r in session.execute(
            text(
                "select enrolment_id, snapshot from report_documents"
                " where arm_id = :a and term_id = :t and status = 'valid'"
            ),
            {"a": arm.id, "t": term.id},
        )
    }
    again = published_before(session, arm, term)

    published: list[PublishedReport] = []
    for pupil in pupils:
        enrolment = str(pupil.enrolment_id)
        entry = session.execute(
            text(
                "select e.id, e.form_teacher_comment, e.times_present, e.head_comment"
                " from student_term_entries e join class_report_sections s on s.id = e.section_id"
                " where s.arm_id = :a and s.term_id = :t and e.enrolment_id = :e"
            ),
            {"a": arm.id, "t": term.id, "e": enrolment},
        ).first()
        given = (
            {}
            if entry is None
            else {
                str(r.trait_id): r.value
                for r in session.execute(
                    text("select trait_id, value from student_trait_ratings where entry_id = :e"),
                    {"e": entry.id},
                )
            }
        )
        opened = section.times_school_opened if section else None
        present = entry.times_present if entry else None
        overall = results.pupils.get(enrolment) if results else None
        snapshot: dict[str, Any] = {
            "card": settings.card,
            "school": {
                "name": school.name,
                "code": school.code,
                "address": school.address,
                "city": school.city,
                "state": school.state,
                "phone": school.phone,
                "email": school.email,
                "colour": school.colour,
                "logo_file_id": str(school.logo_file_id) if school.logo_file_id else None,
            },
            "term": {
                "number": term.term_number,
                "name": TERM_NAMES[term.term_number],
                "session": term.session_name,
                "starts_on": term.starts_on.isoformat(),  # CHANGE 2026-10-24
                "ends_on": term.ends_on.isoformat(),
                "next_term_begins": term.next_term_begins.isoformat()
                if term.next_term_begins
                else None,
            },
            "class": {"name": arm.class_name, "level": arm.level, "form_teacher": form_teacher},
            "pupil": {
                "surname": pupil.surname,
                "first_name": pupil.first_name,
                "other_names": pupil.other_names,
                "admission_number": pupil.admission_number,
                "gender": pupil.gender,
                "date_of_birth": pupil.date_of_birth.isoformat() if pupil.date_of_birth else None,
                "house": pupil.house,
            },
            "template": {
                "id": str(template.id),
                "version": template.version,
                "style": template.style,
                "settings": settings.model_dump(mode="json"),
            },
            "calculation_version": CALCULATION_VERSION,
            "attendance": {
                "times_school_opened": opened,
                "times_present": present,
                "times_absent": opened - present
                if opened is not None and present is not None
                else None,
            },
            "comments": {
                "form_teacher": entry.form_teacher_comment if entry else None,
                "form_teacher_name": form_teacher,
                "head": entry.head_comment if entry else None,
                "head_title": level.head_title,
            },
            "traits": [
                {"name": t.name, "domain": t.domain, "value": given.get(str(t.id))} for t in traits
            ],
            "trait_key": key,
        }
        if settings.card == "scores" and results is not None:
            subjects = score_subjects(session, arm, term, results, bands, pass_mark, enrolment)
            snapshot |= {
                "structure": structure,
                "grading": {"pass_mark": pass_mark, "bands": [b.model_dump() for b in bands]},
                "subjects": subjects,
                "summary": {
                    "total": overall.total if overall else None,
                    "average": as_text(overall.average) if overall else None,
                    "position": overall.position if overall else None,
                    "number_in_class": results.class_size,
                    "class_average": as_text(results.class_average),
                    "subjects": len(subjects),
                    "marks_obtainable": 100 * len(subjects),
                    "highest_average": as_text(max(averages, default=None)),
                    "lowest_average": as_text(min(averages, default=None)),
                },
            }
        else:
            snapshot |= {"areas": skills_areas(session, arm, term, enrolment), "scale": scale}

        if valid.get(enrolment) == json.loads(json_dump(snapshot)):
            continue  # nothing on this pupil's report changed: it stays Valid
        code = new_verification_code()
        report = session.execute(
            text(
                "insert into report_documents (school_id, term_id, arm_id, enrolment_id,"
                " template_id, report_code, verification_code, snapshot, calculation_version)"
                " values (:school, :t, :a, :e, :tpl, :code, :vcode, cast(:snap as jsonb), :cv)"
                " returning id, report_code, revision"
            ),
            {
                "school": school_id,
                "t": term.id,
                "a": arm.id,
                "e": enrolment,
                "tpl": template.id,
                "code": codes[pupil.admission_number],
                "vcode": code,
                "snap": json_dump(snapshot),
                "cv": CALCULATION_VERSION,
            },
        ).one()
        record_attention(session, school_id, report.id, snapshot, teacher_of, pass_mark, overall)
        published.append(
            PublishedReport(
                enrolment_id=enrolment,
                admission_number=pupil.admission_number,
                report_code=report.report_code,
                revision=report.revision,
                verification_code=code,
            )
        )

    if published:
        tell_the_class(session, who, arm, term, [r.enrolment_id for r in published], updated=again)
    write_audit(
        session,
        school_id,
        who.role.value,
        "results.republish" if again else "results.publish",
        target=("class_arms", arm.id),
        new={"term_id": str(term.id), "reports": len(published)},
    )
    return Published(published=len(published), reports=published)


def json_dump(value: dict[str, Any]) -> str:
    return json.dumps(value, default=str)


def record_attention(
    session: Session,
    school_id: uuid.UUID,
    report_id: uuid.UUID,
    snapshot: dict[str, Any],
    teacher_of: dict[str, uuid.UUID],
    pass_mark: int,
    overall: Any,
) -> None:
    """Students needing attention from this report (F23 rules 1 to 3 and 8)."""
    insert = text(
        "insert into attention_entries (school_id, report_document_id, kind, subject_id,"
        " teacher_id, score, grade, pass_mark, learning_area_id, skill_id, rating,"
        " failed_count, average) values (:s, :r, :kind, :subject, :teacher, :score, :grade,"
        " :pass, :area, :skill, :rating, :failed, :average)"
    )
    empty: dict[str, Any] = {
        "s": school_id,
        "r": report_id,
        "subject": None,
        "teacher": None,
        "score": None,
        "grade": None,
        "pass": None,
        "area": None,
        "skill": None,
        "rating": None,
        "failed": None,
        "average": None,
    }
    failed = 0
    for subject in snapshot.get("subjects", []):
        if subject["total"] is not None and subject["total"] < pass_mark:
            failed += 1
            session.execute(
                insert,
                {
                    **empty,
                    "kind": "subject",
                    "subject": subject["subject_id"],
                    "teacher": teacher_of.get(subject["subject_id"]),
                    "score": subject["total"],
                    "grade": subject["grade"],
                    "pass": pass_mark,
                },
            )
    for area in snapshot.get("areas", []):
        for skill in area["skills"]:
            if skill["attention"]:
                failed += 1
                session.execute(
                    insert,
                    {
                        **empty,
                        "kind": "skill",
                        "area": area["learning_area_id"],
                        "skill": skill["skill_id"],
                        "rating": skill["rating"],
                    },
                )
    if failed:
        session.execute(
            insert,
            {
                **empty,
                "kind": "student",
                "failed": failed,
                "average": overall.average if overall else None,
            },
        )


def tell_the_class(
    session: Session,
    who: Principal,
    arm: Any,
    term: Any,
    enrolments: list[str],
    *,
    updated: bool = False,
) -> None:
    """One notice for the class's audience only; one email per pupil or parent with an email.

    `enrolments` are the pupils who got a new report: on a republish, only
    they and their parents hear about it (with the class's staff).
    """
    term_name = TERM_NAMES[term.term_number]
    if updated:
        title = f"Updated {term_name} results for {arm.class_label} are now available"
        body = (
            f"Updated {term_name} {term.session_name} results for {arm.class_name}"
            " are published. Log in to view the report."
        )
    else:
        title = f"{term_name} results for {arm.class_label} are now available"
        body = (
            f"{term_name} {term.session_name} results for {arm.class_name}"
            " are published. Log in to view the report."
        )
    notice_id = session.scalar(
        text(
            "insert into notices (school_id, title, body, kind) values (:s, :t, :b, 'system')"
            " returning id"
        ),
        {"s": who.school_id, "t": title, "b": body},
    )
    session.execute(
        text("insert into notice_audiences (school_id, notice_id, class_id) values (:s, :n, :c)"),
        {"s": who.school_id, "n": notice_id, "c": arm.class_id},
    )
    families = set(
        session.scalars(
            text(
                "select p.user_id from enrolments e join students p on p.id = e.student_id"
                " where e.id = any(:e) and p.user_id is not null"
                " union select g.user_id from enrolments e join guardian_students gs"
                " on gs.student_id = e.student_id join guardians g on g.id = gs.guardian_id"
                " join school_memberships m on m.user_id = g.user_id and m.school_id = g.school_id"
                " and m.status = 'active'"
                " where e.id = any(:e)"
            ),
            {"e": [uuid.UUID(e) for e in enrolments]},
        )
    )
    staff = set(
        session.scalars(
            text(
                "select teacher_id from teacher_assignments where arm_id = :a"
                " union select assistant_id from class_assistants where arm_id = :a"
                " union select rs.reviewer_id from reviewer_scopes rs, result_sheets r"
                " left join subjects sx on sx.id = r.subject_id"
                " where r.arm_id = :a and r.term_id = :t"
                " and ((rs.department_id is not null and rs.department_id = sx.department_id)"
                "  or (rs.department_id is null"
                "      and (rs.subject_id is null or rs.subject_id = r.subject_id)"
                "      and (rs.class_id is null or rs.class_id = :c)))"
            ),
            {"a": arm.id, "t": term.id, "c": arm.class_id},
        )
    )
    for user_id in families | staff:
        session.execute(
            text(
                "insert into notice_recipients (school_id, notice_id, user_id) values (:s, :n, :u)"
            ),
            {"s": who.school_id, "n": notice_id, "u": user_id},
        )
    emails_on = session.scalar(
        text("select enabled from school_features where feature = 'email_notifications'")
    )
    if not emails_on or not families:
        return
    school_name = session.scalar(
        text("select name from schools where id = :s"), {"s": who.school_id}
    )
    for user in session.execute(
        text("select id, full_name, email from users where id = any(:ids) and email is not null"),
        {"ids": list(families)},
    ):
        queue_email(
            session,
            who.school_id,
            "results_published",
            user.email,
            {
                "full_name": user.full_name,
                "school_name": school_name,
                "class_name": arm.class_name,
                "term_name": term_name,
                "session_name": term.session_name,
                "updated": updated,
                "login_path": "/login",
            },
            priority=5,
        )


# --- reports: list and revoke --------------------------------------------------------------------


@router.get("/reports", response_model=list[ReportRow])
def list_reports(
    who: Publishers,
    session: DbSession,
    arm_id: uuid.UUID | None = None,
    term_id: uuid.UUID | None = None,
) -> list[ReportRow]:
    rows = session.execute(
        text(
            "select d.id, d.enrolment_id, p.admission_number,"
            " p.first_name || ' ' || p.surname as pupil_name, d.report_code, d.revision,"
            " d.status, d.verification_code from report_documents d"
            " join enrolments e on e.id = d.enrolment_id join students p on p.id = e.student_id"
            " where (cast(:a as uuid) is null or d.arm_id = :a)"
            " and (cast(:t as uuid) is null or d.term_id = :t)"
            " order by p.surname, p.first_name, d.revision desc"
        ),
        {"a": arm_id, "t": term_id},
    )
    return [
        ReportRow(
            id=str(r.id),
            enrolment_id=str(r.enrolment_id),
            admission_number=r.admission_number,
            pupil_name=r.pupil_name,
            report_code=r.report_code,
            revision=r.revision,
            status=r.status,
            verification_code=r.verification_code,
        )
        for r in rows
    ]


@router.post("/reports/{report_id}/revoke", response_model=Revoked)
def revoke(report_id: uuid.UUID, body: RevokeBody, who: Revokers, session: DbSession) -> Revoked:
    report = found(
        session.execute(
            text("select id, status from report_documents where id = :r"), {"r": report_id}
        ).first()
    )
    require_status(report.status, "valid")
    session.execute(
        text("update report_documents set status = 'revoked', revoke_reason = :why where id = :r"),
        {"why": body.reason, "r": report_id},
    )
    write_audit(
        session,
        who.school_id,
        who.role.value,
        "results.revoke",
        target=("report_documents", report_id),
        old={"status": "valid"},
        new={"status": "revoked"},
        reason=body.reason,
    )
    return Revoked(id=str(report_id), status="revoked")


# --- reopening ------------------------------------------------------------------------------------

OPEN_CORRECTIONS = ("open", "investigating", "needs_more_information")


@router.post("/publications/{arm_id}/reopen", response_model=Readiness)
def reopen(arm_id: uuid.UUID, body: ReopenBody, who: Reopeners, session: DbSession) -> Readiness:
    """New revisions of chosen sheets (Draft) or of the class sections (Open), with a reason."""
    arm = load_arm(session, who, arm_id)
    term = active_term(session)
    if not published_before(session, arm, term):
        raise ProblemError(
            409, "This class has not been published this term.", code="not_published"
        )
    if not body.sheet_ids and not body.sections:
        raise ProblemError(
            422, "Choose the sheets or class sections to reopen.", code="nothing_to_reopen"
        )
    if body.correction_request_id is not None:
        request = found(
            session.execute(
                text(
                    "select c.id, c.status from correction_requests c"
                    " join report_documents d on d.id = c.report_document_id"
                    " where c.id = :c and d.arm_id = :a and d.term_id = :t"
                ),
                {"c": body.correction_request_id, "a": arm.id, "t": term.id},
            ).first()
        )
        require_status(request.status, *OPEN_CORRECTIONS)
    sheets = [
        found(
            session.execute(
                text(
                    "select id, status from result_sheets"
                    " where id = :s and arm_id = :a and term_id = :t"
                ),
                {"s": sheet_id, "a": arm.id, "t": term.id},
            ).first()
        )
        for sheet_id in dict.fromkeys(body.sheet_ids)
    ]
    for sheet in sheets:
        require_status(sheet.status, "published")
    section = None
    if body.sections:
        section = found(
            session.execute(
                text(
                    "select id, status from class_report_sections"
                    " where arm_id = :a and term_id = :t"
                ),
                {"a": arm.id, "t": term.id},
            ).first()
        )
        require_status(section.status, "published")
    for sheet in sheets:
        session.execute(
            text(
                "update result_sheets set status = 'draft', status_comment = :why,"
                " revision = revision + 1 where id = :s"
            ),
            {"why": body.reason, "s": sheet.id},
        )
    if section is not None:
        session.execute(
            text(
                "update class_report_sections set status = 'open', status_comment = :why,"
                " revision = revision + 1 where id = :s"
            ),
            {"why": body.reason, "s": section.id},
        )
    write_audit(
        session,
        who.school_id,
        who.role.value,
        "results.reopen",
        target=("class_arms", arm.id),
        new={
            "term_id": str(term.id),
            "sheet_ids": [str(sheet.id) for sheet in sheets],
            "sections": section is not None,
            "correction_request_id": str(body.correction_request_id)
            if body.correction_request_id
            else None,
        },
        reason=body.reason,
    )
    ensure_defaults(session, found(who.school_id), who.role.value)
    _, _, settings = current(session, arm.level)
    return readiness(session, arm, term, settings)
