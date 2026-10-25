"""Requests and responses of the students routes (D-173)."""

import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from app.core.schemas import ApiModel
from app.src.platform_admin.schemas import Username

NamePart = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]

OtherNames = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

AdmissionNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9/._-]{0,29}$")
]

House = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class PupilFields(ApiModel):
    surname: NamePart
    first_name: NamePart
    other_names: OtherNames | None = None
    admission_number: AdmissionNumber
    gender: Literal["female", "male"]
    date_of_birth: date | None = None
    house: House | None = None


class EditPupil(ApiModel):
    surname: NamePart | None = None
    first_name: NamePart | None = None
    other_names: OtherNames | None = None
    admission_number: AdmissionNumber | None = None
    gender: Literal["female", "male"] | None = None
    date_of_birth: date | None = None
    house: House | None = None
    department_id: uuid.UUID | None = None
    status: Literal["active", "withdrawn", "graduated"] | None = None


class PupilRow(ApiModel):
    id: str
    surname: str
    first_name: str
    other_names: str | None
    admission_number: str
    gender: str
    date_of_birth: date | None
    house: str | None
    department_id: str | None
    status: str
    arm_id: str | None
    has_login: bool


class Move(ApiModel):
    arm_id: uuid.UUID


class PupilSubjects(ApiModel):
    subject_ids: Annotated[list[uuid.UUID], Field(max_length=40)]


class SubjectName(ApiModel):
    id: str
    name: str


class NewLogin(ApiModel):
    username: Username


class ImportRow(ApiModel):
    row: int
    admission_number: str
    surname: str
    first_name: str
    errors: list[str]


class ImportPreview(ApiModel):
    rows: list[ImportRow]
    valid: int
    invalid: int


class Imported(ApiModel):
    created: int
