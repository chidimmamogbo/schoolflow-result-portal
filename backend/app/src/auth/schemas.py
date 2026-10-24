"""Request and response shapes for /auth (BUILD_PROMPT 9.2b).

Lengths are generous outer limits only; the real password rules (D-036) are
checked in routes.py so each refusal gets its own clear code.
"""

from typing import Annotated

from pydantic import Field

from app.core.schemas import ApiModel

Text = Annotated[str, Field(min_length=1, max_length=254)]
Password = Annotated[str, Field(min_length=1, max_length=1024)]
Token = Annotated[str, Field(min_length=1, max_length=200)]


class LoginRequest(ApiModel):
    identifier: Text
    password: Password
    # Only on the Student tab (D-033).
    school_code: Annotated[str, Field(min_length=1, max_length=10)] | None = None


class LoginResult(ApiModel):
    must_change_password: bool


class ChangePasswordRequest(ApiModel):
    current_password: Password
    new_password: Password


class LinkRequest(ApiModel):
    token: Token
    password: Password


class ForgotRequest(ApiModel):
    # Any text: a username or admission number gets the same answer (AC02.8).
    email: Text


class Accepted(ApiModel):
    detail: str


class SchoolPublic(ApiModel):
    code: str
    name: str
    colour: str
    # The logo route arrives with uploads (9.2e); until then there is none.
    logo_url: str | None


class MeUser(ApiModel):
    id: str
    full_name: str
    username: str
    email: str | None


class MeSchool(ApiModel):
    id: str
    code: str
    name: str
    colour: str


class MeSchoolLink(ApiModel):
    id: str
    name: str
    role: str


class FormClass(ApiModel):
    arm_id: str
    name: str


class Me(ApiModel):
    user: MeUser
    school: MeSchool | None
    schools: list[MeSchoolLink]
    role: str
    is_primary: bool
    is_super_admin: bool
    must_change_password: bool
    permissions: list[str]
    features: list[str]
    form_class: FormClass | None
    unread_notices: int
