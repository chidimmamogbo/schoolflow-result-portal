"""Requests and responses of the form_class routes (D-173)."""

import uuid
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.core.schemas import ApiModel

Comment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]

ReturnComment = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]


# --- shapes -------------------------------------------------------------------------------
class MyClass(ApiModel):
    arm_id: str
    class_name: str
    level: str
    status: str
    revision: int
    can_submit: bool


class TraitOut(ApiModel):
    id: str
    name: str
    domain: str


class PupilEntry(ApiModel):
    enrolment_id: str
    admission_number: str
    surname: str
    first_name: str
    comment: str | None
    times_present: int | None
    times_absent: int | None
    ratings: dict[str, int]
    average: Decimal | None
    suggested_comments: list[str]


class EntryCounts(ApiModel):
    pupils: int
    with_comment: int
    with_attendance: int


class ClassView(ApiModel):
    arm_id: str
    class_name: str
    level: str
    term_id: str
    status: str
    revision: int
    status_comment: str | None
    times_school_opened: int | None
    can_edit: bool
    can_submit: bool
    traits: list[TraitOut]
    key: dict[str, str]
    pupils: list[PupilEntry]
    counts: EntryCounts


class BroadsheetSubject(ApiModel):
    id: str
    name: str
    sheet_id: str | None
    status: str


class BroadsheetRow(ApiModel):
    enrolment_id: str
    admission_number: str
    surname: str
    first_name: str
    totals: dict[str, int | None]
    average: Decimal | None
    position: int | None


class Broadsheet(ApiModel):
    kind: Literal["scores", "ratings"]
    subjects: list[BroadsheetSubject]
    rows: list[BroadsheetRow]
    class_average: Decimal | None


class AttendanceDays(ApiModel):
    times_school_opened: Annotated[int, Field(ge=1, le=366)]


class EntryIn(ApiModel):
    comment: Comment | None = None
    times_present: Annotated[int, Field(ge=0, le=366)] | None = None
    ratings: dict[uuid.UUID, Annotated[int, Field(ge=1, le=5)] | None] | None = None


class SectionMove(ApiModel):
    arm_id: str
    status: str
    revision: int
    status_comment: str | None


class ReturnBody(ApiModel):
    comment: ReturnComment


class PreviewSubject(ApiModel):
    name: str
    total: int | None
    grade: str | None


class PreviewTrait(ApiModel):
    name: str
    domain: str
    value: int | None


class Attendance(ApiModel):
    times_school_opened: int | None
    times_present: int | None
    times_absent: int | None


class Preview(ApiModel):
    label: str
    school_name: str
    class_name: str
    pupil_name: str
    admission_number: str
    subjects: list[PreviewSubject]
    average: Decimal | None
    position: int | None
    comment: str | None
    traits: list[PreviewTrait]
    attendance: Attendance
