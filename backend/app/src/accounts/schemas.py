"""Requests and responses of the accounts routes (D-173)."""

from typing import Literal, Self

from pydantic import model_validator

from app.core.schemas import ApiModel
from app.src.platform_admin.schemas import Email, Line, Username


class NewAdmin(ApiModel):
    full_name: Line
    username: Username
    email: Email | None = None
    login_method: Literal["activation", "temporary_password"]

    @model_validator(mode="after")
    def activation_needs_email(self) -> Self:
        if self.login_method == "activation" and self.email is None:
            raise ValueError("An activation email needs an email address.")
        return self


class AdminRow(ApiModel):
    id: str
    full_name: str
    username: str
    email: str | None
    is_primary: bool
    is_active: bool
    activated: bool


class Admins(ApiModel):
    admins: list[AdminRow]
    places_left: int


class CreatedAdmin(ApiModel):
    id: str
    # Shown once, for the "Staff login slip" (D-040); None with an activation email.
    temporary_password: str | None
