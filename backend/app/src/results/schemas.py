"""Requests and responses of the results routes (D-173)."""

import uuid
from typing import Annotated, Literal

from pydantic import Field, StrictInt, StringConstraints

from app.core.schemas import ApiModel

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


# --- shapes ---------------------------------------------------------------------------------
class SheetRow(ApiModel):
    id: str | None
    arm_id: str
    subject_id: str
    class_name: str
    subject_name: str
    level: str
    status: str
    revision: int | None


class OpenSheet(ApiModel):
    arm_id: uuid.UUID
    subject_id: uuid.UUID


class ColumnOut(ApiModel):
    id: str
    label: str
    name: str
    max_score: int


class PupilRow(ApiModel):
    enrolment_id: str
    admission_number: str
    surname: str
    first_name: str
    scores: dict[str, int]
    total: int | None
    grade: str | None
    missing: list[str]
    out_of_range: list[str]


class Counts(ApiModel):
    complete: int
    missing: int
    errors: int


class SheetView(ApiModel):
    id: str
    class_name: str
    subject_name: str
    level: str
    term_id: str
    status: str
    revision: int
    status_comment: str | None
    can_edit: bool
    columns: list[ColumnOut]
    rows: list[PupilRow]
    counts: Counts


class Cell(ApiModel):
    enrolment_id: uuid.UUID
    component_id: uuid.UUID
    # Whole numbers only: 15.5 and "15" are refused (AT-11.2). None removes a score.
    value: StrictInt | None


class SaveScores(ApiModel):
    scores: Annotated[list[Cell], Field(max_length=2000)]
    reason: Reason | None = None


class ImportRow(ApiModel):
    row: int
    admission_number: str
    errors: list[str]


class ImportPreview(ApiModel):
    rows: list[ImportRow]
    valid: int
    invalid: int


Comment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class RatingSheetRow(ApiModel):
    id: str | None
    arm_id: str
    learning_area_id: str
    class_name: str
    learning_area_name: str
    level: str
    status: str
    revision: int | None


class OpenRatingSheet(ApiModel):
    arm_id: uuid.UUID
    learning_area_id: uuid.UUID


class SkillOut(ApiModel):
    id: str
    name: str
    description: str | None


class PointOut(ApiModel):
    id: str
    name: str
    code: str
    is_attention: bool


class PupilRatings(ApiModel):
    enrolment_id: str
    admission_number: str
    surname: str
    first_name: str
    ratings: dict[str, str]
    comment: str | None
    missing: list[str]


class RatingCounts(ApiModel):
    complete: int
    missing: int


class RatingSheetView(ApiModel):
    id: str
    class_name: str
    learning_area_name: str
    level: str
    term_id: str
    status: str
    revision: int
    status_comment: str | None
    can_edit: bool
    skills: list[SkillOut]
    scale: list[PointOut]
    rows: list[PupilRatings]
    counts: RatingCounts


class RatingCell(ApiModel):
    enrolment_id: uuid.UUID
    skill_id: uuid.UUID
    point_id: uuid.UUID | None


class CommentCell(ApiModel):
    enrolment_id: uuid.UUID
    comment: Comment | None


class SaveRatings(ApiModel):
    ratings: Annotated[list[RatingCell], Field(max_length=3000)] = Field(
        default_factory=list[RatingCell]
    )
    comments: Annotated[list[CommentCell], Field(max_length=200)] = Field(
        default_factory=list[CommentCell]
    )
    reason: Reason | None = None


MoveComment = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]


class MoveResult(ApiModel):
    id: str
    status: str
    revision: int
    status_comment: str | None


class ReturnBody(ApiModel):
    comment: MoveComment


class SheetSummary(ApiModel):
    id: str
    kind: Literal["scores", "ratings"]
    class_name: str
    name: str
    status: str
    revision: int
    needs_review: bool
