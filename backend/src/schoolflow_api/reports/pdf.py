"""Report card PDFs (BUILD_PROMPT 9.2k; SPEC F12; D-058, D-060, D-064, D-067; CHANGE 2026-10-24).

A PDF is never stored: it is made again on each download from the same card
HTML as the online card (D-058, D-066), by WeasyPrint. WeasyPrint needs the
Pango system library, which the backend container and CI install; on a
machine without it (this project's Windows laptop) PDF downloads answer 503
and the PDF tests skip. The fetcher allows only inline `data:` resources
(the logo), so a PDF never reaches the network or the disk (D-064); fonts
come from the system by name. The same report always gives the same bytes
(D-067): the creation date is the publication date and the PDF identifier
comes from the report ID and revision.
"""

import hashlib
import importlib
from functools import lru_cache
from typing import Any

from schoolflow_api.core.errors import ProblemError


@lru_cache
def weasyprint() -> Any:
    """WeasyPrint, loaded on first use (it needs Pango, D-070; it ships no type stubs)."""
    try:
        module = importlib.import_module("weasyprint")
        importlib.import_module("weasyprint.urls")
    except (ImportError, OSError) as error:
        raise ProblemError(
            503, "Service unavailable", "PDF downloads are not available on this server."
        ) from error
    return module


def available() -> bool:
    try:
        weasyprint()
    except ProblemError:
        return False
    return True


def pdf_of(html: str, report_code: str, revision: int) -> bytes:
    module = weasyprint()
    identifier = hashlib.sha256(f"{report_code}:{revision}".encode()).digest()[:16]
    # Inline data only: no network, no files (D-064; WeasyPrint 70 URLFetcher).
    fetcher = module.urls.URLFetcher(allowed_protocols={"data"}, fail_on_errors=False)
    document = module.HTML(string=html, url_fetcher=fetcher)
    pdf: bytes = document.write_pdf(pdf_identifier=identifier)
    return pdf


def filename(report_code: str, revision: int) -> str:
    return f"{report_code}-revision-{revision}.pdf"
