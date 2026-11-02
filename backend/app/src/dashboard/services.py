"""The dashboards (BUILD_PROMPT 9.2u; SPEC F16, F23 rule 6; D-179).

Nothing here is stored: every number is worked out on each read from the
tables the other domains own, and only the database's row-level security and
the scope rules below decide what is counted.

- School admins (`school_dashboard`) see what is blocking release in the active
  term. A feature that is off drops its part; a level that is off disappears
  (F25 rule 4). Averages use approved and published sheets only, and Skill
  ratings levels never compute any. The attention card comes only from
  published results (F23 rule 7).
- Staff who teach or review (`staff_dashboard`) see their own work. Teaching
  comes from assignments, not the role (D-144).
- Parents, students and the super admin read the routes they already have
  (`/portal`, `/notices`, `/platform/billing`); see D-179.
- Reminders (`remind`) post a notice to the people who still owe the work.
"""

import uuid
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import Principal, found
from app.core.errors import ProblemError
from app.core.permissions import Role
from app.src.attention.services import FILTERS, FROM, SCOPE
from app.src.audit.services import write_audit
from app.src.billing.services import billing_card
from app.src.dashboard.schemas import (
    AttentionCard,
    AverageRow,
    ClassProgress,
    MyClass,
    MySheets,
    Problems,
    Reminded,
    Reminder,
    SchoolDashboard,
    SchoolResults,
    SheetCounts,
    SheetProblem,
    StaffDashboard,
    Stats,
    TermAverage,
    UnusualChange,
)
from app.src.grading.services import ensure_defaults
from app.src.notices.services import members
from app.src.publication.services import (
    NOT_SUBMITTED,
    OPEN_CORRECTIONS,
    TERM_NAMES,
    needed_sheets,
    readiness,
)
from app.src.reports.services import current
from app.src.results.services import my_rating_sheets, my_sheets, review_queue, term_sheets
from app.src.schools.models import Feature

# A change after submission this big, as a share of the column's maximum, is
# worth the principal's eye (default, D-179). 4 to 14 in a CA of 20 is 50%.
UNUSUAL_PERCENT = 25
UNUSUAL_LIMIT = 20
TREND_TERMS = 6
ONE_PLACE = Decimal("0.1")
SECTION_PROBLEMS = (NOT_SUBMITTED, "Class sections are not submitted")
UNSUBMITTED = (None, "not_started", "draft", "returned_for_correction")
TO_DO = ("not_started", "draft")
WAITING = ("submitted", "resubmitted", "reviewed")
DONE = ("approved", "published")

SHEET_FROM = """
    from result_sheets r
    join terms t on t.id = r.term_id
    join class_arms a on a.id = r.arm_id
    join classes c on c.id = a.class_id
    join school_levels l on l.level = c.level and l.enabled
"""

MISSING_SCORES = f"""
    select r.id, c.name || a.name as class_name, s.name, n.pupils * m.columns - k.stored as count
    {SHEET_FROM}
    join subjects s on s.id = r.subject_id
    cross join lateral (select count(*) as pupils from enrolments e
        join student_subjects ss on ss.enrolment_id = e.id and ss.subject_id = r.subject_id
        where e.arm_id = r.arm_id and e.session_id = t.session_id and e.left_on is null) n
    cross join lateral (select count(*) as columns from assessment_components ac
        where ac.structure_id = r.structure_id) m
    cross join lateral (select count(*) as stored from scores sc
        join enrolments e on e.id = sc.enrolment_id
        where sc.sheet_id = r.id and e.left_on is null) k
    where r.term_id = :t and r.status not in ('approved', 'published')
    order by class_name, s.name
"""  # noqa: S608 (fixed SQL)

