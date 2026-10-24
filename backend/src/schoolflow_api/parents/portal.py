"""The parent and student portal (BUILD_PROMPT 9.2m; SPEC F14; AC14.1, AC14.2; D-138, D-172).

A parent sees the children linked to them in every school where their link
is active and the Parent portal is on, grouped by school with its name, logo
and colour (one account across schools, D-138); a student sees only
themselves. Only published reports appear (AC14.1): Valid ones and older
Superseded revisions, each with its status and revision; a revoked report is
withdrawn and never shown. A report opens as light data for the online view
or as the printed card's HTML or PDF. Reading another school's children switches
the database's school for that query only, and only to schools the signed-
in parent belongs to; reports themselves are read in the school chosen with
X-School-Id, like every other request. Staff use the school's own pages.
"""

import datetime as dt
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.authz.deps import Principal, found, require
from schoolflow_api.authz.permissions import Role
from schoolflow_api.core.deps import DbSession
from schoolflow_api.core.errors import ProblemError
from schoolflow_api.core.schemas import ApiModel
from schoolflow_api.db import use_context
from schoolflow_api.files.storage import FileStorage, get_file_storage
from schoolflow_api.reports import pdf
from schoolflow_api.reports.render import Issued, logo_uri, render_card
from schoolflow_api.schools.models import Feature
from schoolflow_api.settings import get_settings

router = APIRouter(prefix="/me", tags=["my children"])

Families = Annotated[Principal, Depends(require("reports.view"))]
Readers = Annotated[Principal, Depends(require("reports.view", feature=Feature.PARENT_PORTAL))]
Storage = Annotated[FileStorage, Depends(get_file_storage)]
FAMILY = (Role.PARENT, Role.STUDENT)
PRIVATE = {"Cache-Control": "private, no-store"}
TERM_NAMES = {1: "First Term", 2: "Second Term", 3: "Third Term"}


class LatestReport(ApiModel):
    report_id: str
    term: str
    session: str
    status: str
    revision: int
    published_at: dt.datetime | None
    card: str
    average: str | None
    position: int | None
    number_in_class: int | None
    subjects: int | None


class Child(ApiModel):
    student_id: str
    name: str
    admission_number: str
    class_name: str | None
    latest: LatestReport | None


class SchoolChildren(ApiModel):
    school_id: str
    school_name: str
    school_code: str
    colour: str | None
    logo_url: str | None
    children: list[Child]


class ReportRow(ApiModel):
    report_id: str
    term: str
    session: str
    class_name: str
    report_code: str
    revision: int
    status: str
    published_at: dt.datetime | None


class ReportView(ApiModel):
    report_id: str
    report_code: str
    revision: int
    status: str
    published_at: dt.datetime | None
    verification_code: str | None
    has_newer_revision: bool
    card: str
    school: dict[str, Any]
    term: dict[str, Any]
    class_info: dict[str, Any]
    pupil: dict[str, Any]
    subjects: list[dict[str, Any]] | None
    summary: dict[str, Any] | None
    structure: list[dict[str, Any]] | None
    areas: list[dict[str, Any]] | None
    scale: list[dict[str, Any]] | None
    attendance: dict[str, Any]
    comments: dict[str, Any]
    traits: list[dict[str, Any]]
    trait_key: dict[str, Any]


def family_only(who: Principal) -> None:
    if who.role not in FAMILY:
        raise ProblemError(403, "You don't have permission to do this.", code="permission_denied")


# A ward of the signed-in person: their own record (a student) or a linked child.
MINE = """(
    st.user_id = :me
    or exists (select 1 from guardian_students gs join guardians g on g.id = gs.guardian_id
               where gs.student_id = st.id and g.user_id = :me)
)"""


