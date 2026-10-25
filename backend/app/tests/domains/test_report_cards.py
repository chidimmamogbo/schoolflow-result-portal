"""Report card HTML (BUILD_PROMPT 9.2k; SPEC F12, F26; AC12.3, AC26.3; D-061 to D-066, D-172).

Behaviour: the card is built from the snapshot alone, block by block in the
template's order with the footer (report ID, revision, publication date, QR
code) always last; hidden blocks are left out; a Skills card never shows
totals, grades or positions; school data is escaped, the accent colour must
be a plain colour, and nothing is loaded from the network. School admins
open any report's card and preview templates with fictional data marked
"Preview, not published"; others are refused. All data is fictional.
"""

import datetime as dt
from html import unescape
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.src.reports.render import PREVIEW_LABEL, Issued, render_card
from app.src.reports.schemas import ScoreCard, SkillsCard
from app.src.reports.services import sample_snapshot
from app.tests.domains.test_publication import app, as_, code_of, fast_hashing, gmc, send
from app.tests.domains.test_republishing import publish_a

__all__ = ["app", "fast_hashing", "gmc"]

SCHOOL = SimpleNamespace(
    name="Greenfield Model College", code="GMC", address="Independence Layout", city="Enugu",
    state="Enugu", phone="08010000001", email="office@gmc.example", colour="#1E6B45",
    logo_file_id=None,
)  # fmt: skip
ISSUED = Issued(
    "GMC-2627-T1-JSS1A-014", 2, dt.datetime(2026, 12, 8, 14, 2, tzinfo=dt.UTC), "7KQ4-M2XD-P9QA"
)


def card(snapshot: dict[str, Any], **kw: Any) -> str:
    return render_card(snapshot, ISSUED, verify_base_url="https://schoolflow.example/", **kw)


def test_a_score_card_follows_its_template() -> None:
    settings = ScoreCard()
    html = card(sample_snapshot(SCHOOL, "junior_secondary", "modern", settings, "Principal"))
    footer = "Report ID <strong>GMC-2627-T1-JSS1A-014</strong> · Revision 2 · Published 8 Dec 2026"
    verify = "enter code 7KQ4-M2XD-P9QA at https://schoolflow.example/verify"
    for text_ in ("Greenfield Model College", "Chukwuemeka Obi", "GMC/2026/014", "Mathematics",
                  "TOTAL", "Overall class position", "Principal's comment", footer, verify,
                  "<svg"):  # fmt: skip
        assert text_.lower() in html.lower(), text_
    assert "Times school opened" not in html  # Attendance is hidden by default
    assert "<script" not in html and "http://" not in html
    assert html.index("Student Report Card") < html.index("Mathematics") < html.index("Report ID")
    assert PREVIEW_LABEL not in html

    # Hidden blocks are left out; the footer stays, and stays last.
    settings = ScoreCard(hidden=["subject_table", "comments"])
    html = card(sample_snapshot(SCHOOL, "junior_secondary", "classic", settings, "Principal"))
    body = html[html.index("<body>") :]
    assert "Mathematics" not in body and "comment" not in body.lower()
    assert "Class position" in html  # the Classic style's label
    assert html.rindex("Report ID") > html.rindex("Total score")


def test_a_skills_card_never_shows_totals_grades_or_positions() -> None:
    settings = SkillsCard()
    html = card(sample_snapshot(SCHOOL, "nursery", "early_years", settings, "Head teacher"))
    assert "Counts 1 to 20" in html and "Very good" in html and "Rating key" in html
    shown = unescape(html)
    assert "Class teacher's comment" in shown and "Head teacher's comment" in shown
    body = html[html.index("<body>") :].lower()
    for word in ("total", "grade", "position", "average"):  # AC26.3
        assert word not in body, word
    codes = card(
        sample_snapshot(
            SCHOOL, "nursery", "early_years",
            SkillsCard.model_validate({"skills_table": {"rating_display": "codes"}}),
            "Head teacher",
        )
    )  # fmt: skip
    assert "<td>VG</td>" in codes


def test_school_data_is_escaped_and_colours_are_checked() -> None:
    school = SimpleNamespace(**{**vars(SCHOOL), "name": "<b>Bold</b> & Co", "colour": "red;}"})
    html = card(sample_snapshot(school, "junior_secondary", "modern", ScoreCard(), "Principal"))
    assert "<b>Bold</b>" not in html and "&lt;b&gt;Bold&lt;/b&gt; &amp; Co" in html
    assert "red;}" not in html and "--accent: #1F4E79" in html
    accent = ScoreCard.model_validate({"page": {"accent": "#AA3300"}})
    html = card(sample_snapshot(SCHOOL, "junior_secondary", "modern", accent, "Principal"))
    assert "--accent: #AA3300" in html
    preview = card(
        sample_snapshot(SCHOOL, "junior_secondary", "modern", ScoreCard(), "x"), preview=True
    )
    assert PREVIEW_LABEL in preview


def test_school_admins_open_cards_and_preview_templates(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    publish_a(app, gmc)
    report_id = db_session.scalar(
        text("select id from report_documents where report_code = 'GMC-2627-T1-JSS1A-014'")
    )
    ngozi = as_(app, "ngozi.okeke")
    response = ngozi.get(f"/api/v1/school/reports/{report_id}/card.html")
    assert response.status_code == 200
    assert "Chukwuemeka Obi" in response.text and "GMC-2627-T1-JSS1A-014" in response.text
    tunde = as_(app, "tunde.adebayo")
    assert code_of(send(tunde, "GET", f"/school/reports/{report_id}/card.html")) == (
        403,
        "permission_denied",
    )

    preview = ngozi.get("/api/v1/school/report-templates/junior_secondary/preview.html")
    assert preview.status_code == 200
    assert PREVIEW_LABEL in preview.text and "Greenfield Model College" in preview.text
    assert send(tunde, "GET", "/school/report-templates/junior_secondary/preview.html")[0] == 403
    assert code_of(send(ngozi, "GET", "/school/report-templates/nursery/preview.html")) == (
        404,
        "level_disabled",
    )


def test_published_snapshots_keep_the_term_dates(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    publish_a(app, gmc)
    term = db_session.execute(
        text("select starts_on, ends_on from terms where id = :t"), {"t": gmc["term"]}
    ).one()
    report_id, snapshot = db_session.execute(
        text(
            "select id, snapshot from report_documents where report_code = 'GMC-2627-T1-JSS1A-014'"
        )
    ).one()
    assert (snapshot["term"]["starts_on"], snapshot["term"]["ends_on"]) == (
        term.starts_on.isoformat(),
        term.ends_on.isoformat(),
    )
    html = as_(app, "ngozi.okeke").get(f"/api/v1/school/reports/{report_id}/card.html").text
    expected = (
        f"{term.starts_on.day} {term.starts_on:%b %Y} to {term.ends_on.day} {term.ends_on:%b %Y}"
    )
    assert "Term dates" in html and expected in html
