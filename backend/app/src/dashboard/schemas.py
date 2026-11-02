"""What the dashboards send (BUILD_PROMPT 9.2u; SPEC F16; D-179)."""

from typing import Literal

from pydantic import Field

from app.core.schemas import ApiModel
from app.src.billing.schemas import SchoolBilling


class SheetCounts(ApiModel):
    awaiting_submission: int = 0
    awaiting_review: int = 0
    awaiting_approval: int = 0
    approved: int = 0
    published: int = 0
    total: int = 0


class ClassProgress(SheetCounts):
    class_name: str


class SheetProblem(ApiModel):
    sheet_id: str
    class_name: str
    name: str
    count: int


class Problems(ApiModel):
    count: int = 0
    sheets: list[SheetProblem] = Field(default_factory=list[SheetProblem])


class UnusualChange(ApiModel):
    sheet_id: str
    student_name: str
    class_name: str
    subject: str
    column: str
    old: int
    new: int
    reason: str


class AverageRow(ApiModel):
    name: str
    average: str
    pass_rate: str


class TermAverage(ApiModel):
    term: str
    average: str


class Stats(ApiModel):
    """Approved and published score sheets only; Skill ratings levels compute nothing."""

    sheets_counted: int = 0
    average: str | None = None
    pass_rate: str | None = None
    by_subject: list[AverageRow] = Field(default_factory=list[AverageRow])
    by_class: list[AverageRow] = Field(default_factory=list[AverageRow])
    trend: list[TermAverage] = Field(default_factory=list[TermAverage])


class AttentionCard(ApiModel):
    term: str
    pass_mark: int
    subject_results: int
    skills: int
    students: int


class SchoolResults(ApiModel):
    nothing_started: bool
    sheets: SheetCounts
    classes: list[ClassProgress]
    missing_scores: Problems
    missing_ratings: Problems
    invalid_scores: Problems
    open_sections: list[str]
    unusual_changes: list[UnusualChange]
    stats: Stats
    attention: AttentionCard | None


class SchoolDashboard(ApiModel):
    term: str | None
    results: SchoolResults | None
    corrections_open: int | None
    billing: SchoolBilling


class MySheets(ApiModel):
    to_do: int = 0
    returned: int = 0
    waiting: int = 0
    done: int = 0
    total: int = 0


class MyClass(ApiModel):
    arm_id: str
    class_name: str
    status: str


class StaffDashboard(ApiModel):
    term: str | None
    sheets: MySheets
    review_waiting: int | None
    my_class: list[MyClass]
    attention: AttentionCard | None


class Reminder(ApiModel):
    audience: Literal["form_teachers", "teachers"]


class Reminded(ApiModel):
    reminded: int
