"""Report cards for the school's staff (BUILD_PROMPT 9.2k; SPEC F12; D-066, D-172).

School admins open any published report of their school as the printed
card's HTML or PDF (Valid, Superseded or Revoked, the status printed in the
footer), and preview a level's template with fictional data, watermarked
"Preview, not published", before saving it. Both use the same renderer as
the parents' card and the PDF.

Report templates: blocks, block settings and page settings (BUILD_PROMPT 9.2k).

SPEC F12 and F26 rule 6; D-061, D-170.

A template is versioned JSON, one per level that is on (each save is the next
version; nothing is edited in place). Its shape is checked here, so the PDF
renderer only ever sees settings it understands:
- the blocks in order, each shown or hidden, except the footer: always
  shown and always last;
- no setting exists that could hide the report ID, revision, publication date
  or QR code (AC12.3), and unknown settings are refused;
- a Score report card for a Scores level, a Skills report card for a Skill
  ratings level (AC12.4); the core styles only (Bold Banner, Ink Saver and
  Cumulative come after the core).
Until a school saves one, a level uses the defaults below (Modern for Score
cards, Early Years for Skills cards), which follow
`design/NAVIGATION_AND_SETTINGS.md` section 3 (CHANGE 2026-10-24). The
head's title is a template setting there; it is stored once per level
(`school_levels.head_title`), which is the same thing because each level
has one template.
"""

import uuid
from typing import Any, Literal

from fastapi import Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import Principal, ensure_level_enabled, found
from app.core.errors import ProblemError
from app.platform import pdf as pdf
from app.platform.storage import FileStorage
from app.src.audit.services import write_audit
from app.src.reports.render import Issued, logo_uri, render_card
from app.src.reports.schemas import ScoreCard, Settings, SkillsCard, TemplateIn, TemplateOut
from app.src.reports.utils import parse
from app.src.schools.models import Level
from app.src.schools.schemas import LevelName

# Fictional sample data for previews (the design's own example pupil).
SAMPLE_SUBJECTS = (
    ("English Language", (15, 14, 45), "B2", "Very good", 4, "65.1"),
    ("Mathematics", (16, 15, 47), "A1", "Excellent", 2, "64.8"),
    ("Basic Science", (14, 13, 42), "B3", "Good", 5, "61.7"),
    ("Social Studies", (16, 15, 49), "A1", "Excellent", 2, "70.3"),
)

SAMPLE_AREAS = (
    ("Number work", (("Counts 1 to 20", "Very good", "VG"), ("Recognises shapes", "Good", "G"))),
    ("Letter work", (("Recognises letters A to Z", "Excellent", "E"),)),
)


def school_report(session: Session, report_id: uuid.UUID) -> Any:
    return found(
        session.execute(
            text(
                "select id, report_code, revision, status, published_at, verification_code,"
                " snapshot from report_documents where id = :r"
            ),
            {"r": report_id},
        ).first()
    )


def school_report_card(
    report_id: uuid.UUID,
    _: Principal,
    session: Session,
    storage: FileStorage,
) -> HTMLResponse:
    return card_response(session, storage, school_report(session, report_id))


def school_report_pdf(
    report_id: uuid.UUID,
    _: Principal,
    session: Session,
    storage: FileStorage,
) -> Response:
    return pdf_response(session, storage, school_report(session, report_id))


def sample_snapshot(
    school: Any, level: str, style: str, settings: Settings, head_title: str
) -> dict[str, Any]:
    labels = ("CA1", "CA2", "Exam")
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
        "term": {"number": 1, "name": "First Term", "session": "2026/2027",
                 "next_term_begins": "2027-01-05"},
        "class": {"name": "JSS 1A" if settings.card == "scores" else "Nursery 2",
                  "level": level, "form_teacher": "Tunde Adebayo"},
        "pupil": {"surname": "Obi", "first_name": "Chukwuemeka", "other_names": None,
                  "admission_number": "GMC/2026/014", "gender": "male",
                  "date_of_birth": "2015-03-14", "house": "Blue"},
        "template": {"id": None, "version": None, "style": style,
                     "settings": settings.model_dump(mode="json")},
        "attendance": {"times_school_opened": 60, "times_present": 57, "times_absent": 3},
        "comments": {"form_teacher": "Chukwuemeka is attentive and works well with others.",
                     "form_teacher_name": "Tunde Adebayo", "head": "A good result. Keep it up.",
                     "head_title": head_title},
        "traits": [{"name": "Punctuality", "domain": "affective", "value": 5},
                   {"name": "Handwriting", "domain": "psychomotor", "value": 4}],
        "trait_key": {"5": "Excellent", "4": "Very good", "3": "Good", "2": "Fair", "1": "Poor"},
    }  # fmt: skip
    if settings.card == "scores":
        snapshot |= {
            "structure": [{"label": "CA1", "max_score": 20}, {"label": "CA2", "max_score": 20},
                          {"label": "Exam", "max_score": 60}],
            "grading": {"pass_mark": 40, "bands": [
                {"grade": "A1", "min_score": 75, "max_score": 100, "remark": "Excellent"},
                {"grade": "F9", "min_score": 0, "max_score": 39, "remark": "Fail"}]},
            "subjects": [
                {"name": name, "category": None, "teacher": "Tunde Adebayo",
                 "scores": dict(zip(labels, scores, strict=True)), "total": sum(scores),
                 "grade": grade, "remark": remark, "position": position,
                 "class_average": average, "highest": 88, "lowest": 31,
                 "below_pass_mark": False}
                for name, scores, grade, remark, position, average in SAMPLE_SUBJECTS
            ],
            "summary": {"total": 287, "average": "71.75", "position": 3, "number_in_class": 12,
                        "class_average": "65.40", "subjects": 4, "marks_obtainable": 400,
                        "highest_average": "82.10", "lowest_average": "44.30"},
        }  # fmt: skip
    else:
        snapshot |= {
            "areas": [
                {"name": area, "comment": "Making good progress.",
                 "skills": [{"skill": skill, "description": None, "rating": rating, "code": code,
                             "attention": False} for skill, rating, code in skills]}
                for area, skills in SAMPLE_AREAS
            ],
            "scale": [{"name": "Excellent", "code": "E", "description": None, "attention": False},
                      {"name": "Needs improvement", "code": "NI", "description": None,
                       "attention": True}],
        }  # fmt: skip
    return snapshot


