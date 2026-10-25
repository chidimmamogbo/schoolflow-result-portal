"""Requests and responses of the portal routes (D-173)."""

import datetime as dt
from typing import Any

from app.core.schemas import ApiModel
from app.platform import pdf as pdf


class LatestReport(ApiModel):
    report_id: str
    term: str
    session: str
    status: str
    revision: int
    published_at: dt.datetime | None
    card: str
    average: str | None
    position: int | None
    number_in_class: int | None
    subjects: int | None


class Child(ApiModel):
    student_id: str
    name: str
    admission_number: str
    class_name: str | None
    latest: LatestReport | None


class SchoolChildren(ApiModel):
    school_id: str
    school_name: str
    school_code: str
    colour: str | None
    logo_url: str | None
    children: list[Child]


class ReportRow(ApiModel):
    report_id: str
    term: str
    session: str
    class_name: str
    report_code: str
    revision: int
    status: str
    published_at: dt.datetime | None


class ReportView(ApiModel):
    report_id: str
    report_code: str
    revision: int
    status: str
    published_at: dt.datetime | None
    verification_code: str | None
    has_newer_revision: bool
    card: str
    school: dict[str, Any]
    term: dict[str, Any]
    class_info: dict[str, Any]
    pupil: dict[str, Any]
    subjects: list[dict[str, Any]] | None
    summary: dict[str, Any] | None
    structure: list[dict[str, Any]] | None
    areas: list[dict[str, Any]] | None
    scale: list[dict[str, Any]] | None
    attendance: dict[str, Any]
    comments: dict[str, Any]
    traits: list[dict[str, Any]]
    trait_key: dict[str, Any]
