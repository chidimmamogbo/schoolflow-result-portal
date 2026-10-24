"""Report card PDFs (BUILD_PROMPT 9.2k; SPEC F12, F14; CHANGE 2026-10-24).

D-058, D-064, D-067, D-069.

Behaviour: a parent, the pupil and school admins download a published
report as a PDF made again from the card's HTML on each download; it holds
the pupil's name, the subjects and scores and the report ID; the same report
always gives the same bytes, dated with its publication date; it is A4 by
default. Nobody downloads a report that is not theirs. Without Pango (this
project's Windows laptop) downloads answer 503 and the PDF checks skip; in
CI they must run. All data is fictional.
"""

import datetime as dt
import io
import os
from typing import Any

import pypdf
import pypdfium2  # pyright: ignore[reportMissingTypeStubs]
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from schoolflow_api.core.errors import ProblemError
from schoolflow_api.reports import pdf
from tests.auth_support import logged_in
from tests.test_publication import app, as_, code_of, fast_hashing, gmc, send
from tests.test_republishing import publish_a

__all__ = ["app", "fast_hashing", "gmc"]

needs_pango = pytest.mark.skipif(
    not pdf.available() and os.environ.get("CI") != "true",
    reason="WeasyPrint needs Pango (installed in CI and the container, not on Windows)",
)


def chukwuemeka_report(db_session: Session) -> tuple[Any, Any]:
    row = db_session.execute(
        text(
            "select id, published_at from report_documents"
            " where report_code = 'GMC-2627-T1-JSS1A-014'"
        )
    ).one()
    return row.id, row.published_at


def test_ci_can_make_pdfs() -> None:
    if os.environ.get("CI") == "true":
        assert pdf.available(), "CI must install Pango so the PDF tests run"


def test_only_the_family_and_school_admins_download(
    app: FastAPI, db_session: Session, gmc: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    publish_a(app, gmc)
    report_id, _ = chukwuemeka_report(db_session)
    assert send(as_(app, "ada.eze"), "GET", f"/me/reports/{report_id}/report.pdf")[0] == 404
    assert code_of(
        send(as_(app, "tunde.adebayo"), "GET", f"/school/reports/{report_id}/report.pdf")
    ) == (
        403,
        "permission_denied",
    )

    def missing() -> Any:
        raise ProblemError(503, "Service unavailable", "PDF downloads are not available.")

    monkeypatch.setattr(pdf, "weasyprint", missing)
    assert send(as_(app, "ikenna.obi"), "GET", f"/me/reports/{report_id}/report.pdf")[0] == 503


@needs_pango
def test_a_parent_downloads_the_report_as_a_pdf(
    app: FastAPI, db_session: Session, gmc: dict[str, Any]
) -> None:
    publish_a(app, gmc)
    report_id, published_at = chukwuemeka_report(db_session)
    ikenna = as_(app, "ikenna.obi")
    response = ikenna.get(f"/api/v1/me/reports/{report_id}/report.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="GMC-2627-T1-JSS1A-014-revision-1.pdf"'
    )
    assert response.headers["cache-control"] == "private, no-store"

    document = pypdf.PdfReader(io.BytesIO(response.content))
    words = " ".join(page.extract_text() for page in document.pages)
    for expected in ("Chukwuemeka Obi", "GMC-2627-T1-JSS1A-014", "Mathematics", "78", "Revision 1"):
        assert expected in words, expected
    created = document.metadata.creation_date if document.metadata else None
    assert created is not None
    assert created.astimezone(dt.UTC).replace(microsecond=0) == published_at.astimezone(
        dt.UTC
    ).replace(microsecond=0)

    # The same report gives the same bytes (D-067), for the family and for staff.
    again = ikenna.get(f"/api/v1/me/reports/{report_id}/report.pdf").content
    staff = as_(app, "ngozi.okeke").get(f"/api/v1/school/reports/{report_id}/report.pdf").content
    assert again == response.content == staff

    pupil = logged_in(app, "chukwuemeka.obi", school_code="GMC")
    assert pupil.get(f"/api/v1/me/reports/{report_id}/report.pdf").status_code == 200

    page: Any = pypdfium2.PdfDocument(response.content)[0]  # pypdfium2 is loosely typed
    width, height = page.get_size()
    assert (round(width), round(height)) == (595, 842)  # A4 in points
    image = page.render(scale=1).to_pil()
    assert image.width > 0 and image.getbbox() is not None  # something is drawn