def children_here(session: Session, who: Principal) -> list[Child]:
    rows = session.execute(
        text(
            "select st.id, st.first_name || ' ' || st.surname as name, st.admission_number,"  # noqa: S608 (fixed SQL)
            " (select c.name || a.name from enrolments e join class_arms a on a.id = e.arm_id"
            "  join classes c on c.id = a.class_id where e.student_id = st.id"
            "  and e.left_on is null order by e.created_at desc limit 1) as class_name,"
            " d.id as report_id, t.term_number, y.name as session_name, d.status, d.revision,"
            " d.published_at, d.snapshot ->> 'card' as card,"
            " d.snapshot -> 'summary' ->> 'average' as average,"
            " cast(d.snapshot -> 'summary' ->> 'position' as integer) as position,"
            " cast(d.snapshot -> 'summary' ->> 'number_in_class' as integer) as in_class,"
            " cast(d.snapshot -> 'summary' ->> 'subjects' as integer) as subjects"
            f" from students st left join lateral (select d.* from report_documents d"
            "   join enrolments e on e.id = d.enrolment_id"
            "   where e.student_id = st.id and d.status = 'valid'"
            "   order by d.published_at desc nulls last limit 1) d on true"
            " left join terms t on t.id = d.term_id"
            " left join academic_sessions y on y.id = t.session_id"
            f" where {MINE} order by st.first_name, st.surname"
        ),
        {"me": who.user_id},
    )
    return [
        Child(
            student_id=str(r.id),
            name=r.name,
            admission_number=r.admission_number,
            class_name=r.class_name,
            latest=None
            if r.report_id is None
            else LatestReport(
                report_id=str(r.report_id),
                term=TERM_NAMES[r.term_number],
                session=r.session_name,
                status=r.status,
                revision=r.revision,
                published_at=r.published_at,
                card=r.card,
                average=r.average,
                position=r.position,
                number_in_class=r.in_class,
                subjects=r.subjects,
            ),
        )
        for r in rows
    ]


@router.get("/children", response_model=list[SchoolChildren])
def my_children(who: Families, session: DbSession) -> list[SchoolChildren]:
    """Every school where this parent's link is active and the portal is on (AC14.2), by name."""
    family_only(who)
    schools = (
        [m.school_id for m in who.memberships if m.active and m.role is Role.PARENT]
        if who.role is Role.PARENT
        else [found(who.school_id)]
    )
    groups: list[SchoolChildren] = []
    try:
        for school_id in schools:
            use_context(session, school_id=school_id, user_id=who.user_id)
            school = session.execute(
                text(
                    "select s.id, s.name, s.code, s.colour, s.logo_file_id, s.status,"
                    " (select enabled from school_features where feature = 'parent_portal')"
                    " as portal from schools s where s.id = :s"
                ),
                {"s": school_id},
            ).first()
            if school is None or school.status != "active" or not school.portal:
                continue
            groups.append(
                SchoolChildren(
                    school_id=str(school.id),
                    school_name=school.name,
                    school_code=school.code,
                    colour=school.colour,
                    logo_url=f"/api/v1/auth/schools/{school.code}/logo"
                    if school.logo_file_id
                    else None,
                    children=children_here(session, who),
                )
            )
    finally:
        use_context(session, school_id=who.school_id, user_id=who.user_id)
    return sorted(groups, key=lambda g: (g.school_name.lower(), g.school_code))


def my_student(session: Session, who: Principal, student_id: uuid.UUID) -> None:
    found(
        session.scalar(
            text(f"select st.id from students st where st.id = :s and {MINE}"),  # noqa: S608
            {"s": student_id, "me": who.user_id},
        )
    )


@router.get("/students/{student_id}/reports", response_model=list[ReportRow])
def student_reports(student_id: uuid.UUID, who: Readers, session: DbSession) -> list[ReportRow]:
    family_only(who)
    my_student(session, who, student_id)
    rows = session.execute(
        text(
            "select d.id, t.term_number, y.name as session_name, d.snapshot -> 'class' ->> 'name'"
            " as class_name, d.report_code, d.revision, d.status, d.published_at"
            " from report_documents d join enrolments e on e.id = d.enrolment_id"
            " join terms t on t.id = d.term_id join academic_sessions y on y.id = t.session_id"
            " where e.student_id = :s and d.status in ('valid', 'superseded')"
            " order by y.starts_on desc, t.term_number desc, d.revision desc"
        ),
        {"s": student_id},
    )
    return [
        ReportRow(
            report_id=str(r.id),
            term=TERM_NAMES[r.term_number],
            session=r.session_name,
            class_name=r.class_name,
            report_code=r.report_code,
            revision=r.revision,
            status=r.status,
            published_at=r.published_at,
        )
        for r in rows
    ]


