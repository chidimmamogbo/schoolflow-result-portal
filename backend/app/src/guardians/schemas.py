"""Requests and responses of the guardians routes (D-173)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from app.core.schemas import ApiModel
from app.src.platform_admin.schemas import Email, Line, Username

Relationship = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]

Phone = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9][0-9 ()-]{5,19}$")
]


class WardLink(ApiModel):
    student_id: uuid.UUID
    relationship: Relationship


class NewGuardian(ApiModel):
    full_name: Line
    phone: Phone | None = None
    email: Email | None = None
    wards: Annotated[list[WardLink], Field(min_length=1, max_length=20)]
    login: Literal["link_request", "temporary_password", "none"]
    username: Username | None = None

    @model_validator(mode="after")
    def login_fits_the_email(self) -> Self:
        if self.email is not None and self.login != "link_request":
            raise ValueError("A parent with an email is added by a link request (D-140).")
        if self.email is None and self.login == "link_request":
            raise ValueError("A link request needs an email.")
        if self.login == "temporary_password" and self.username is None:
            raise ValueError("A login slip needs a username.")
        return self


class EditGuardian(ApiModel):
    full_name: Line | None = None
    phone: Phone | None = None
    privacy_consent: bool | None = None


class WardRow(ApiModel):
    student_id: str
    name: str
    relationship: str


class GuardianRow(ApiModel):
    id: str
    full_name: str
    phone: str | None
    email: str | None
    login_status: Literal["none", "waiting", "linked", "paused"]
    wards: list[WardRow]


class GuardianCreated(ApiModel):
    id: str
    login_status: str
    # Shown once, only for a parent without an email (D-140).
    temporary_password: str | None


class LinkRequestRow(ApiModel):
    id: str
    school_id: str
    school_name: str
    school_code: str
    guardian_name: str
    created_at: datetime
    expires_at: datetime


class Accepted(ApiModel):
    school_id: str
