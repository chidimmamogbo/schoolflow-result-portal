"""Students needing attention (BUILD_PROMPT 9.2j2; SPEC F23; D-147, D-171).

The entries are written when a class is published (`reports/publication.py`),
one per published result below the pass mark (or skill at or below the
attention rating) and one per pupil with the count; here they are only read.
Only entries of Valid reports count, so a republished or revoked report drops
out and its new revision's entries take its place (rule 1). Only staff with
`attention.view` reach this list (parents and students are refused, AC23.4),
and each sees their scope (rule 5):
- school admins: every class, and they alone may filter by teacher;
- reviewers: the subjects and classes their scope covers (a department
  covers its subjects; a class scope covers that class's learning areas);
- anyone who teaches: their own subjects or learning areas in their arms,
  and every subject of an arm where they are the form teacher or an
  assistant (AC23.2, AC23.3).
By student counts only the entries the viewer can see; the overall average
and its "Average below pass mark" flag show only to viewers who see the
whole class (school admins, and the arm's form teacher and assistants).
"""

import uuid
from decimal import Decimal
from typing import Annotated, Any

from fastapi import Query, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import Principal
from app.core.errors import ProblemError
from app.core.permissions import Role
from app.src.attention.schemas import AttentionList, AttentionRow, View
from app.src.results.services import csv_text

# Who sees an entry. `ae` is the entry, `c` its class, `d` its report.
SCOPE = """(
    :admin
    or exists (select 1 from reviewer_scopes rs left join subjects sx on sx.id = ae.subject_id
               where rs.reviewer_id = :me
                 and ((rs.department_id is not null and rs.department_id = sx.department_id)
                   or (rs.department_id is null
                       and (rs.subject_id is null or rs.subject_id = ae.subject_id)
                       and (rs.class_id is null or rs.class_id = c.id))))
    or exists (select 1 from teacher_subjects ts
               where ts.teacher_id = :me and ts.arm_id = d.arm_id
                 and (ts.subject_id = ae.subject_id or ts.learning_area_id = ae.learning_area_id))
    or d.arm_id in (select arm_id from teacher_assignments where teacher_id = :me
                    and is_form_teacher
                    union select arm_id from class_assistants where assistant_id = :me)
)"""

WHOLE_CLASS = """(
    :admin
    or d.arm_id in (select arm_id from teacher_assignments where teacher_id = :me
                    and is_form_teacher
                    union select arm_id from class_assistants where assistant_id = :me)
)"""

FILTERS = """
    d.status = 'valid'
    and (cast(:term as uuid) is null or d.term_id = :term)
    and (cast(:session as uuid) is null or t.session_id = :session)
    and (cast(:class as uuid) is null or c.id = :class)
    and (cast(:arm as uuid) is null or d.arm_id = :arm)
"""

FROM = """
    from attention_entries ae
    join report_documents d on d.id = ae.report_document_id
    join terms t on t.id = d.term_id
    join class_arms a on a.id = d.arm_id
    join classes c on c.id = a.class_id
    join enrolments e on e.id = d.enrolment_id
    join students p on p.id = e.student_id
"""

PUPIL = """
    d.id as report_id, d.enrolment_id, d.term_id,
    p.first_name || ' ' || p.surname as student_name, p.admission_number,
    c.name || a.name as class_name
"""


def entries(session: Session, who: Principal, view: View, params: dict[str, Any]) -> list[Any]:
    base = {**params, "me": who.user_id, "admin": who.role is Role.SCHOOL_ADMIN}
    if view == "by_subject":
        return list(
            session.execute(
                text(
                    f"select {PUPIL}, s.name as subject, ae.score, ae.grade,"
                    " u.full_name as teacher"
                    f" {FROM} join subjects s on s.id = ae.subject_id"
                    " left join users u on u.id = ae.teacher_id"
                    f" where ae.kind = 'subject' and {FILTERS} and {SCOPE}"
                    " and (cast(:subject as uuid) is null or ae.subject_id = :subject)"
                    " and (cast(:teacher as uuid) is null or ae.teacher_id = :teacher)"
                    " order by class_name, p.surname, p.first_name, s.name"
                ),
                base,
            )
        )
    if view == "by_learning_area":
        return list(
            session.execute(
                text(
                    f"select {PUPIL}, la.name as learning_area, k.name as skill, ae.rating"  # noqa: S608 (fixed SQL)
                    f" {FROM} join learning_areas la on la.id = ae.learning_area_id"
                    " join skills k on k.id = ae.skill_id"
                    f" where ae.kind = 'skill' and {FILTERS} and {SCOPE}"
                    " and (cast(:area as uuid) is null or ae.learning_area_id = :area)"
                    " and (cast(:teacher as uuid) is null or exists (select 1"
                    "   from teacher_subjects ts where ts.teacher_id = :teacher"
                    "   and ts.arm_id = d.arm_id and ts.learning_area_id = ae.learning_area_id))"
                    " order by class_name, p.surname, p.first_name, la.position, k.position"
                ),
                base,
            )
        )
    return list(
        session.execute(
            text(
                f"select {PUPIL}, count(*) as failed_count,"  # noqa: S608 (fixed SQL)
                f" bool_or({WHOLE_CLASS}) as whole_class,"
                " (select st.average from attention_entries st"
                "  where st.report_document_id = d.id and st.kind = 'student') as average,"
                " cast(d.snapshot -> 'grading' ->> 'pass_mark' as integer) as pass_mark"
                f" {FROM} where ae.kind in ('subject', 'skill') and {FILTERS} and {SCOPE}"
                " and (cast(:subject as uuid) is null or ae.subject_id = :subject)"
                " and (cast(:area as uuid) is null or ae.learning_area_id = :area)"
                " and (cast(:teacher as uuid) is null or ae.teacher_id = :teacher"
                "  or exists (select 1 from teacher_subjects ts where ts.teacher_id = :teacher"
                "   and ts.arm_id = d.arm_id and ts.learning_area_id = ae.learning_area_id))"
                " group by d.id, d.enrolment_id, d.term_id, p.first_name, p.surname,"
                " p.admission_number, c.name, a.name, d.snapshot"
                " order by class_name, p.surname, p.first_name"
            ),
            base,
        )
    )


