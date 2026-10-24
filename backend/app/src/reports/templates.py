"""Report templates: blocks, block settings and page settings (BUILD_PROMPT 9.2k).

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
from typing import Annotated, Any, Literal, Self

from fastapi import APIRouter, Depends
from fastapi.exceptions import RequestValidationError
from pydantic import Field, StringConstraints, ValidationError, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import DbSession, Principal, ensure_level_enabled, found, require
from app.core.errors import ProblemError
from app.core.schemas import ApiModel
from app.src.audit.services import write_audit
from app.src.schools.models import Level
from app.src.schools.schemas import HeadTitle, LevelName

router = APIRouter(prefix="/school", tags=["report templates"])

Member = Annotated[Principal, Depends(require())]
Manage = Annotated[Principal, Depends(require("report_templates.manage"))]

CoreStyle = Literal["modern", "classic", "compact", "early_years"]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Hex = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]

SCORE_BLOCKS = (
    "school_header", "student_details", "subject_table", "summary", "affective_psychomotor",
    "attendance", "comments", "signatures", "footer",
)  # fmt: skip
SKILLS_BLOCKS = (
    "school_header", "student_details", "skills_table", "rating_key", "attendance", "comments",
    "signatures", "footer",
)  # fmt: skip


class SchoolHeader(ApiModel):
    logo: bool = True
    logo_position: Literal["left", "centre", "right"] = "left"
    motto: bool = True
    address: bool = True
    contacts: bool = True
    report_title: Title = "Student Report Card"
    session_term_line: bool = True


class StudentDetails(ApiModel):
    photo: bool = False
    admission_number: bool = True
    gender: bool = True
    age: bool = False
    date_of_birth: bool = False
    class_arm: bool = True
    house: bool = False
    form_teacher_name: bool = True
    department: bool = False


class SubjectTable(ApiModel):
    components: bool = True
    total: bool = True
    grade: bool = True
    remark: bool = True
    position: bool = True
    class_average: bool = True
    highest: bool = False
    lowest: bool = False
    teacher_initials: bool = False
    highlight_below_pass: bool = False
    row_shading: bool = True
    group_by_category: bool = False


class Summary(ApiModel):
    total_score: bool = True
    total_average: bool = True
    overall_position: bool = True
    number_in_class: bool = True
    class_average: bool = False
    number_of_subjects: bool = False
    promotion_result: bool = False
    marks_obtainable: bool = False
    highest_average: bool = False
    lowest_average: bool = False


class AffectivePsychomotor(ApiModel):
    affective: bool = True
    psychomotor: bool = True
    rating_key: bool = True
    layout: Literal["side_by_side", "stacked"] = "side_by_side"


class AttendanceBlock(ApiModel):
    times_school_opened: bool = True
    times_present: bool = True
    times_absent: bool = True


class Comments(ApiModel):
    form_teacher: bool = True
    principal: bool = True
    show_names: bool = True


class Signatures(ApiModel):
    form_teacher_line: bool = True
    principal_signature_file_id: uuid.UUID | None = None
    stamp_file_id: uuid.UUID | None = None
    date_line: bool = True


class Footer(ApiModel):
    """The report ID, revision, publication date and QR code are always printed (AC12.3)."""

    qr_position: Literal["left", "right"] = "right"
    next_term_begins: bool = True
    contact_line: bool = True
    note: Note | None = None


class SkillsTable(ApiModel):
    area_comments: bool = True
    skill_descriptions: bool = False
    rating_display: Literal["words", "codes", "words_and_codes"] = "words"
    group_by_area: bool = True


class RatingKey(ApiModel):
    show_descriptions: bool = True


class Page(ApiModel):
    paper: Literal["a4", "letter"] = "a4"
    font: Literal["inter", "merriweather", "nunito"] = "inter"
    text_size: Literal["small", "medium", "large"] = "medium"
    accent: Hex | None = None  # the school colour when empty
    borders: Literal["none", "lines", "boxed"] = "lines"
    watermark: bool = False
    grading_key: Literal["off", "below_summary", "in_footer"] = "below_summary"
    margins: Literal["narrow", "normal"] = "normal"


def check_blocks(blocks: list[str], hidden: list[str], allowed: tuple[str, ...]) -> None:
    if sorted(blocks) != sorted(allowed):
        raise ValueError("List every block once: " + ", ".join(allowed) + ".")
    if blocks[-1] != "footer":
        raise ValueError("The footer is always last.")
    if "footer" in hidden:
        raise ValueError("The footer, with the report ID and QR code, is always shown.")
    if not set(hidden) <= set(allowed):
        raise ValueError("Only listed blocks can be hidden.")


class ScoreCard(ApiModel):
    card: Literal["scores"] = "scores"
    blocks: list[str] = Field(default_factory=lambda: list(SCORE_BLOCKS))
    hidden: list[str] = Field(default_factory=lambda: ["attendance"])
    school_header: SchoolHeader = SchoolHeader()
    student_details: StudentDetails = StudentDetails()
    subject_table: SubjectTable = SubjectTable()
    summary: Summary = Summary()
    affective_psychomotor: AffectivePsychomotor = AffectivePsychomotor()
    attendance: AttendanceBlock = AttendanceBlock()
    comments: Comments = Comments()
    signatures: Signatures = Signatures()
    footer: Footer = Footer()
    page: Page = Page()

    @model_validator(mode="after")
    def blocks_valid(self) -> Self:
        check_blocks(self.blocks, self.hidden, SCORE_BLOCKS)
        return self


class SkillsCard(ApiModel):
    card: Literal["skills"] = "skills"
    blocks: list[str] = Field(default_factory=lambda: list(SKILLS_BLOCKS))
    hidden: list[str] = Field(default_factory=list[str])
    school_header: SchoolHeader = SchoolHeader()
    student_details: StudentDetails = StudentDetails(age=True)
    skills_table: SkillsTable = SkillsTable()
    rating_key: RatingKey = RatingKey()
    attendance: AttendanceBlock = AttendanceBlock()
    comments: Comments = Comments()
    signatures: Signatures = Signatures()
    footer: Footer = Footer()
    page: Page = Page(font="nunito", text_size="large")

    @model_validator(mode="after")
    def blocks_valid(self) -> Self:
        check_blocks(self.blocks, self.hidden, SKILLS_BLOCKS)
        return self


Settings = ScoreCard | SkillsCard


def shown(settings: Settings, block: str) -> bool:
    return block in settings.blocks and block not in settings.hidden


class TemplateOut(ApiModel):
    level: str
    card: Literal["scores", "skills"]
    id: str | None
    version: int | None
    style: str
    head_title: str
    settings: dict[str, Any]


class TemplateIn(ApiModel):
    style: CoreStyle
    head_title: HeadTitle | None = None
    settings: dict[str, Any]


# --- reading and saving --------------------------------------------------------------------------


def card_for(session: Session, level: str) -> Literal["scores", "skills"]:
    mode = session.scalar(
        text("select assessment_mode from school_levels where level = :l"), {"l": level}
    )
    return "skills" if mode == "skill_ratings" else "scores"


def parse(card: Literal["scores", "skills"], raw: dict[str, Any]) -> Settings:
    model = SkillsCard if card == "skills" else ScoreCard
    return model.model_validate({**raw, "card": card})


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


@router.get("/report-templates", response_model=list[TemplateOut])
def list_templates(_: Member, session: DbSession) -> list[TemplateOut]:
    order = [level.value for level in Level]
    levels = sorted(
        session.scalars(text("select level from school_levels where enabled")), key=order.index
    )
    templates: list[TemplateOut] = []
    for level in levels:
        row, style, settings = current(session, str(level))
        templates.append(out(session, str(level), row, style, settings))
    return templates


@router.put("/report-templates/{level}", response_model=TemplateOut)
def save_template(
    level: LevelName, body: TemplateIn, who: Manage, session: DbSession
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
