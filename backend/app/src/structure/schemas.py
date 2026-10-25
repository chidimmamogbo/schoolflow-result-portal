"""Requests and responses of the structure routes (D-173)."""

from datetime import date
from typing import Annotated, Self

from pydantic import Field, StringConstraints, model_validator

from app.core.schemas import ApiModel
from app.src.schools.schemas import LevelName, Name

ArmName = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)]

SessionName = Annotated[str, StringConstraints(pattern=r"^[0-9]{4}/[0-9]{4}$")]


class NewSession(ApiModel):
    name: SessionName
    starts_on: date
    ends_on: date

    @model_validator(mode="after")
    def years_follow_on(self) -> Self:
        first, second = (int(year) for year in self.name.split("/"))
        if second != first + 1:
            raise ValueError("A session runs over two years in a row, like 2026/2027.")
        if self.ends_on <= self.starts_on:
            raise ValueError("The session must end after it starts.")
        return self


class TermFields(ApiModel):
    starts_on: date
    ends_on: date
    next_term_begins: date | None = None

    @model_validator(mode="after")
    def dates_in_order(self) -> Self:
        if self.ends_on <= self.starts_on:
            raise ValueError("The term must end after it starts.")
        if self.next_term_begins is not None and self.next_term_begins <= self.ends_on:
            raise ValueError("Next term must begin after this term ends.")
        return self


class NewTerm(TermFields):
    term_number: Annotated[int, Field(ge=1, le=3)]


class EditTerm(ApiModel):
    starts_on: date | None = None
    ends_on: date | None = None
    next_term_begins: date | None = None


class TermRow(ApiModel):
    id: str
    term_number: int
    starts_on: date
    ends_on: date
    next_term_begins: date | None
    is_active: bool


class SessionRow(ApiModel):
    id: str
    name: str
    starts_on: date
    ends_on: date
    terms: list[TermRow]


class NewClass(ApiModel):
    level: LevelName
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class Rename(ApiModel):
    name: Name


class NewArm(ApiModel):
    name: ArmName = ""


class ArmRow(ApiModel):
    id: str
    name: str


class ClassRow(ApiModel):
    id: str
    level: str
    name: str
    arms: list[ArmRow]


class NewDepartment(ApiModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class DepartmentRow(ApiModel):
    id: str
    name: str


class SubjectFields(ApiModel):
    name: Name
    department_id: str | None = None
    category: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)] | None
    ) = None


class EditSubject(ApiModel):
    name: Name | None = None
    department_id: str | None = None
    category: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)] | None
    ) = None


class SubjectRow(ApiModel):
    id: str
    name: str
    department_id: str | None
    category: str | None


class ArmSubjects(ApiModel):
    subject_ids: Annotated[list[str], Field(max_length=40)]
