"""Requests and responses of the correction queue (SPEC F15; D-174)."""

import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import StringConstraints

from app.core.schemas import ApiModel

Explanation = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
IssueType = Literal["score", "detail", "other"]
Status = Literal["open", "investigating", "needs_more_information", "resolved", "rejected"]


class NewRequest(ApiModel):
    report_id: uuid.UUID
    subject_id: uuid.UUID | None = None
    learning_area_id: uuid.UUID | None = None
    issue_type: IssueType
    explanation: Explanation


class Move(ApiModel):
    status: Status
    message: Message | None = None


class RequestRow(ApiModel):
    id: str
    number: str
    status: Status
    issue_type: IssueType
    student_name: str
    class_name: str
    term: str
    subject: str | None
    learning_area: str | None
    report_code: str
    revision: int
    requested_by: str | None
    created_at: dt.datetime


class Requests(ApiModel):
    open: int  # the Corrections badge: requests not yet resolved or rejected
    requests: list[RequestRow]


class Event(ApiModel):
    from_status: Status | None
    to_status: Status
    actor_name: str | None
    message: str | None
    created_at: dt.datetime


class Attachment(ApiModel):
    content_type: str
    size_bytes: int
    original_name: str


class LinkedReport(ApiModel):
    id: str
    report_code: str
    revision: int
    status: str
    published_at: dt.datetime | None


class Score(ApiModel):
    name: str
    before: int | None
    after: int | None


class Average(ApiModel):
    before: str | None
    after: str | None


class Change(ApiModel):
    """What the corrected report changed, for the request's subject and overall."""

    subject: Score | None
    average: Average


class RequestDetail(RequestRow):
    explanation: str
    status_message: str | None
    events: list[Event]
    attachment: Attachment | None
    corrected_report: LinkedReport | None
    change: Change | None
