"""Requests and responses of the publication routes (D-173)."""

import uuid
from typing import Annotated

from pydantic import Field, StringConstraints

from app.core.schemas import ApiModel

Comment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class Readiness(ApiModel):
    ready: bool
    problems: list[str]
    class_name: str
    status: str


class HeadComment(ApiModel):
    enrolment_id: uuid.UUID
    comment: Comment


class HeadComments(ApiModel):
    comments: Annotated[list[HeadComment], Field(min_length=1, max_length=200)]


class PublishedReport(ApiModel):
    enrolment_id: str
    admission_number: str
    report_code: str
    revision: int
    verification_code: str


class Published(ApiModel):
    published: int
    reports: list[PublishedReport]


class ReportRow(ApiModel):
    id: str
    enrolment_id: str
    admission_number: str
    pupil_name: str
    report_code: str
    revision: int
    status: str
    verification_code: str


class RevokeBody(ApiModel):
    reason: Reason


class Revoked(ApiModel):
    id: str
    status: str


class ReopenBody(ApiModel):
    reason: Reason
    sheet_ids: Annotated[list[uuid.UUID], Field(max_length=100)] = Field(
        default_factory=list[uuid.UUID]
    )
    sections: bool = False
    correction_request_id: uuid.UUID | None = None
