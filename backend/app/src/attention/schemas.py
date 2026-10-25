"""Requests and responses of the attention routes (D-173)."""

from typing import Literal

from app.core.schemas import ApiModel

View = Literal["by_subject", "by_student", "by_learning_area"]


class AttentionRow(ApiModel):
    report_id: str
    enrolment_id: str
    student_name: str
    admission_number: str
    class_name: str
    term_id: str
    subject: str | None = None
    score: int | None = None
    grade: str | None = None
    teacher: str | None = None
    learning_area: str | None = None
    skill: str | None = None
    rating: str | None = None
    failed_count: int | None = None
    average: str | None = None
    average_below_pass_mark: bool | None = None


class AttentionList(ApiModel):
    view: View
    term_id: str | None
    pass_mark: int
    count: int
    rows: list[AttentionRow]
