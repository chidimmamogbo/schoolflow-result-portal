"""Report card HTML from a frozen snapshot (BUILD_PROMPT 9.2k; SPEC F12, F26; D-061 to D-067).

The renderer reads only the published snapshot (what the report says) and the
report's own record (report ID, revision, publication date, verification
code), never the live tables, so a report always looks as it was issued.
One Jinja2 file per block, included in the template's order with the footer
always last; Score and Skills report cards share the engine, and a Skills
card never shows totals, averages, grades or positions (AC26.3). Autoescape
is on, the card uses light colours only (PDFs and print are always light),
fonts are named, never fetched, and nothing is loaded from the network: the
QR code is an inline SVG holding only the verification URL (D-065) and the
logo, when given, is an inline data URI. The same HTML serves the online
view, previews (watermarked "Preview, not published") and, through
WeasyPrint, the PDF (D-066).
"""

import base64
import datetime as dt
import re
from dataclasses import dataclass
from typing import Any

import segno
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape
from markupsafe import Markup

from app.src.reports.schemas import Settings
from app.src.reports.utils import parse
from app.src.results.engine import ordinal

PREVIEW_LABEL = "Preview, not published"
DEFAULT_ACCENT = "#1F4E79"
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

environment = Environment(
    loader=PackageLoader("app.src.reports", "html"),
    autoescape=select_autoescape(default=True, default_for_string=True),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass(frozen=True)
class Issued:
    """What the report's own record adds to the snapshot."""

    report_code: str
    revision: int
    published_at: dt.datetime | None
    verification_code: str | None
    status: str = "valid"


def day(value: dt.date | dt.datetime | str | None) -> str:
    """Dates as the design shows them: 5 Jan 2027."""
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        value = dt.date.fromisoformat(value[:10])
    return f"{value.day} {value:%b %Y}"


def place(value: int | None) -> str:
    return "" if value is None else ordinal(value)


def initials(name: str | None) -> str:
    return "".join(part[0] for part in (name or "").split() if part).upper()


def age_on(birth: str | None, when: dt.date) -> int | None:
    if not birth:
        return None
    born = dt.date.fromisoformat(birth)
    return when.year - born.year - ((when.month, when.day) < (born.month, born.day))


def qr_svg(url: str) -> Markup:
    """The verification URL as an inline SVG (no other data in the QR, D-071)."""
    svg = segno.make(url, error="m").svg_inline(scale=3, border=2, dark="#000000", light="#ffffff")
    return Markup(svg)  # segno's own SVG markup; the URL is ours  # noqa: S704


def logo_uri(content: bytes | None, content_type: str | None) -> str | None:
    if not content or content_type not in ("image/png", "image/jpeg", "image/webp"):
        return None
    return f"data:{content_type};base64,{base64.b64encode(content).decode()}"


environment.filters["day"] = day
environment.filters["place"] = place
environment.filters["initials"] = initials


def visible_blocks(settings: Settings) -> list[str]:
    blocks = [b for b in settings.blocks if b not in settings.hidden and b != "footer"]
    return [*blocks, "footer"]


def render_card(
    snapshot: dict[str, Any],
    issued: Issued,
    *,
    verify_base_url: str,
    logo: str | None = None,
    preview: bool = False,
) -> str:
    """The whole card as one HTML document."""
    settings = parse(snapshot["card"], snapshot["template"]["settings"])
    published = (issued.published_at or dt.datetime.now(dt.UTC)).date()
    verify_url = (
        f"{verify_base_url.rstrip('/')}/verify/{issued.verification_code}"
        if issued.verification_code
        else None
    )
    traits = snapshot.get("traits", [])
    # Only a plain #RRGGBB colour reaches the stylesheet.
    accent = next(
        (c for c in (settings.page.accent, snapshot["school"].get("colour")) if c and HEX.match(c)),
        DEFAULT_ACCENT,
    )
    return environment.get_template("card.html").render(
        s=snapshot,
        t=settings,
        style=snapshot["template"]["style"],
        accent=accent,
        blocks=visible_blocks(settings),
        issued=issued,
        published_on=day(issued.published_at) if issued.published_at else "",
        published_iso=issued.published_at.isoformat(timespec="seconds")
        if issued.published_at
        else None,
        verify_url=verify_url,
        verify_base=verify_base_url.rstrip("/") + "/verify",
        qr=qr_svg(verify_url) if verify_url else None,
        logo=logo,
        preview=preview,
        preview_label=PREVIEW_LABEL,
        age=age_on(snapshot["pupil"].get("date_of_birth"), published),
        affective=[x for x in traits if x["domain"] == "affective"],
        psychomotor=[x for x in traits if x["domain"] == "psychomotor"],
        head_label=(snapshot["comments"].get("head_title") or "Head teacher"),
    )
