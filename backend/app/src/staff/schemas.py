"""Requests and responses of the staff routes (D-173)."""

import uuid
from typing import Literal, Self

from pydantic import model_validator

from app.core.schemas import ApiModel
from app.src.platform_admin.schemas import Email, Line, Username


# --- shapes -------------------------------------------------------------------------------
class NewStaff(ApiModel):
    full_name: Line
    username: Username
    email: Email | None = None
    role: Literal["teacher", "reviewer"]
    login_method: Literal["activation", "temporary_password"]

    @model_validator(mode="after")
    def activation_needs_email(self) -> Self:
        if self.login_method == "activation" and self.email is None:
            raise ValueError("An activation email needs an email address.")
        return self


class EditStaff(ApiModel):
    full_name: Line | None = None
    email: Email | None = None


class StaffRow(ApiModel):
    id: str
    full_name: str
    username: str
    email: str | None
    role: str
    is_active: bool
    activated: bool


class NewAssignment(ApiModel):
    teacher_id: uuid.UUID
    arm_id: uuid.UUID
    subject_id: uuid.UUID | None = None
    learning_area_id: uuid.UUID | None = None
    is_form_teacher: bool = False
    teaches_all_subjects: bool = False

    @model_validator(mode="after")
    def one_kind(self) -> Self:
        kinds = (self.subject_id is not None) + (self.learning_area_id is not None)
        if kinds + self.is_form_teacher != 1:
            raise ValueError("Give a subject, a learning area, or make them the form teacher.")
        if self.teaches_all_subjects and not self.is_form_teacher:
            raise ValueError("Only the form teacher can teach all subjects.")
        return self


class AssignmentRow(ApiModel):
    id: str
    teacher_id: str
    teacher_name: str
    arm_id: str
    subject_id: str | None
    learning_area_id: str | None
    is_form_teacher: bool
    teaches_all_subjects: bool


class NewAssistant(ApiModel):
    user_id: uuid.UUID


class AssistantRow(ApiModel):
    user_id: str
    full_name: str
    username: str


class NewScope(ApiModel):
    department_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    class_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def department_or_subjects(self) -> Self:
        if (self.department_id is not None) == (
            self.subject_id is not None or self.class_id is not None
        ):
            raise ValueError("Give a whole department, or subjects and/or classes.")
        return self


class ScopeRow(ApiModel):
    id: str
    department_id: str | None
    subject_id: str | None
    class_id: str | None