def as_row(view: View, r: Any) -> AttentionRow:
    row = AttentionRow(
        report_id=str(r.report_id),
        enrolment_id=str(r.enrolment_id),
        student_name=r.student_name,
        admission_number=r.admission_number,
        class_name=r.class_name,
        term_id=str(r.term_id),
    )
    if view == "by_subject":
        row.subject, row.score, row.grade, row.teacher = r.subject, r.score, r.grade, r.teacher
    elif view == "by_learning_area":
        row.learning_area, row.skill, row.rating = r.learning_area, r.skill, r.rating
    else:
        row.failed_count = r.failed_count
        if r.whole_class and r.average is not None:
            average: Decimal = r.average
            row.average = str(average)
            row.average_below_pass_mark = r.pass_mark is not None and average < r.pass_mark
    return row


def attention_list(
    session: Session,
    who: Principal,
    view: View,
    term_id: uuid.UUID | None,
    session_id: uuid.UUID | None,
    class_id: uuid.UUID | None,
    arm_id: uuid.UUID | None,
    subject_id: uuid.UUID | None,
    learning_area_id: uuid.UUID | None,
    teacher_id: uuid.UUID | None,
) -> AttentionList:
    if teacher_id is not None and who.role is not Role.SCHOOL_ADMIN:
        raise ProblemError(403, "Only school admins can filter by teacher.", code="admins_only")
    if term_id is None and session_id is None:
        term_id = session.scalar(text("select id from terms where is_active"))
    params = {
        "term": term_id,
        "session": session_id,
        "class": class_id,
        "arm": arm_id,
        "subject": subject_id,
        "area": learning_area_id,
        "teacher": teacher_id,
    }
    rows = [as_row(view, r) for r in entries(session, who, view, params)]
    pass_mark = int(session.scalar(text("select pass_mark from school_settings")) or 40)
    return AttentionList(
        view=view,
        term_id=str(term_id) if term_id else None,
        pass_mark=pass_mark,
        count=len(rows),
        rows=rows,
    )


Ids = Annotated[uuid.UUID | None, Query()]


def get_attention(
    who: Principal,
    session: Session,
    view: View = "by_subject",
    term_id: Ids = None,
    session_id: Ids = None,
    class_id: Ids = None,
    arm_id: Ids = None,
    subject_id: Ids = None,
    learning_area_id: Ids = None,
    teacher_id: Ids = None,
) -> AttentionList:
    return attention_list(
        session, who, view, term_id, session_id, class_id, arm_id, subject_id,
        learning_area_id, teacher_id,
    )  # fmt: skip


CSV_HEADERS: dict[View, list[str]] = {
    "by_subject": ["Student", "Admission number", "Class", "Subject", "Score", "Grade", "Teacher"],
    "by_learning_area": ["Pupil", "Admission number", "Class", "Learning area", "Skill", "Rating"],
    "by_student": [
        "Student", "Admission number", "Class", "Failed subjects or skills", "Average",
        "Average below pass mark",
    ],
}  # fmt: skip


def csv_cells(view: View, row: AttentionRow) -> list[str]:
    start = [row.student_name, row.admission_number, row.class_name]
    if view == "by_subject":
        rest = [row.subject, row.score, row.grade, row.teacher]
    elif view == "by_learning_area":
        rest = [row.learning_area, row.skill, row.rating]
    else:
        flag = (
            None
            if row.average_below_pass_mark is None
            else ("Yes" if row.average_below_pass_mark else "No")
        )
        rest = [row.failed_count, row.average, flag]
    return ["" if v is None else str(v) for v in [*start, *rest]]  # made safe by csv_text


def export_attention(
    who: Principal,
    session: Session,
    view: View = "by_subject",
    term_id: Ids = None,
    session_id: Ids = None,
    class_id: Ids = None,
    arm_id: Ids = None,
    subject_id: Ids = None,
    learning_area_id: Ids = None,
    teacher_id: Ids = None,
) -> Response:
    listing = attention_list(
        session, who, view, term_id, session_id, class_id, arm_id, subject_id,
        learning_area_id, teacher_id,
    )  # fmt: skip
    rows = [CSV_HEADERS[view], *(csv_cells(view, r) for r in listing.rows)]
    return Response(
        csv_text(rows),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="students-needing-attention.csv"'},
    )
