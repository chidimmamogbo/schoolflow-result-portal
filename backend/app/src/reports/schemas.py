"""Requests and responses of the reports routes (D-173)."""

import uuid
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from app.core.schemas import ApiModel
from app.src.schools.schemas import HeadTitle

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


Settings = ScoreCard | SkillsCard
