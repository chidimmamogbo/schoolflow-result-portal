"""Report cards for the school's staff (BUILD_PROMPT 9.2k; SPEC F12; D-066, D-172).

School admins open any published report of their school as the printed
card's HTML or PDF (Valid, Superseded or Revoked, the status printed in the
footer), and preview a level's template with fictional data, watermarked
"Preview, not published", before saving it. Both use the same renderer as
the parents' card and the PDF.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import DbSession, Principal, ensure_level_enabled, found, require
from app.src.portal.router import Storage, card_response, pdf_response, school_logo
from app.src.reports.render import Issued, render_card
from app.src.reports.templates import Settings, card_for, current, head_title_of
from app.src.schools.models import Feature, Level
from app.src.schools.schemas import LevelName

router = APIRouter(prefix="/school", tags=["report cards"])

Publishers = Annotated[Principal, Depends(require("results.publish", feature=Feature.RESULTS))]
Designers = Annotated[Principal, Depends(require("report_templates.manage"))]

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


@router.get("/reports/{report_id}/card.html", response_class=HTMLResponse)
def school_report_card(
    report_id: uuid.UUID, _: Publishers, session: DbSession, storage: Storage
) -> HTMLResponse:
    return card_response(session, storage, school_report(session, report_id))


@router.get("/reports/{report_id}/report.pdf", response_class=Response)
def school_report_pdf(
    report_id: uuid.UUID, _: Publishers, session: DbSession, storage: Storage
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


@router.get("/report-templates/{level}/preview.html", response_class=HTMLResponse)
def preview_template(
    level: LevelName, who: Designers, session: DbSession, storage: Storage
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