def my_report(session: Session, who: Principal, report_id: uuid.UUID) -> Any:
    family_only(who)
    return found(
        session.execute(
            text(
                "select d.id, d.report_code, d.revision, d.status, d.published_at,"  # noqa: S608 (fixed SQL)
                " d.verification_code, d.snapshot, exists (select 1 from report_documents n"
                "  where n.enrolment_id = d.enrolment_id and n.term_id = d.term_id"
                "  and n.revision > d.revision) as has_newer"
                " from report_documents d join enrolments e on e.id = d.enrolment_id"
                " join students st on st.id = e.student_id"
                f" where d.id = :r and d.status in ('valid', 'superseded') and {MINE}"
            ),
            {"r": report_id, "me": who.user_id},
        ).first()
    )


@router.get("/reports/{report_id}", response_model=ReportView)
def report_view(report_id: uuid.UUID, who: Readers, session: DbSession) -> ReportView:
    """The low-bandwidth online view: the report's own data, as published."""
    row = my_report(session, who, report_id)
    s = row.snapshot
    return ReportView(
        report_id=str(row.id),
        report_code=row.report_code,
        revision=row.revision,
        status=row.status,
        published_at=row.published_at,
        verification_code=row.verification_code,
        has_newer_revision=row.has_newer,
        card=s["card"],
        school={k: v for k, v in s["school"].items() if k != "logo_file_id"},
        term=s["term"],
        class_info=s["class"],
        pupil=s["pupil"],
        subjects=s.get("subjects"),
        summary=s.get("summary"),
        structure=s.get("structure"),
        areas=s.get("areas"),
        scale=s.get("scale"),
        attendance=s["attendance"],
        comments=s["comments"],
        traits=s.get("traits", []),
        trait_key=s.get("trait_key", {}),
    )


def school_logo(session: Session, storage: FileStorage, snapshot: dict[str, Any]) -> str | None:
    file_id = snapshot["school"].get("logo_file_id")
    if not file_id:
        return None
    row = session.execute(
        text("select storage_key, content_type from files where id = :f"), {"f": file_id}
    ).first()
    return logo_uri(storage.get(row.storage_key), row.content_type) if row else None


def card_html(session: Session, storage: FileStorage, row: Any) -> str:
    return render_card(
        row.snapshot,
        Issued(row.report_code, row.revision, row.published_at, row.verification_code, row.status),
        verify_base_url=str(get_settings().app_base_url),
        logo=school_logo(session, storage, row.snapshot),
    )


def card_response(session: Session, storage: FileStorage, row: Any) -> HTMLResponse:
    return HTMLResponse(card_html(session, storage, row), headers=PRIVATE)


def pdf_response(session: Session, storage: FileStorage, row: Any) -> Response:
    """The PDF, made again from the same HTML on each download (D-058)."""
    body = pdf.pdf_of(card_html(session, storage, row), row.report_code, row.revision)
    name = pdf.filename(row.report_code, row.revision)
    return Response(
        body,
        media_type="application/pdf",
        headers={**PRIVATE, "Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/reports/{report_id}/card.html", response_class=HTMLResponse)
def report_card(
    report_id: uuid.UUID, who: Readers, session: DbSession, storage: Storage
) -> HTMLResponse:
    """The printed card as HTML (the PDF is made from the same HTML)."""
    return card_response(session, storage, my_report(session, who, report_id))


@router.get("/reports/{report_id}/report.pdf", response_class=Response)
def report_pdf(
    report_id: uuid.UUID, who: Readers, session: DbSession, storage: Storage
) -> Response:
    return pdf_response(session, storage, my_report(session, who, report_id))