MISSING_RATINGS = f"""
    select r.id, c.name || a.name as class_name, la.name, n.pupils * m.skills - k.stored as count
    {SHEET_FROM}
    join learning_areas la on la.id = r.learning_area_id
    cross join lateral (select count(*) as pupils from enrolments e
        where e.arm_id = r.arm_id and e.session_id = t.session_id and e.left_on is null) n
    cross join lateral (select count(*) as skills from skills sk
        where sk.learning_area_id = r.learning_area_id and sk.is_active) m
    cross join lateral (select count(*) as stored from skill_ratings sr
        join enrolments e on e.id = sr.enrolment_id
        join skills sk on sk.id = sr.skill_id and sk.is_active
        where sr.sheet_id = r.id and e.left_on is null) k
    where r.term_id = :t and r.status not in ('approved', 'published')
    order by class_name, la.name
"""  # noqa: S608 (fixed SQL)

# The database refuses these (a trigger, migration 11), so this normally finds
# nothing; it is here because a wrong score must never pass unseen (F16).
INVALID_SCORES = f"""
    select r.id, c.name || a.name as class_name, s.name, count(*) as count
    {SHEET_FROM}
    join subjects s on s.id = r.subject_id
    join scores sc on sc.sheet_id = r.id
    join assessment_components ac on ac.id = sc.component_id
    where r.term_id = :t and (sc.value > ac.max_score or ac.structure_id <> r.structure_id)
    group by r.id, c.name, a.name, s.name
    order by class_name, s.name
"""

# One row per pupil per subject: a sheet's columns add up to 100.
TOTALS = f"""
    select r.id as sheet_id, s.name as subject, c.name || a.name as class_name,
        sum(sc.value) as total
    {SHEET_FROM}
    join subjects s on s.id = r.subject_id
    join scores sc on sc.sheet_id = r.id
    join enrolments e on e.id = sc.enrolment_id
    where r.term_id = :t and r.status in ('approved', 'published') and e.left_on is null
    group by r.id, s.name, c.name, a.name, sc.enrolment_id
"""

# Older terms keep pupils who have since left: their results were real.
TREND = f"""
    select term_number, session_name, round(avg(total), 1) as average from (
        select y.starts_on, t.term_number, y.name as session_name, sum(sc.value) as total
        {SHEET_FROM}
        join academic_sessions y on y.id = t.session_id
        join scores sc on sc.sheet_id = r.id
        join enrolments e on e.id = sc.enrolment_id
        where r.subject_id is not null and r.status in ('approved', 'published')
          and (not t.is_active or e.left_on is null)
        group by y.starts_on, t.term_number, y.name, r.id, sc.enrolment_id
    ) x
    group by starts_on, term_number, session_name
    order by starts_on desc, term_number desc limit :n
"""  # noqa: S608 (fixed SQL)

# Changes made after submission always carry a reason (D-143); the audit keeps them.
CHANGES = """
    select ev.target_id as sheet_id, ev.new_values, ev.reason,
        c.name || a.name as class_name, s.name as subject
    from audit_events ev
    join result_sheets r on r.id = ev.target_id
    join class_arms a on a.id = r.arm_id
    join classes c on c.id = a.class_id
    join school_levels l on l.level = c.level and l.enabled
    join subjects s on s.id = r.subject_id
    where ev.action = 'scores.save' and ev.target_table = 'result_sheets'
      and ev.reason is not null and r.term_id = :t
    order by ev.created_at desc, ev.id
"""

ATTENTION_COUNTS = f"""
    select count(*) filter (where ae.kind = 'subject') as subject_results,
        count(*) filter (where ae.kind = 'skill') as skills,
        count(distinct d.enrolment_id)
            filter (where ae.kind in ('subject', 'skill')) as students
    {FROM}
    join school_levels l on l.level = c.level and l.enabled
    where {FILTERS} and {SCOPE}
"""


def feature_on(session: Session, feature: Feature) -> bool:
    return bool(
        session.scalar(
            text("select enabled from school_features where feature = :f"), {"f": feature.value}
        )
    )


def active_term(session: Session) -> Any:
    """The active term with its label, or None: a new school has not started one."""
    return session.execute(
        text(
            "select t.id, t.session_id, t.term_number, s.name as session_name"
            " from terms t join academic_sessions s on s.id = t.session_id where t.is_active"
        )
    ).first()


def label(term: Any) -> str:
    return f"{TERM_NAMES[term.term_number]} {term.session_name}"


def pass_mark_of(session: Session) -> int:
    return int(session.scalar(text("select pass_mark from school_settings")) or 40)