def preview_template(
    level: LevelName,
    who: Principal,
    session: Session,
    storage: FileStorage,
) -> HTMLResponse:
    """The level's current template (or its defaults) with fictional data."""
    ensure_level_enabled(session, who, Level(level))
    card_for(session, level)
    _, style, settings = current(session, level)
    school = session.execute(
        text(
            "select name, code, address, city, state, phone, email, colour, logo_file_id"
            " from schools where id = :s"
        ),
        {"s": who.school_id},
    ).one()
    snapshot = sample_snapshot(school, level, style, settings, head_title_of(session, level))
    html = render_card(
        snapshot,
        Issued("GMC-2627-T1-JSS1A-014", 1, None, "7KQ4-M2XD-P9QA"),
        verify_base_url=str(get_settings().app_base_url),
        logo=school_logo(session, storage, snapshot),
        preview=True,
    )
    return HTMLResponse(html, headers={"Cache-Control": "private, no-store"})


# --- reading and saving --------------------------------------------------------------------------
def card_for(session: Session, level: str) -> Literal["scores", "skills"]:
    mode = session.scalar(
        text("select assessment_mode from school_levels where level = :l"), {"l": level}
    )
    return "skills" if mode == "skill_ratings" else "scores"


def latest(session: Session, level: str) -> Any:
    return session.execute(
        text(
            "select id, version, style, settings from report_templates where level = :l"
            " order by version desc limit 1"
        ),
        {"l": level},
    ).first()


def current(session: Session, level: str) -> tuple[Any, str, Settings]:
    """(saved row or None, style, settings) for the level; the defaults when unsaved."""
    card = card_for(session, level)
    row = latest(session, level)
    if row is not None and row.settings.get("card", "scores") == card:
        return row, row.style, parse(card, row.settings)
    default = SkillsCard() if card == "skills" else ScoreCard()
    return None, "early_years" if card == "skills" else "modern", default


def save(session: Session, who: Principal, level: str, style: str, settings: Settings) -> Any:
    template_id = session.scalar(
        text(
            "insert into report_templates (school_id, level, style, settings)"
            " values (:s, :l, :st, cast(:j as jsonb)) returning id"
        ),
        {"s": who.school_id, "l": level, "st": style, "j": settings.model_dump_json()},
    )
    write_audit(
        session,
        who.school_id,
        who.role.value,
        "report_templates.save",
        target=("report_templates", template_id),
        new={"level": level, "style": style},
    )
    return session.execute(
        text("select id, version, style, settings from report_templates where id = :id"),
        {"id": template_id},
    ).one()


def template_for_publication(session: Session, who: Principal, level: str) -> tuple[Any, Settings]:
    """The level's latest template; the defaults are saved as version 1 if none was saved."""
    row, style, settings = current(session, level)
    if row is None:
        row = save(session, who, level, style, settings)
    return row, settings


def head_title_of(session: Session, level: str) -> str:
    title: str = session.scalar(
        text("select head_title from school_levels where level = :l"), {"l": level}
    )
    return title


def out(session: Session, level: str, row: Any, style: str, settings: Settings) -> TemplateOut:
    return TemplateOut(
        level=level,
        card=settings.card,
        id=str(row.id) if row else None,
        version=row.version if row else None,
        style=style,
        head_title=head_title_of(session, level),
        settings=settings.model_dump(mode="json"),
    )


def list_templates(
    _: Principal,
    session: Session,
) -> list[TemplateOut]:
    order = [level.value for level in Level]
    levels = sorted(
        session.scalars(text("select level from school_levels where enabled")), key=order.index
    )
    templates: list[TemplateOut] = []
    for level in levels:
        row, style, settings = current(session, str(level))
        templates.append(out(session, str(level), row, style, settings))
    return templates


def save_template(
    level: LevelName,
    body: TemplateIn,
    who: Principal,
    session: Session,
) -> TemplateOut:
    ensure_level_enabled(session, who, Level(level))
    card = card_for(session, level)
    try:
        settings = parse(card, body.settings)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from None
    signatures = settings.signatures
    for file_id, purpose in (
        (signatures.principal_signature_file_id, "signature"),
        (signatures.stamp_file_id, "stamp"),
    ):
        if file_id is not None and not session.scalar(
            text("select exists (select 1 from files where id = :f and purpose = :p)"),
            {"f": file_id, "p": purpose},
        ):
            raise ProblemError(
                422, f"Choose an uploaded {purpose} of this school.", code="unknown_file"
            )
    old_title = head_title_of(session, level)
    if body.head_title is not None and body.head_title != old_title:
        session.execute(
            text("update school_levels set head_title = :h where level = :l"),
            {"h": body.head_title, "l": level},
        )
        write_audit(
            session,
            who.school_id,
            who.role.value,
            "school_levels.update",
            target=("schools", found(who.school_id)),
            old={"level": level, "head_title": old_title},
            new={"level": level, "head_title": body.head_title},
        )
    row = save(session, who, level, body.style, settings)
    return out(session, level, row, body.style, settings)


PRIVATE = {"Cache-Control": "private, no-store"}


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