def arms_of(session: Session, term: Any) -> list[Any]:
    """Arms with pupils this session, in levels that are on."""
    return list(
        session.execute(
            text(
                "select a.id, a.class_id, c.level, c.name || a.name as class_name"
                " from class_arms a join classes c on c.id = a.class_id"
                " join school_levels l on l.level = c.level and l.enabled"
                " where exists (select 1 from enrolments e where e.arm_id = a.id"
                "   and e.session_id = :y and e.left_on is null)"
                " order by c.name, a.name"
            ),
            {"y": term.session_id},
        )
    )


def add_sheet(counts: SheetCounts, status: str | None, *, covered: bool) -> None:
    counts.total += 1
    if status in UNSUBMITTED:
        counts.awaiting_submission += 1
    elif status in ("submitted", "resubmitted"):
        # A sheet no reviewer covers goes straight to approval (D-142).
        if covered:
            counts.awaiting_review += 1
        else:
            counts.awaiting_approval += 1
    elif status == "reviewed":
        counts.awaiting_approval += 1
    elif status == "approved":
        counts.approved += 1
    elif status == "published":
        counts.published += 1


def problems_from(rows: Any) -> Problems:
    sheets = [
        SheetProblem(sheet_id=str(r.id), class_name=r.class_name, name=r.name, count=int(r.count))
        for r in rows
        if r.count > 0
    ]
    return Problems(count=sum(s.count for s in sheets), sheets=sheets)


def rounded(value: Decimal, places: Decimal = ONE_PLACE) -> str:
    return str(value.quantize(places, rounding=ROUND_HALF_UP))


def average_of(totals: list[int]) -> str:
    return rounded(Decimal(sum(totals)) / len(totals))


def pass_rate_of(totals: list[int], pass_mark: int) -> str:
    passed = sum(1 for total in totals if total >= pass_mark)
    return rounded(Decimal(passed * 100) / len(totals), Decimal(1))


def rows_by(rows: list[Any], key: str, pass_mark: int) -> list[AverageRow]:
    groups: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        groups[getattr(row, key)].append(int(row.total))
    return [
        AverageRow(name=name, average=average_of(totals), pass_rate=pass_rate_of(totals, pass_mark))
        for name, totals in sorted(groups.items())
    ]


def stats_of(session: Session, term: Any) -> Stats:
    trend_rows = list(session.execute(text(TREND), {"n": TREND_TERMS}))
    trend = [TermAverage(term=label(r), average=str(r.average)) for r in reversed(trend_rows)]
    rows = list(session.execute(text(TOTALS), {"t": term.id}))
    if not rows:
        return Stats(trend=trend)
    pass_mark = pass_mark_of(session)
    totals = [int(r.total) for r in rows]
    return Stats(
        sheets_counted=len({r.sheet_id for r in rows}),
        average=average_of(totals),
        pass_rate=pass_rate_of(totals, pass_mark),
        by_subject=rows_by(rows, "subject", pass_mark),
        by_class=rows_by(rows, "class_name", pass_mark),
        trend=trend,
    )


def unusual_changes(session: Session, term: Any) -> list[UnusualChange]:
    events = session.execute(text(CHANGES), {"t": term.id}).all()
    if not events:
        return []
    columns = {
        str(r.id): r
        for r in session.execute(text("select id, label, max_score from assessment_components"))
    }
    pupils = {
        str(r.id): r.student_name
        for r in session.execute(
            text(
                "select e.id, p.first_name || ' ' || p.surname as student_name"
                " from enrolments e join students p on p.id = e.student_id"
                " where e.session_id = :y"
            ),
            {"y": term.session_id},
        )
    }
    changes: list[UnusualChange] = []
    for event in events:
        for cell in event.new_values.get("cells", []):
            enrolment, component = cell["cell"]
            old, new = cell["old"], cell["new"]
            column = columns.get(component)
            if old is None or new is None or column is None or enrolment not in pupils:
                continue
            if abs(new - old) * 100 < column.max_score * UNUSUAL_PERCENT:
                continue
            changes.append(
                UnusualChange(
                    sheet_id=str(event.sheet_id),
                    student_name=pupils[enrolment],
                    class_name=event.class_name,
                    subject=event.subject,
                    column=column.label,
                    old=old,
                    new=new,
                    reason=event.reason,
                )
            )
    return changes[:UNUSUAL_LIMIT]


def attention_card(session: Session, who: Principal, term: Any) -> AttentionCard | None:
    """Only from published results (F23 rule 7): before the first, there is no card."""
    published = session.scalar(
        text(
            "select exists (select 1 from report_documents where term_id = :t and status = 'valid')"
        ),
        {"t": term.id},
    )
    if not published:
        return None
    counts = session.execute(
        text(ATTENTION_COUNTS),
        {
            "term": term.id,
            "session": None,
            "class": None,
            "arm": None,
            "me": who.user_id,
            "admin": who.role is Role.SCHOOL_ADMIN,
        },
    ).one()
    return AttentionCard(
        term=label(term),
        pass_mark=pass_mark_of(session),
        subject_results=counts.subject_results,
        skills=counts.skills,
        students=counts.students,
    )


def open_section_arms(session: Session, term: Any, arms: list[Any]) -> list[Any]:
    """Arms whose form teacher sections still stop publication, by the publish rule itself."""
    still_open: list[Any] = []
    for arm in arms:
        _, _, settings = current(session, arm.level)
        problems = readiness(session, arm, term, settings).problems
        if any(problem in SECTION_PROBLEMS for problem in problems):
            still_open.append(arm)
    return still_open


def school_results(session: Session, who: Principal, term: Any) -> SchoolResults:
    ensure_defaults(session, found(who.school_id), who.role.value)
    covered = {r.id: bool(r.covered) for r in term_sheets(session, reviewer=None, waiting=False)}
    arms = arms_of(session, term)
    sheets = SheetCounts()
    classes: list[ClassProgress] = []
    started = False
    for arm in arms:
        _, _, settings = current(session, arm.level)
        progress = ClassProgress(class_name=arm.class_name)
        for need in needed_sheets(session, arm, term, settings.card):
            started = started or need.sheet_id is not None
            is_covered = covered.get(need.sheet_id, False)
            add_sheet(sheets, need.status, covered=is_covered)
            add_sheet(progress, need.status, covered=is_covered)
        classes.append(progress)
    params = {"t": term.id}
    return SchoolResults(
        nothing_started=not started,
        sheets=sheets,
        classes=classes,
        missing_scores=problems_from(session.execute(text(MISSING_SCORES), params)),
        missing_ratings=problems_from(session.execute(text(MISSING_RATINGS), params)),
        invalid_scores=problems_from(session.execute(text(INVALID_SCORES), params)),
        open_sections=[a.class_name for a in open_section_arms(session, term, arms)],
        unusual_changes=unusual_changes(session, term),
        stats=stats_of(session, term),
        attention=attention_card(session, who, term),
    )


def school_dashboard(who: Principal, session: Session) -> SchoolDashboard:
    term = active_term(session)
    results = None
    if term is not None and feature_on(session, Feature.RESULTS):
        results = school_results(session, who, term)
    corrections = None
    if feature_on(session, Feature.CORRECTION_QUEUE):
        corrections = int(
            session.scalar(
                text("select count(*) from correction_requests where status = any(:s)"),
                {"s": list(OPEN_CORRECTIONS)},
            )
            or 0
        )
    return SchoolDashboard(
        term=label(term) if term is not None else None,
        results=results,
        corrections_open=corrections,
        billing=billing_card(who=who, session=session),
    )


def my_sheet_counts(session: Session, who: Principal) -> MySheets:
    counts = MySheets()
    statuses = [r.status for r in my_sheets(who=who, session=session)]
    statuses += [r.status for r in my_rating_sheets(who=who, session=session)]
    for status in statuses:
        counts.total += 1
        if status in TO_DO:
            counts.to_do += 1
        elif status == "returned_for_correction":
            counts.returned += 1
        elif status in WAITING:
            counts.waiting += 1
        elif status in DONE:
            counts.done += 1
    return counts


def my_form_classes(session: Session, who: Principal, term: Any) -> list[MyClass]:
    rows = session.execute(
        text(
            "select a.id, c.name || a.name as class_name, coalesce(x.status, 'open') as status"
            " from teacher_assignments ta join class_arms a on a.id = ta.arm_id"
            " join classes c on c.id = a.class_id"
            " join school_levels l on l.level = c.level and l.enabled"
            " left join class_report_sections x on x.arm_id = a.id and x.term_id = :t"
            " where ta.teacher_id = :me and ta.is_form_teacher order by c.name, a.name"
        ),
        {"t": term.id, "me": who.user_id},
    )
    return [MyClass(arm_id=str(r.id), class_name=r.class_name, status=r.status) for r in rows]


def staff_dashboard(who: Principal, session: Session) -> StaffDashboard:
    term = active_term(session)
    if term is None:
        return StaffDashboard(
            term=None, sheets=MySheets(), review_waiting=None, my_class=[], attention=None
        )
    review_waiting = None
    if who.role is Role.REVIEWER:
        review_waiting = len(review_queue(who=who, session=session))
    return StaffDashboard(
        term=label(term),
        sheets=my_sheet_counts(session, who),
        review_waiting=review_waiting,
        my_class=my_form_classes(session, who, term),
        attention=attention_card(session, who, term),
    )


def form_teachers_owing(session: Session, term: Any, arms: list[Any]) -> set[uuid.UUID]:
    still_open = [a.id for a in open_section_arms(session, term, arms)]
    return set(
        session.scalars(
            text(
                "select teacher_id from teacher_assignments"
                " where is_form_teacher and arm_id = any(:a)"
            ),
            {"a": still_open},
        )
    )


def teachers_owing(session: Session, term: Any, arms: list[Any]) -> set[uuid.UUID]:
    owing: set[uuid.UUID] = set()
    for arm in arms:
        _, _, settings = current(session, arm.level)
        for need in needed_sheets(session, arm, term, settings.card):
            if need.status in UNSUBMITTED:
                owing.update(
                    session.scalars(
                        text(
                            "select teacher_id from teacher_subjects where arm_id = :a"
                            " and (subject_id = :n or learning_area_id = :n)"
                        ),
                        {"a": arm.id, "n": need.id},
                    )
                )
    return owing


def remind(body: Reminder, who: Principal, session: Session) -> Reminded:
    """A notice to those who still owe the work; never an email (default, D-179)."""
    if not feature_on(session, Feature.NOTICE_BOARD):
        raise ProblemError(
            404, "This feature is switched off for your school.", code="feature_disabled"
        )
    term = active_term(session)
    if term is None:
        raise ProblemError(409, "Activate a term first.", code="no_active_term")
    school_id = found(who.school_id)
    ensure_defaults(session, school_id, who.role.value)
    arms = arms_of(session, term)
    if body.audience == "form_teachers":
        owing = form_teachers_owing(session, term, arms)
        title = "Please submit your form class"
        words = f"Your form class comments and ratings for {label(term)} are not yet submitted."
    else:
        owing = teachers_owing(session, term, arms)
        title = "Please submit your result sheets"
        words = f"Some of your result sheets for {label(term)} are not yet submitted."
    told = owing & members(session)
    if not told:
        return Reminded(reminded=0)
    notice_id = session.scalar(
        text(
            "insert into notices (school_id, title, body, kind)"
            " values (:s, :t, :b, 'system') returning id"
        ),
        {"s": school_id, "t": title, "b": f"{words} Results cannot be published until they are."},
    )
    session.execute(
        text(
            "insert into notice_audiences (school_id, notice_id, role) values (:s, :n, 'teacher')"
        ),
        {"s": school_id, "n": notice_id},
    )
    for user_id in told:
        session.execute(
            text(
                "insert into notice_recipients (school_id, notice_id, user_id) values (:s, :n, :u)"
            ),
            {"s": school_id, "n": notice_id, "u": user_id},
        )
    write_audit(
        session,
        school_id,
        who.role.value,
        "dashboard.remind",
        target=("notices", notice_id),
        new={"audience": body.audience, "recipients": len(told)},
    )
    return Reminded(reminded=len(told))
